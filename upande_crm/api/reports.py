"""Run ERPNext's own CRM and Selling reports inside the CRM.

This is a *presentation* layer, not a reimplementation. `frappe.desk.query_report.run`
executes any report type and hands back columns, rows, an optional chart and an
optional summary; the CRM renders that with its own tiles, charts and tables.
Reimplementing the report logic in Python here would guarantee the two drift.

## Why there is a registry rather than a generic runner

A Script Report's filters are declared in its **client-side `.js`**, not on the
Report doctype — `frappe.get_doc("Report", name).filters` is empty for all 35
reports on this site. So the server cannot discover what a report needs, and
running them blind fails for about a third:

    Sales Analytics          AttributeError: 'NoneType' has no attribute 'startswith'
    Quotation Trends         'Based On' is mandatory
    Sales Person-wise …      Please select the document type first
    Inactive Customers       'Days Since Last Order' must be >= zero

`REPORTS` below therefore declares each report's filters explicitly, and every
entry is asserted to actually run by `tests/test_reports.py`. Anything not in the
registry and not filter-free is listed in the catalogue with a desk link instead
of being run into a traceback.

Traps found by measuring, worth not rediscovering:
  * the filter is `doc_type` in Sales Analytics and Sales Person-wise Transaction
    Summary, but `doctype` in Inactive Customers;
  * the trends reports reject `based_on` equal to `group_by`;
  * the two site-custom Query Reports declare no filters yet reference
    `%(from_date)s` in their SQL, so dates must be passed anyway.

## Permissions — the deliberate exception in this app

Every other endpoint here role-gates and then reads with `ignore_permissions=True`,
because the dashboards are a shared sales command centre (a recorded, intended
decision). **Reports do not do that.** `Customer Credit Balance` and the commission
summaries are financial, and the report runner already enforces Report permissions
plus the referenced doctype's, so it is called without widening: a user who may not
read a report gets a clean refusal rather than the data. `_guard()` still gates the
endpoints themselves.
"""

import json

import frappe
from frappe import _

from upande_crm.api.crm import _guard, _range

# Sentinels resolved per request, so reports obey the CRM's own header controls.
COMPANY = "__company__"
RANGE_FROM = "__range_from__"
RANGE_TO = "__range_to__"
CUSTOMER = "__customer__"
FISCAL_YEAR = "__fiscal_year__"

GROUPS = (
    ("pipeline", "Pipeline", "Opportunities, stages and what was lost"),
    ("leads", "Leads", "Inbound quality, owner effectiveness and conversion"),
    ("customers", "Customers", "Acquisition, loyalty, dormancy and exposure"),
    ("sales", "Sales", "Orders, revenue mix and rep performance"),
)

DATED = {"from_date": RANGE_FROM, "to_date": RANGE_TO}


def _r(key, report, group, label, blurb, filters=None, editable=(), date_scoped=None):
    return {
        "key": key,
        "report": report,
        "group": group,
        "label": label,
        "blurb": blurb,
        "filters": filters or {},
        "editable": tuple(editable),
        # Whether the header date pill reaches this report at all. Inferred from
        # the filter set unless stated, so a card can say "not date-scoped"
        # instead of implying a range it ignores.
        "date_scoped": date_scoped if date_scoped is not None
        else any(v in (RANGE_FROM, RANGE_TO) for v in (filters or {}).values()),
    }


