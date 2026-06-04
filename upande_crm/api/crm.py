"""Whitelisted CRM dashboard endpoints backing the /crm React section.

Each `crm_dashboard_*` method returns plain dicts/lists in the exact shape the
frontend expects (see frontend/crm/src/sections/*). Everything is defensive: a
missing doctype or column degrades to zero/empty rather than raising, so the
dashboard renders on any ERPNext/CRM install. An optional `customer` arg scopes
the customer-linked views.

Access: gated to the same sales/CRM roles as the /crm page.
"""

import json

import frappe
from frappe.utils import add_days, add_months, getdate, nowdate, flt, get_quarter_start, now_datetime

CRM_ROLES = {"System Manager", "Sales Manager", "Sales User", "CRM Manager", "CRM User"}


# ---------------------------------------------------------------- session
@frappe.whitelist()
def get_csrf_token() -> dict:
    """Return a fresh CSRF token for the current session. GET-safe.
    Called by the React app to recover from stale tokens after the page has
    been open long enough that the boot-injected token has rotated."""
    return {"csrf_token": frappe.sessions.get_csrf_token()}


# ---------------------------------------------------------------- helpers
def _guard():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)
    if not (set(frappe.get_roles(frappe.session.user)) & CRM_ROLES):
        frappe.throw("Not permitted", frappe.PermissionError)


def _has(doctype):
    try:
        return bool(frappe.db.exists("DocType", doctype))
    except Exception:
        return False


def _hascol(doctype, col):
    try:
        return col in frappe.db.get_table_columns(doctype)
    except Exception:
        return False


def _count(doctype, filters=None):
    try:
        return frappe.db.count(doctype, filters or {})
    except Exception:
        return 0


def _range(date_from, date_to):
    to = getdate(date_to) if date_to else getdate(nowdate())
    frm = getdate(date_from) if date_from else add_days(to, -30)
    return str(frm), str(to)


def _df(doctype, field, frm, to):
    """filters-dict fragment scoping `field` to [frm, to]; {} if the column is absent
    (so it degrades to an unfiltered count instead of raising)."""
    return {field: ["between", [frm, to]]} if _hascol(doctype, field) else {}


def _dw(doctype, field, frm, to, base=""):
    """SQL WHERE clause scoping `field` to [frm, to], AND-merged with `base`.
    frm/to are validated YYYY-MM-DD dates (from _range), safe to inline."""
    parts = []
    if base:
        parts.append(f"({base})")
    if _hascol(doctype, field):
        parts.append(f"`{field}` between '{frm}' and '{to}'")
    return ("where " + " and ".join(parts)) if parts else ""


def _group(doctype, field, where_sql="", limit=8):
    """Top-N value counts for a field → [{label, count}]."""
    if not _has(doctype) or not _hascol(doctype, field):
        return []
    try:
        rows = frappe.db.sql(
            f"""select coalesce(nullif(`{field}`, ''), 'Unknown') as label, count(*) as count
                from `tab{doctype}` {where_sql}
                group by label order by count desc limit {int(limit)}""",
            as_dict=True,
        )
        return [{"label": r.label, "count": r.count} for r in rows]
    except Exception:
        return []


def _month_trend(doctype, datefield, months=12):
    if not _has(doctype) or not _hascol(doctype, datefield):
        return []
    start = str(add_months(getdate(nowdate()), -(months - 1)).replace(day=1))
    try:
        rows = frappe.db.sql(
            f"""select date_format(`{datefield}`, '%%Y-%%m') as month, count(*) as count
                from `tab{doctype}` where `{datefield}` >= %s
                group by month order by month""",
            (start,), as_dict=True,
        )
        return [{"month": r.month, "count": r.count} for r in rows]
    except Exception:
        return []


def _rows(doctype, fields, filters=None, order_by="creation desc", limit=500):
    """Safe get_all that drops fields/filters the schema doesn't have."""
    if not _has(doctype):
        return []
    cols = set(frappe.db.get_table_columns(doctype))
    fields = [f for f in fields if f in cols or f == "name"]
    filters = {k: v for k, v in (filters or {}).items() if k in cols}
    try:
        return frappe.get_all(doctype, fields=fields, filters=filters, order_by=order_by, limit=limit)
    except Exception:
        return []


