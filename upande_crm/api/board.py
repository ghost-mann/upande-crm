"""The pipeline board: every open prospect, where it stands, and what moves it.

Columns, left to right: open leads (with their qualification), one column per
configured opportunity stage (Settings → Opportunity Stages), and the customers
confirmed in the date range. Open opportunities sitting in a stage the settings
no longer list are shown in an "Other stages" column rather than dropped — an
unlisted stage is a configuration change, not a lost deal.

Moves are the two edits a sales manager makes from here: an opportunity's stage,
and a lead's qualification. Both check write permission on that record.
"""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, nowdate

from upande_crm.api.crm import _guard, _has, _hascol, _range
from upande_crm.modules import requires_module

CARD_LIMIT = 60
QUALIFICATION = ("Unqualified", "In Process", "Qualified")


def _stages():
    from upande_crm.api.settings import DEFAULTS, get_settings, parse_lines

    return parse_lines(get_settings().get("opportunity_stages")) or parse_lines(DEFAULTS["opportunity_stages"])


def ensure_pipeline_records(settings=None):
    """Create any configured opportunity stage or lead channel that does not
    exist yet. Runs when Settings are saved and on install/migrate — a site where
    nobody ever saved Settings still needs the default stages, or moving a card
    to one fails its Link check. Never deletes: a stage still used by old
    opportunities must survive being unlisted."""
    from upande_crm.api.settings import DEFAULTS, get_settings, parse_lines

    s = settings if settings is not None else get_settings()
    for field, doctype, key in (("opportunity_stages", "Sales Stage", "stage_name"),
                                ("lead_channels", "UTM Source", "name")):
        if not frappe.db.exists("DocType", doctype):
            continue
        for value in parse_lines(s.get(field) or DEFAULTS[field]):
            if frappe.db.exists(doctype, value):
                continue
            if key == "name":  # UTM Source is prompt-named
                frappe.new_doc(doctype).insert(ignore_permissions=True, set_name=value)
            else:
                frappe.get_doc({"doctype": doctype, key: value}).insert(ignore_permissions=True)


def lead_source_sql(alias=""):
    """SQL for a lead's channel: v16's `utm_source`, falling back to the v15
    `source` column restored sites still carry, so old and new leads both count."""
    p = f"{alias}." if alias else ""
    parts = [f"nullif({p}`{c}`, '')" for c in ("utm_source", "source") if _hascol("Lead", c)]
    return f"coalesce({', '.join(parts)}, 'Unknown')" if parts else "'Unknown'"


def _lead_cards():
    from upande_crm.api.settings import open_statuses

    statuses = open_statuses("lead_open_statuses")
    # get_list applies the caller's record-level permissions (User Permissions,
    # permission query conditions); the columns it cannot express are read after.
    permitted = frappe.get_list("Lead", filters={"status": ["in", statuses]}, pluck="name",
                                order_by="creation desc", limit_page_length=0)
    total = len(permitted)
    names = permitted[:CARD_LIMIT]
    rows = frappe.db.sql(
        f"""select name, lead_name, company_name, qualification_status, {lead_source_sql()} as source,
                   creation, lead_owner, status
            from `tabLead` where name in %(names)s order by creation desc""",
        {"names": tuple(names)}, as_dict=True) if names else []
    today = nowdate()
    return total, [{
        "doctype": "Lead", "name": r.name, "title": r.company_name or r.lead_name or r.name,
        "subtitle": r.lead_name if r.company_name else None, "qualification": r.qualification_status,
        "source": r.source, "owner": r.lead_owner, "age_days": date_diff(today, r.creation), "status": r.status,
    } for r in rows]


def _opportunity_cards(stages):
    from upande_crm.api.settings import open_statuses

    statuses = tuple(open_statuses("opportunity_open_statuses"))
    amount = "opportunity_amount" if _hascol("Opportunity", "opportunity_amount") else "0"
    # Column totals add base amounts: opportunities here are in several currencies.
    base = "base_opportunity_amount" if _hascol("Opportunity", "base_opportunity_amount") else amount
    from upande_crm.api.visits import readable_parties

    permitted = frappe.get_list("Opportunity", filters={"status": ["in", list(statuses)]}, pluck="name",
                                limit_page_length=0)
    rows = frappe.db.sql(
        f"""select name, party_name, customer_name, opportunity_from, sales_stage, {amount} as amount,
                   {base} as base_amount,
                   probability, expected_closing, creation, opportunity_owner, status, currency
            from `tabOpportunity` where name in %(names)s order by creation desc""",
        {"names": tuple(permitted)}, as_dict=True) if permitted else []
    # party_name is a Dynamic Link, which User Permissions skip.
    rows = readable_parties(rows, "opportunity_from", "party_name")
    today = nowdate()
    by_stage = {s: [] for s in stages}
    other = []
    for r in rows:
        card = {"doctype": "Opportunity", "name": r.name, "title": r.customer_name or r.party_name or r.name,
                "party_type": r.opportunity_from, "party": r.party_name, "stage": r.sales_stage or "",
                "amount": flt(r.amount), "base_amount": flt(r.base_amount), "currency": r.currency,
                "probability": cint(r.probability),
                "expected_closing": str(r.expected_closing) if r.expected_closing else None,
                "owner": r.opportunity_owner, "age_days": date_diff(today, r.creation), "status": r.status}
        (by_stage[r.sales_stage] if r.sales_stage in by_stage else other).append(card)
    return by_stage, other