# Every entry here is asserted to run by tests/test_reports.py.
REPORTS = (
    # ---------------------------------------------------------------- pipeline
    # based_on/data_based_on are not optional despite not being marked reqd:
    # omitting them fails with a bare `KeyError: None`.
    _r("pipeline_by_stage", "Opportunity Summary by Sales Stage", "pipeline",
       "Pipeline by sales stage",
       "Opportunity count and value at each stage of the funnel.",
       {"company": COMPANY, **DATED, "based_on": "Source", "data_based_on": "Number"},
       editable=("based_on", "data_based_on")),
    _r("pipeline_analytics", "Sales Pipeline Analytics", "pipeline",
       "Pipeline analytics",
       "Opportunity flow over time, grouped by owner.",
       {"company": COMPANY, **DATED, "pipeline_by": "Owner", "range": "Monthly",
        "based_on": "Number"},
       editable=("pipeline_by", "range", "based_on")),
    _r("lost_opportunity", "Lost Opportunity", "pipeline",
       "Lost opportunities",
       "What was lost, and the reason recorded against it."),
    _r("first_response", "First Response Time for Opportunity", "pipeline",
       "First response time",
       "How long opportunities waited for their first reply."),
    _r("campaign_efficiency", "Campaign Efficiency", "pipeline",
       "Campaign efficiency",
       "Leads and conversions attributed to each campaign.",
       {**DATED}),

    # ---------------------------------------------------------------- leads
    _r("lead_details", "Lead Details", "leads",
       "Lead details",
       "Every lead with owner, territory, source and contact details."),
    _r("lead_owner_efficiency", "Lead Owner Efficiency", "leads",
       "Lead owner efficiency",
       "Conversion rate per lead owner."),
    _r("lead_conversion_time", "Lead Conversion Time", "leads",
       "Lead conversion time",
       "How long leads take to convert, by owner.",
       {"company": COMPANY, **DATED}, editable=("company",)),
    _r("prospects_stalled", "Prospects Engaged But Not Converted", "leads",
       "Engaged but not converted",
       "Prospects that have been worked and have not moved."),
    _r("crm_conversion", "CRM Conversion", "leads",
       "CRM conversion",
       "This site's own lead-to-customer conversion report."),

    # ---------------------------------------------------------------- customers
    _r("acquisition_loyalty", "Customer Acquisition and Loyalty", "customers",
       "Acquisition and loyalty",
       "New against repeat customers, period by period.",
       {"company": COMPANY, **DATED}, editable=("company",)),
    _r("never_transacted", "Customers Without Any Sales Transactions", "customers",
       "Never transacted",
       "Customer records that have never bought anything."),
    _r("inactive_customers", "Inactive Customers", "customers",
       "Dormant customers",
       "Customers with no order in the last N days.",
       {"days_since_last_order": 60, "doctype": "Sales Order"},
       editable=("days_since_last_order", "doctype"), date_scoped=False),
    _r("credit_balance", "Customer Credit Balance", "customers",
       "Credit balance",
       "Credit limit against outstanding exposure per customer.",
       {"company": COMPANY}, editable=("company",)),
    _r("territory_sales", "Territory-wise Sales", "customers",
       "Territory-wise sales",
       "Opportunity and order value by territory."),

    # ---------------------------------------------------------------- sales
    _r("sales_analytics", "Sales Analytics", "sales",
       "Sales analytics",
       "Order value by customer over time — ERPNext's own pivot.",
       {"company": COMPANY, **DATED, "tree_type": "Customer", "doc_type": "Sales Order",
        "value_quantity": "Value", "range": "Monthly"},
       editable=("tree_type", "doc_type", "value_quantity", "range")),
    # Runs bare without error but returns no columns at all until it is given a
    # range — an empty grid rather than a failure, which is worse to debug.
    _r("order_analysis", "Sales Order Analysis", "sales",
       "Sales order analysis",
       "Delivery and billing progress against each order.",
       {"company": COMPANY, **DATED}, editable=("company",)),
    _r("item_sales_history", "Item-wise Sales History", "sales",
       "Item-wise sales history",
       "What sold, to whom, and for how much.",
       {"company": COMPANY, **DATED}, editable=("company",)),
    _r("lost_quotations", "Lost Quotations", "sales",
       "Lost quotations",
       "Quotations that did not convert, grouped by reason.",
       {"company": COMPANY, "timespan": "This Year", "group_by": "Lost Reason"},
       editable=("timespan", "group_by"), date_scoped=False),
    _r("rep_transactions", "Sales Person-wise Transaction Summary", "sales",
       "Sales person transactions",
       "Order value credited to each sales person.",
       {"company": COMPANY, **DATED, "doc_type": "Sales Order"},
       editable=("doc_type",)),
    _r("payment_terms", "Payment Terms Status for Sales Order", "sales",
       "Payment terms status",
       "Which order instalments are due or overdue."),
    _r("order_trends", "Sales Order Trends", "sales",
       "Sales order trends",
       "Order value by period. 'Based on' and 'Group by' may not match.",
       {"company": COMPANY, "period": "Monthly", "based_on": "Customer",
        "group_by": "Item", "fiscal_year": FISCAL_YEAR, "include_closed_orders": 0},
       editable=("period", "based_on", "group_by"), date_scoped=False),
    _r("variety_sales", "Sales per Variety Report (SO)", "sales",
       "Sales per variety",
       "This site's own per-variety order report.",
       {**DATED, "company": COMPANY}),
)