# ---------------------------------------------------------------- overview
@frappe.whitelist()
def crm_dashboard_overview(date_from=None, date_to=None, customer=None):
    _guard()
    frm, to = _range(date_from, date_to)

    # Date-scoped filter fragments per doctype (their natural date field).
    ld = _df("Lead", "creation", frm, to)
    od = _df("Opportunity", "transaction_date", frm, to)
    pd = _df("Prospect", "creation", frm, to)
    cd = _df("Customer", "creation", frm, to)
    td = _df("ToDo", "creation", frm, to)

    leads_total = _count("Lead", ld)
    leads_conv = _count("Lead", {**ld, "status": "Converted"})
    leads_open = _count("Lead", {**ld, "status": ["in", ["Lead", "Open", "Replied", "Interested"]]})
    conv_rate = round((leads_conv / leads_total * 100), 1) if leads_total else 0

    opps_total = _count("Opportunity", od)
    opps_open = _count("Opportunity", {**od, "status": ["in", ["Open", "Quotation", "Replied"]]})
    opps_won = _count("Opportunity", {**od, "status": "Converted"})

    prosp_total = _count("Prospect", pd)
    prosp_terr = _distinct_count("Prospect", "territory", _dw("Prospect", "creation", frm, to))

    cust_active = _count("Customer", {**cd, "disabled": 0})
    cust_companies = _count("Customer", {**cd, "customer_type": "Company", "disabled": 0})

    rev_usd, rev_orders = _so_revenue(frm, to, customer)

    tasks_open = _count("ToDo", {**td, "status": "Open"})
    tasks_high = _count("ToDo", {**td, "status": "Open", "priority": "High"})

    return {
        "kpis": {
            "leads": {"total": leads_total, "open": leads_open, "conv_rate": conv_rate},
            "opps": {"total": opps_total, "open": opps_open, "won": opps_won},
            "prosp": {"total": prosp_total, "territories": prosp_terr},
            "cust": {"active": cust_active, "companies": cust_companies},
            "revenue_30d": {"usd": rev_usd, "orders": rev_orders},
            "tasks": {"open": tasks_open, "high": tasks_high},
        },
        "funnel": [
            {"label": "Leads", "count": leads_total},
            {"label": "Opportunities", "count": opps_total},
            {"label": "Quotations", "count": _count("Quotation", _df("Quotation", "transaction_date", frm, to)) if _has("Quotation") else 0},
            {"label": "Sales Orders", "count": _count("Sales Order", {**_df("Sales Order", "transaction_date", frm, to), "docstatus": 1})},
            {"label": "Converted", "count": opps_won},
        ],
        "lead_status": _group("Lead", "status", _dw("Lead", "creation", frm, to)),
        # Labeled "Last 12 / 6 months" in the UI — intentionally rolling history,
        # independent of the date-range picker.
        "lead_trend": _month_trend("Lead", "creation", 12),
        "so_trend": _month_trend("Sales Order", "transaction_date", 6),
        "top_sources": _group("Lead", "source", _dw("Lead", "creation", frm, to)),
        "top_territories": _group("Lead", "territory", _dw("Lead", "creation", frm, to)),
        "sales_stages": _group("Opportunity", "sales_stage", _dw("Opportunity", "transaction_date", frm, to)),
    }


def _distinct_count(doctype, field, where_sql=""):
    if not _has(doctype) or not _hascol(doctype, field):
        return 0
    try:
        return frappe.db.sql(
            f"select count(distinct nullif(`{field}`,'')) from `tab{doctype}` {where_sql}"
        )[0][0] or 0
    except Exception:
        return 0


def _so_revenue(frm, to, customer=None):
    if not _has("Sales Order"):
        return 0, 0
    cond, params = "docstatus=1 and transaction_date between %s and %s", [frm, to]
    if customer:
        cond += " and customer=%s"
        params.append(customer)
    try:
        r = frappe.db.sql(
            f"select coalesce(sum(base_grand_total),0), count(*) from `tabSales Order` where {cond}",
            params,
        )[0]
        return flt(r[0]), int(r[1])
    except Exception:
        return 0, 0