def _customer_cards(frm, to):
    rows = frappe.get_list("Customer", filters={"creation": ["between", [f"{frm} 00:00:00", f"{to} 23:59:59"]]},
                          fields=["name", "customer_name", "customer_group", "territory", "creation"],
                          order_by="creation desc", limit=CARD_LIMIT)
    total = len(frappe.get_list("Customer", filters={"creation": ["between", [f"{frm} 00:00:00", f"{to} 23:59:59"]]},
                                pluck="name", limit_page_length=0))
    return total, [{"doctype": "Customer", "name": r.name, "title": r.customer_name or r.name,
                    "subtitle": " · ".join(x for x in (r.customer_group, r.territory) if x),
                    "created": str(r.creation)[:10]} for r in rows]


@frappe.whitelist()
@requires_module("opps")
def crm_pipeline_board(date_from=None, date_to=None):
    _guard()
    frm, to = _range(date_from, date_to)
    stages = _stages()
    columns = []
    if _has("Lead") and frappe.has_permission("Lead", "read"):
        total, cards = _lead_cards()
        columns.append({"key": "leads", "label": "Leads", "kind": "lead", "count": total, "cards": cards})
    if _has("Opportunity") and frappe.has_permission("Opportunity", "read"):
        by_stage, other = _opportunity_cards(stages)
        for s in stages:
            cards = by_stage[s]
            columns.append({"key": s, "label": s, "kind": "opportunity", "count": len(cards), "cards": cards[:CARD_LIMIT],
                            "value": sum(c["base_amount"] for c in cards)})
        if other:
            columns.append({"key": "other", "label": "Other stages", "kind": "opportunity", "count": len(other),
                            "cards": other[:CARD_LIMIT], "value": sum(c["base_amount"] for c in other),
                            "note": "Open opportunities in a stage not listed in CRM Settings."})
    if frappe.has_permission("Customer", "read"):
        total, cards = _customer_cards(frm, to)
        columns.append({"key": "customers", "label": "Confirmed customers", "kind": "customer",
                        "count": total, "cards": cards, "note": "Created in the selected range."})
    from upande_crm.api.crm import _company_currency

    return {"columns": columns, "stages": stages, "qualification": list(QUALIFICATION),
            "currency": _company_currency(),
            "range": {"from": frm, "to": to}}


@frappe.whitelist(methods=["POST"])
@requires_module("opps")
def crm_opportunity_set_stage(name, stage):
    _guard()
    stages = _stages()
    if stage not in stages:
        frappe.throw(_("{0} is not a pipeline stage. Choose from: {1}.").format(stage, ", ".join(stages)),
                     frappe.ValidationError)
    if not frappe.has_permission("Opportunity", "write", name):
        frappe.throw(_("Not permitted to change this opportunity"), frappe.PermissionError)
    doc = frappe.get_doc("Opportunity", name)
    doc.sales_stage = stage
    doc.save()
    return {"name": doc.name, "sales_stage": doc.sales_stage}


def apply_qualification(doc, status):
    """Set a lead's qualification, recording who qualified it and when."""
    if status not in QUALIFICATION:
        frappe.throw(_("Qualification must be one of: {0}.").format(", ".join(QUALIFICATION)),
                     frappe.ValidationError)
    doc.qualification_status = status
    if status == "Qualified":
        if not doc.get("qualified_by"):
            doc.qualified_by = frappe.session.user
        if not doc.get("qualified_on"):
            doc.qualified_on = nowdate()
    else:
        doc.qualified_by = None
        doc.qualified_on = None


@frappe.whitelist(methods=["POST"])
@requires_module("leads")
def crm_lead_qualify(name, status):
    _guard()
    if not frappe.has_permission("Lead", "write", name):
        frappe.throw(_("Not permitted to change this lead"), frappe.PermissionError)
    doc = frappe.get_doc("Lead", name)
    apply_qualification(doc, status)
    doc.save()
    return {"name": doc.name, "qualification_status": doc.qualification_status}