BY_KEY = {entry["key"]: entry for entry in REPORTS}
REGISTERED_NAMES = {entry["report"] for entry in REPORTS}

# Modules whose reports the catalogue lists.
CATALOGUE_MODULES = ("CRM", "Selling")

# Rows sent to the browser per report. `Item-wise Sales History` returns 39,232
# rows for one year on this site — enough to lock up the tab. The cap is reported
# back as `truncated` with the true total and a desk link, never applied silently:
# a table that quietly showed the first 500 of 39,232 would be a wrong answer.
ROW_CAP = 500


def _fiscal_year(to_date):
    try:
        return str(frappe.utils.getdate(to_date).year)
    except Exception:
        return str(frappe.utils.getdate(frappe.utils.nowdate()).year)


def _context(date_from, date_to, customer):
    frm, to = _range(date_from, date_to)
    return {
        COMPANY: frappe.defaults.get_global_default("company") or "",
        RANGE_FROM: frm,
        RANGE_TO: to,
        CUSTOMER: customer or "",
        FISCAL_YEAR: _fiscal_year(to),
    }


def _resolve(filters, ctx):
    """Replace sentinels with this request's values."""
    return {k: ctx.get(v, v) if isinstance(v, str) else v for k, v in (filters or {}).items()}


def _load(payload):
    if isinstance(payload, str):
        try:
            return json.loads(payload or "null")
        except ValueError:
            frappe.throw(_("Malformed filters"))
    return payload


# ---------------------------------------------------------------- registry
@frappe.whitelist()
def crm_reports(date_from=None, date_to=None, customer=None):
    """The curated registry, with each entry's resolved filters."""
    _guard()
    ctx = _context(date_from, date_to, customer)
    out = []
    for entry in REPORTS:
        out.append({
            "key": entry["key"],
            "report": entry["report"],
            "group": entry["group"],
            "label": entry["label"],
            "blurb": entry["blurb"],
            "date_scoped": entry["date_scoped"],
            "editable": list(entry["editable"]),
            "filters": _resolve(entry["filters"], ctx),
            "permitted": _permitted(entry["report"]),
            "desk_url": _desk_url(entry["report"]),
        })
    return {
        "groups": [{"key": k, "label": l, "blurb": b} for k, l, b in GROUPS],
        "reports": out,
    }


def _permitted(report):
    """Can this user run this report at all?"""
    try:
        if not frappe.db.exists("Report", report):
            return False
        ref = frappe.db.get_value("Report", report, "ref_doctype")
        if ref and not frappe.has_permission(ref, "report"):
            return False
        return frappe.has_permission("Report", "read", report)
    except Exception:
        return False


def _desk_url(report):
    return "/app/query-report/" + frappe.utils.quoted(report)


# ---------------------------------------------------------------- run
@frappe.whitelist()
def crm_report_run(key=None, report=None, filters=None, date_from=None, date_to=None,
                   customer=None):
    """Run one report and return its columns, rows, chart and summary.

    A failure comes back as `{"error": ...}` for that report rather than raising,
    so one broken report cannot blank a whole tab. Permission failures are the
    exception: those propagate, because a silent empty table would look like
    "no data" rather than "not allowed".
    """
    _guard()
    ctx = _context(date_from, date_to, customer)
    entry = BY_KEY.get(key) if key else None

    if entry:
        name = entry["report"]
        merged = _resolve(entry["filters"], ctx)
        # Only filters the entry declares as editable may be overridden, so a
        # crafted request cannot inject an arbitrary filter into the report's SQL.
        incoming = _load(filters) or {}
        if isinstance(incoming, dict):
            for field in entry["editable"]:
                if field in incoming:
                    merged[field] = incoming[field]
    else:
        # Catalogue path: any report this user may genuinely see, run bare.
        name = report
        if not name or not frappe.db.exists("Report", name):
            frappe.throw(_("Unknown report"), frappe.DoesNotExistError)
        if not _permitted(name):
            frappe.throw(_("Not permitted to run {0}").format(name), frappe.PermissionError)
        merged = _load(filters) if isinstance(_load(filters), dict) else {}

    if not _permitted(name):
        frappe.throw(_("Not permitted to run {0}").format(name), frappe.PermissionError)

    from frappe.desk.query_report import run as run_report

    try:
        # No ignore_permissions: the runner's own checks are the point here.
        result = run_report(name, filters=json.dumps(merged), ignore_prepared_report=True)
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"crm_report_run failed: {name}")
        return {"report": name, "filters": merged, "error": str(e)[:300],
                "desk_url": _desk_url(name)}

    rows = _rows(result.get("result"), result.get("columns"))
    total = len(rows)
    return {
        "report": name,
        "filters": merged,
        "columns": _columns(result.get("columns")),
        "rows": rows[:ROW_CAP],
        "total_rows": total,
        "truncated": total > ROW_CAP,
        "row_cap": ROW_CAP,
        "chart": result.get("chart"),
        "summary": result.get("report_summary"),
        "message": result.get("message"),
        "execution_time": result.get("execution_time"),
        "desk_url": _desk_url(name),
    }