# ---------------------------------------------------------------- leads
@frappe.whitelist()
def crm_dashboard_leads(date_from=None, date_to=None, customer=None):
    _guard()
    frm, to = _range(date_from, date_to)
    d = _df("Lead", "creation", frm, to)
    w = _dw("Lead", "creation", frm, to)
    total = _count("Lead", d)
    converted = _count("Lead", {**d, "status": "Converted"})
    return {
        "kpis": {
            "total": total,
            "open": _count("Lead", {**d, "status": ["in", ["Lead", "Open", "Replied", "Interested"]]}),
            "to_opp": _count("Lead", {**d, "status": "Opportunity"}),
            "to_quot": _count("Lead", {**d, "status": "Quotation"}),
            "converted": converted,
            "conv_rate": round(converted / total * 100, 1) if total else 0,
        },
        "status_mix": _group("Lead", "status", w),
        "qual_mix": _group("Lead", "qualification_status", w),
        "owner_workload": _group("Lead", "lead_owner", w),
        "geography": _group("Lead", "territory", w),
        "rows": _rows("Lead", [
            "name", "lead_name", "company_name", "status", "qualification_status",
            "territory", "source", "lead_owner", "owner", "_assign", "creation",
        ], filters=d),
    }


# ---------------------------------------------------------------- opportunities
@frappe.whitelist()
def crm_dashboard_opportunities(date_from=None, date_to=None, customer=None):
    _guard()
    frm, to = _range(date_from, date_to)
    d = _df("Opportunity", "transaction_date", frm, to)
    w = _dw("Opportunity", "transaction_date", frm, to)
    total = _count("Opportunity", d)
    won = _count("Opportunity", {**d, "status": "Converted"})
    lost = _count("Opportunity", {**d, "status": "Lost"})
    filters = {**d, "party_name": customer} if customer else d
    return {
        "kpis": {
            "total": total,
            "open": _count("Opportunity", {**d, "status": ["in", ["Open", "Quotation", "Replied"]]}),
            "converted": won,
            "lost": lost,
            "win_rate": round(won / (won + lost) * 100, 1) if (won + lost) else 0,
            "from_prospect": _count("Opportunity", {**d, "opportunity_from": "Prospect"}),
        },
        "pipeline": _group("Opportunity", "sales_stage", w, limit=12),
        "status_mix": _group("Opportunity", "status", w),
        "territory_mix": _group("Opportunity", "territory", w),
        "rows": _rows("Opportunity", [
            "name", "customer_name", "party_name", "opportunity_from", "status",
            "sales_stage", "probability", "territory", "source",
            "opportunity_owner", "owner", "_assign", "transaction_date", "creation",
        ], filters=filters),
    }


# ---------------------------------------------------------------- prospects
@frappe.whitelist()
def crm_dashboard_prospects(date_from=None, date_to=None, customer=None):
    _guard()
    frm, to = _range(date_from, date_to)
    d = _df("Prospect", "creation", frm, to)
    w = _dw("Prospect", "creation", frm, to)
    total = _count("Prospect", d)
    qstart = str(get_quarter_start(nowdate())) if _has("Prospect") else None
    this_q = 0
    if qstart and _has("Prospect"):
        this_q = _count("Prospect", {"creation": [">=", qstart]})
    return {
        "kpis": {
            "total": total,
            "with_opp": _distinct_count_link("Opportunity", "party_name", "opportunity_from", "Prospect"),
            "to_customer": 0,
            "conv_rate": 0,
            "territories": _distinct_count("Prospect", "territory", w),
            "this_quarter": this_q,
        },
        "territory_mix": _group("Prospect", "territory", w),
        "size_mix": _group("Prospect", "no_of_employees", w),
        "industry_mix": _group("Prospect", "industry", w),
        "rows": _rows("Prospect", [
            "name", "company_name", "industry", "territory", "no_of_employees",
            "owner", "_assign", "creation",
        ], filters=d),
    }


def _distinct_count_link(doctype, field, type_field, type_value):
    if not _has(doctype) or not _hascol(doctype, field):
        return 0
    try:
        cond = ""
        if _hascol(doctype, type_field):
            cond = f" where `{type_field}`=%s"
            return frappe.db.sql(
                f"select count(distinct `{field}`) from `tab{doctype}`{cond}", (type_value,)
            )[0][0] or 0
        return frappe.db.sql(f"select count(distinct `{field}`) from `tab{doctype}`")[0][0] or 0
    except Exception:
        return 0


