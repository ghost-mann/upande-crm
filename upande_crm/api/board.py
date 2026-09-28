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


def lead_source_sql(alias=""):
    """SQL for a lead's channel: v16's `utm_source`, falling back to the v15
    `source` column restored sites still carry, so old and new leads both count."""
    p = f"{alias}." if alias else ""
    parts = [f"nullif({p}`{c}`, '')" for c in ("utm_source", "source") if _hascol("Lead", c)]
    return f"coalesce({', '.join(parts)}, 'Unknown')" if parts else "'Unknown'"


def _lead_cards():
    from upande_crm.api.settings import open_statuses

    statuses = open_statuses("lead_open_statuses")
    where = "status in %(st)s"
    total = cint(frappe.db.sql(f"select count(*) from `tabLead` where {where}", {"st": tuple(statuses)})[0][0])
    rows = frappe.db.sql(
        f"""select name, lead_name, company_name, qualification_status, {lead_source_sql()} as source,
                   creation, lead_owner, status
            from `tabLead` where {where} order by creation desc limit %(n)s""",
        {"st": tuple(statuses), "n": CARD_LIMIT}, as_dict=True)
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
    rows = frappe.db.sql(
        f"""select name, party_name, customer_name, opportunity_from, sales_stage, {amount} as amount,
                   probability, expected_closing, creation, opportunity_owner, status, currency
            from `tabOpportunity` where status in %(st)s order by creation desc""",
        {"st": statuses}, as_dict=True)
    today = nowdate()
    by_stage = {s: [] for s in stages}
    other = []
    for r in rows:
        card = {"doctype": "Opportunity", "name": r.name, "title": r.customer_name or r.party_name or r.name,
                "party_type": r.opportunity_from, "party": r.party_name, "stage": r.sales_stage or "",
                "amount": flt(r.amount), "currency": r.currency, "probability": cint(r.probability),
                "expected_closing": str(r.expected_closing) if r.expected_closing else None,
                "owner": r.opportunity_owner, "age_days": date_diff(today, r.creation), "status": r.status}
        (by_stage[r.sales_stage] if r.sales_stage in by_stage else other).append(card)
    return by_stage, other


def _customer_cards(frm, to):
    rows = frappe.get_all("Customer", filters={"creation": ["between", [f"{frm} 00:00:00", f"{to} 23:59:59"]]},
                          fields=["name", "customer_name", "customer_group", "territory", "creation"],
                          order_by="creation desc", limit=CARD_LIMIT)
    total = frappe.db.count("Customer", {"creation": ["between", [f"{frm} 00:00:00", f"{to} 23:59:59"]]})
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
                            "value": sum(c["amount"] for c in cards)})
        if other:
            columns.append({"key": "other", "label": "Other stages", "kind": "opportunity", "count": len(other),
                            "cards": other[:CARD_LIMIT], "value": sum(c["amount"] for c in other),
                            "note": "Open opportunities in a stage not listed in CRM Settings."})
    if frappe.has_permission("Customer", "read"):
        total, cards = _customer_cards(frm, to)
        columns.append({"key": "customers", "label": "Confirmed customers", "kind": "customer",
                        "count": total, "cards": cards, "note": "Created in the selected range."})
    return {"columns": columns, "stages": stages, "qualification": list(QUALIFICATION),
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