def _columns(columns):
    """Normalise Frappe's two column shapes into one.

    Older reports return `"Label:Currency/Company:120"` strings; newer ones return
    dicts. The frontend should not have to know the difference.
    """
    out = []
    for col in columns or []:
        if isinstance(col, dict):
            out.append({
                "fieldname": col.get("fieldname") or col.get("label"),
                "label": col.get("label") or col.get("fieldname"),
                "fieldtype": col.get("fieldtype") or "Data",
                "options": col.get("options") or "",
                "width": col.get("width") or 0,
            })
            continue
        parts = str(col).split(":")
        label = parts[0] if parts else str(col)
        fieldtype, options = "Data", ""
        if len(parts) > 1 and parts[1]:
            ft = parts[1]
            if "/" in ft:
                fieldtype, options = ft.split("/", 1)
            else:
                fieldtype = ft
        out.append({"fieldname": frappe.scrub(label), "label": label,
                    "fieldtype": fieldtype, "options": options, "width": 0})
    return out


def _rows(result, columns):
    """Rows as dicts keyed by fieldname, whichever shape the report returned."""
    cols = _columns(columns)
    names = [c["fieldname"] for c in cols]
    out = []
    for row in result or []:
        if isinstance(row, dict):
            out.append({k: v for k, v in row.items() if not str(k).startswith("_")})
        elif isinstance(row, (list, tuple)):
            out.append({names[i]: v for i, v in enumerate(row) if i < len(names)})
    return out


# ---------------------------------------------------------------- catalogue
@frappe.whitelist()
def crm_report_catalogue():
    """Every CRM/Selling report this user may see.

    `runnable` is True when the CRM can execute it here — either it is in the
    registry, or it declares no filters at all. The rest carry a desk link, which
    is the honest answer: their required filters live in client-side JS the server
    cannot introspect.
    """
    _guard()
    try:
        rows = frappe.get_all(
            "Report",
            filters={"module": ["in", list(CATALOGUE_MODULES)], "disabled": 0},
            fields=["name", "report_type", "ref_doctype", "module", "is_standard"],
            order_by="module asc, name asc",
        )
    except Exception:
        return {"reports": []}

    group_by_name = {e["report"]: e["group"] for e in REPORTS}
    out = []
    for row in rows:
        if not _permitted(row.name):
            continue
        registered = row.name in REGISTERED_NAMES
        out.append({
            "report": row.name,
            "module": row.module,
            "type": row.report_type,
            "ref_doctype": row.ref_doctype,
            "custom": row.is_standard == "No",
            "registered": registered,
            "group": group_by_name.get(row.name) or "",
            "runnable": registered or row.name in FILTERLESS,
            "desk_url": _desk_url(row.name),
        })
    return {"reports": out}


# Reports measured to run with no filters at all, so the catalogue can execute
# them even though they are not curated.
FILTERLESS = {
    "Address And Contacts",
    "Available Stock for Packing Items",
    "CRM Conversion",
    "Customers Without Any Sales Transactions",
    "First Response Time for Opportunity",
    "Lead Details",
    "Lead Owner Efficiency",
    "Lost Opportunity",
    "Payment Terms Status for Sales Order",
    "Pending SO Items For Purchase Request",
    "Prospects Engaged But Not Converted",
    "Sales Order Analysis",
    "Territory-wise Sales",
}