# ---------------------------------------------------------------- customers
@frappe.whitelist()
def crm_dashboard_customers(date_from=None, date_to=None, customer=None):
    _guard()
    frm, to = _range(date_from, date_to)
    d = _df("Customer", "creation", frm, to)
    cust_filter = _dw("Customer", "creation", frm, to, base="disabled=0")
    trend = []
    if _has("Sales Order"):
        cond, params = "docstatus=1 and transaction_date between %s and %s", [frm, to]
        if customer:
            cond += " and customer=%s"; params.append(customer)
        try:
            rows = frappe.db.sql(
                f"""select transaction_date as date, count(*) as count,
                          coalesce(sum(base_grand_total),0) as revenue
                   from `tabSales Order` where {cond}
                   group by transaction_date order by transaction_date""",
                params, as_dict=True,
            )
            trend = [{"date": str(r.date), "count": r.count, "revenue": flt(r.revenue)} for r in rows]
        except Exception:
            trend = []

    return {
        "kpis": {
            "total": _count("Customer", d),
            "active": _count("Customer", {**d, "disabled": 0}),
            "disabled": _count("Customer", {**d, "disabled": 1}),
            "companies": _count("Customer", {**d, "customer_type": "Company", "disabled": 0}),
            "individuals": _count("Customer", {**d, "customer_type": "Individual", "disabled": 0}),
            "new_30d": _count("Customer", {"creation": [">=", str(add_days(getdate(nowdate()), -30))]}),
        },
        "type_mix": _group("Customer", "customer_type", cust_filter),
        "territory_mix": _group("Customer", "territory", cust_filter),
        # Labeled "Last 12 months" in the UI — rolling history, independent of the picker.
        "acquisition_trend": _month_trend("Customer", "creation", 12),
        "sales_order_trend": trend,
        "top_revenue": _top_customers(frm, to),
        "rows": _rows("Customer", [
            "name", "customer_name", "customer_type", "customer_group",
            "territory", "disabled", "account_manager", "owner", "_assign", "creation",
        ], filters=({**d, "name": customer} if customer else d)),
    }


def _top_customers(frm, to, limit=20):
    src = "Sales Invoice" if _has("Sales Invoice") else ("Sales Order" if _has("Sales Order") else None)
    if not src:
        return []
    try:
        rows = frappe.db.sql(
            f"""select customer, coalesce(sum(base_grand_total),0) as usd
                from `tab{src}` where docstatus=1 and posting_date between %s and %s
                group by customer order by usd desc limit {int(limit)}""",
            (frm, to), as_dict=True,
        ) if src == "Sales Invoice" else frappe.db.sql(
            f"""select customer, coalesce(sum(base_grand_total),0) as usd
                from `tab{src}` where docstatus=1 and transaction_date between %s and %s
                group by customer order by usd desc limit {int(limit)}""",
            (frm, to), as_dict=True,
        )
        return [{"customer": r.customer, "usd": flt(r.usd)} for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------- events / tasks / emails
@frappe.whitelist()
def crm_dashboard_events_tasks(date_from=None, date_to=None, customer=None):
    _guard()
    frm, to = _range(date_from, date_to)
    ev = _df("Event", "starts_on", frm, to)
    tdo = _df("ToDo", "creation", frm, to)
    cm = _df("Communication", "communication_date", frm, to)
    emails = _rows("Communication", [
        "name", "subject", "sender", "recipients", "communication_date",
        "sent_or_received", "reference_doctype", "reference_name", "status", "_user_tags",
    ], filters={**cm, "communication_type": "Communication"}, order_by="communication_date desc", limit=300)
    sent = sum(1 for e in emails if e.get("sent_or_received") == "Sent")
    recv = sum(1 for e in emails if e.get("sent_or_received") == "Received")
    return {
        "kpis": {
            "events_total": _count("Event", ev),
            "events_open": _count("Event", {**ev, "status": "Open"}),
            "tasks_open": _count("ToDo", {**tdo, "status": "Open"}),
            "tasks_high": _count("ToDo", {**tdo, "status": "Open", "priority": "High"}),
            "emails_sent": sent,
            "emails_recv": recv,
        },
        "event_categories": _group("Event", "event_category", _dw("Event", "starts_on", frm, to)),
        "task_priorities": _group("ToDo", "priority", _dw("ToDo", "creation", frm, to, base="status='Open'")),
        "email_by_ref": _group("Communication", "reference_doctype",
                               _dw("Communication", "communication_date", frm, to, base="communication_type='Communication'")),
        "events": _rows("Event", ["name", "subject", "event_category", "starts_on", "status", "owner", "_assign"],
                        filters=ev, order_by="starts_on desc", limit=300),
        "todos": _rows("ToDo", ["name", "description", "priority", "allocated_to", "owner", "_assign", "status",
                                "reference_type", "reference_name"],
                       filters={**tdo, "status": "Open"}, order_by="creation desc", limit=300),
        "emails": emails,
    }


# ---------------------------------------------------------------- activity log
@frappe.whitelist()
def crm_dashboard_activity(date_from=None, date_to=None, customer=None):
    _guard()
    frm, to = _range(date_from, date_to)
    dt = "CRM Activity Log" if _has("CRM Activity Log") else None
    if not dt:
        # Fall back to Communications as an activity stream.
        cm = _df("Communication", "communication_date", frm, to)
        rows = _rows("Communication", ["name", "subject", "communication_type", "communication_date",
                                       "reference_doctype", "reference_name", "sender"],
                     filters=cm, order_by="communication_date desc", limit=200)
        return {"kpis": {"total": len(rows), "today": 0, "sent": 0, "failed": 0, "skipped": 0},
                "by_type": _group("Communication", "communication_type",
                                  _dw("Communication", "communication_date", frm, to)), "rows": rows}

    d = _df(dt, "activity_date", frm, to)
    w = _dw(dt, "activity_date", frm, to)
    rows = _rows(dt, ["name", "activity_date", "activity_type", "subject", "reference_doctype",
                      "reference_name", "customer", "email_status", "triggered_by"],
                 filters=({**d, "customer": customer} if customer else d),
                 order_by="activity_date desc", limit=500)
    today = str(getdate(nowdate()))
    return {
        "kpis": {
            "total": _count(dt, d),
            "today": _count(dt, {"activity_date": [">=", today]}) if _hascol(dt, "activity_date") else 0,
            "sent": _count(dt, {**d, "email_status": "Sent"}) if _hascol(dt, "email_status") else 0,
            "failed": _count(dt, {**d, "email_status": "Failed"}) if _hascol(dt, "email_status") else 0,
            "skipped": _count(dt, {**d, "email_status": "Skipped"}) if _hascol(dt, "email_status") else 0,
        },
        "by_type": _group(dt, "activity_type", w),
        "rows": rows,
    }


# ---------------------------------------------------------------- mail
_FOLDER_REF = {"crm_leads": "Lead", "crm_opps": "Opportunity",
               "crm_customers": "Customer", "crm_quotations": "Quotation"}


@frappe.whitelist()
def crm_mail_data(folder="inbox", tab="all", search="", limit=100, offset=0):
    _guard()
    limit, offset = int(limit), int(offset)
    base = "communication_type='Communication'"

    def _cnt(where):
        try:
            return frappe.db.sql(f"select count(*) from `tabCommunication` where {where}")[0][0] or 0
        except Exception:
            return 0

    counts = {
        "inbox": _cnt(f"{base} and sent_or_received='Received'"),
        "inbox_unread": _cnt(f"{base} and sent_or_received='Received' and status='Open' and coalesce(seen,0)=0"),
        "sent_ok": _cnt(f"{base} and sent_or_received='Sent'"),
        "crm_leads": _cnt(f"{base} and reference_doctype='Lead'"),
        "crm_opps": _cnt(f"{base} and reference_doctype='Opportunity'"),
        "crm_customers": _cnt(f"{base} and reference_doctype='Customer'"),
        "crm_quotations": _cnt(f"{base} and reference_doctype='Quotation'"),
    }

    conds = [base]
    params = []
    if folder == "inbox":
        conds.append("sent_or_received='Received'")
    elif folder == "sent":
        conds.append("sent_or_received='Sent'")
    elif folder in _FOLDER_REF:
        conds.append("reference_doctype=%s"); params.append(_FOLDER_REF[folder])
    if tab == "unread":
        conds.append("status='Open' and sent_or_received='Received' and coalesce(seen,0)=0")
    if search:
        conds.append("(subject like %s or sender like %s or recipients like %s)")
        like = f"%{search}%"; params += [like, like, like]

    where = " and ".join(conds)
    rows = []
    try:
        rows = frappe.db.sql(
            f"""select name, subject, sender, recipients, cc, communication_date, sent_or_received,
                       reference_doctype, reference_name, status, seen, _user_tags, content
                from `tabCommunication` where {where}
                order by communication_date desc limit {limit} offset {offset}""",
            params, as_dict=True,
        )
    except Exception:
        rows = []

    for r in rows:
        direction = r.get("sent_or_received") or "Received"
        r["direction"] = direction
        cp = (r.get("recipients") if direction == "Sent" else r.get("sender")) or ""
        r["counterparty"] = cp
        r["display_name"] = _name_from_addr(cp)
        r["unread"] = 1 if (direction == "Received" and r.get("status") == "Open" and not r.get("seen")) else 0
        # trim heavy html for the list
        r["content"] = (r.get("content") or "")

    return {"counts": counts, "rows": rows}


def _name_from_addr(a):
    if not a:
        return ""
    a = a.split(",")[0].strip()
    if "<" in a:
        a = a.split("<")[0].strip().strip('"')
    if a and "@" not in a:
        return a
    return a.split("@")[0] if "@" in a else a


# ---------------------------------------------------------------- search
@frappe.whitelist()
def crm_search(query=""):
    _guard()
    query = (query or "").strip()
    if len(query) < 2:
        return {"results": []}
    like = f"%{query}%"
    out = []

    def add(doctype, label_field, icon, route_dt):
        if not _hascol(doctype, label_field):
            return
        try:
            res = frappe.db.sql(
                f"""select name, `{label_field}` as label from `tab{doctype}`
                    where name like %s or `{label_field}` like %s
                    order by modified desc limit 6""",
                (like, like), as_dict=True,
            )
        except Exception:
            res = []
        for r in res:
            out.append({"doctype": route_dt, "name": r.name, "label": r.get("label") or r.name, "icon": icon})

    if _has("Lead"): add("Lead", "lead_name", "person_add", "Lead")
    if _has("Opportunity"): add("Opportunity", "customer_name", "trending_up", "Opportunity")
    if _has("Customer"): add("Customer", "customer_name", "storefront", "Customer")
    return {"results": out}


# ---------------------------------------------------------------- compose
@frappe.whitelist()
def crm_send_email(recipients, subject="", content="", cc=None, bcc=None,
                   reference_doctype=None, reference_name=None, in_reply_to=None):
    _guard()
    if not recipients:
        frappe.throw("Recipients required")

    sender = frappe.session.user if frappe.session.user != "Guest" else None
    comm = frappe.get_doc({
        "doctype": "Communication",
        "communication_type": "Communication",
        "communication_medium": "Email",
        "sent_or_received": "Sent",
        "subject": subject or "(no subject)",
        "content": content or "",
        "sender": sender,
        "recipients": recipients,
        "cc": cc or None,
        "bcc": bcc or None,
        "communication_date": now_datetime(),
        "reference_doctype": reference_doctype or None,
        "reference_name": reference_name or None,
        # Thread a reply onto the message it answers.
        "in_reply_to": in_reply_to or None,
        # Sent-from-app messages are already "read".
        "seen": 1,
    })
    comm.insert(ignore_permissions=True)

    def _split(v):
        return [x.strip() for x in str(v or "").split(",") if x.strip()]

    try:
        frappe.sendmail(
            recipients=_split(recipients),
            cc=_split(cc) or None,
            bcc=_split(bcc) or None,
            subject=subject or "(no subject)",
            message=content or "",
            communication=comm.name,
        )
        status = "sent"
    except Exception as e:
        status = f"queued (mail not configured: {e})"
    return {"name": comm.name, "status": status}


@frappe.whitelist()
def crm_mark_read(name, seen=1):
    """Mark a Communication as read/unread (used when a thread is opened in the app)."""
    _guard()
    try:
        frappe.db.set_value("Communication", name, "seen", 1 if int(seen) else 0, update_modified=False)
        return {"name": name, "seen": 1 if int(seen) else 0}
    except Exception as e:
        return {"name": name, "error": str(e)}
