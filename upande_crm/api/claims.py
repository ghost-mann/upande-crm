"""Customer claims: log them, see what is overdue, and how fast they close.

Reads follow the rest of the CRM: they never raise past the role gate, and a
site without the doctype (not yet migrated) gets empty structures. Writes throw,
because a claim that silently did not save is worse than an error.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, nowdate

from upande_crm.api.crm import _company_currency, _guard, _has, _range
from upande_crm.modules import requires_module

DOCTYPE = "CRM Claim"
REFERENCE_KINDS = ("Sales Invoice", "Delivery Note", "Sales Order")
# Fields a client may set. Everything else (owner, docstatus, resolved_on) is
# the server's.
EDITABLE = {
    "customer", "claim_type", "status", "raised_on", "assigned_to", "reference_doctype",
    "reference_name", "item_code", "qty_affected", "amount_claimed", "amount_credited",
    "description", "root_cause", "resolution",
}
ROW_FIELDS = ["name", "customer", "claim_type", "status", "raised_on", "resolved_on", "assigned_to",
              "reference_doctype", "reference_name", "item_code", "qty_affected",
              "amount_claimed", "amount_credited"]


def _settings():
    from upande_crm.api.settings import DEFAULTS, get_settings, parse_lines

    s = get_settings()
    return {
        "types": parse_lines(s.get("claim_types")) or parse_lines(DEFAULTS["claim_types"]),
        "sla_days": cint(s.get("claim_sla_days")) or DEFAULTS["claim_sla_days"],
    }


def _available():
    return _has(DOCTYPE) and frappe.has_permission(DOCTYPE, "read")


def _decorate(rows, sla_days):
    today = nowdate()
    for r in rows:
        open_ = r.status not in ("Resolved", "Rejected")
        r["age_days"] = date_diff(r.resolved_on or today, r.raised_on) if r.raised_on else None
        r["overdue"] = bool(open_ and r["age_days"] is not None and r["age_days"] > sla_days)
        for k in ("raised_on", "resolved_on"):
            r[k] = str(r[k]) if r.get(k) else None
    return rows


def _median(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


@frappe.whitelist()
@requires_module("claims")
def crm_dashboard_claims(date_from=None, date_to=None, customer=None):
    _guard()
    cfg = _settings()
    empty = {"kpis": {}, "by_type": [], "by_status": [], "rows": [], "types": cfg["types"],
             "sla_days": cfg["sla_days"], "currency": _company_currency(), "available": False}
    if not _available():
        return empty
    frm, to = _range(date_from, date_to)
    filters = {"customer": customer} if customer else {}

    # Everything still open, whenever it was raised, plus whatever was raised in
    # the range: an old open claim is exactly what this page must not hide.
    open_rows = frappe.get_all(DOCTYPE, filters={**filters, "status": ["in", ["Open", "Under Review"]]},
                               fields=ROW_FIELDS, order_by="raised_on asc", limit=500)
    range_rows = frappe.get_all(DOCTYPE, filters={**filters, "raised_on": ["between", [frm, to]]},
                                fields=ROW_FIELDS, order_by="raised_on desc", limit=500)
    seen, rows = set(), []
    for r in open_rows + range_rows:
        if r.name not in seen:
            seen.add(r.name)
            rows.append(r)
    _decorate(rows, cfg["sla_days"])

    resolved = frappe.get_all(DOCTYPE, filters={**filters, "resolved_on": ["between", [frm, to]]},
                              fields=["raised_on", "resolved_on", "status"], limit=0)
    in_range = [r for r in rows if r["raised_on"] and frm <= r["raised_on"] <= to]
    by_type, by_status = {}, {}
    for r in in_range:
        by_type[r.claim_type] = by_type.get(r.claim_type, 0) + 1
        by_status[r.status] = by_status.get(r.status, 0) + 1

    kpis = {
        "open": sum(1 for r in rows if r.status == "Open"),
        "under_review": sum(1 for r in rows if r.status == "Under Review"),
        "overdue": sum(1 for r in rows if r["overdue"]),
        "raised": len(in_range),
        "resolved": sum(1 for r in resolved if r.status == "Resolved"),
        "rejected": sum(1 for r in resolved if r.status == "Rejected"),
        "median_days_to_close": _median([date_diff(r.resolved_on, r.raised_on) for r in resolved
                                         if r.resolved_on and r.raised_on]),
        "claimed": sum(flt(r.amount_claimed) for r in in_range),
        "credited": sum(flt(r.amount_credited) for r in in_range),
    }
    rows.sort(key=lambda r: (not r["overdue"], r["raised_on"] or ""), reverse=False)
    return {**empty, "available": True, "kpis": kpis,
            "by_type": [{"label": k, "count": v} for k, v in sorted(by_type.items(), key=lambda x: -x[1])],
            "by_status": [{"label": k, "count": v} for k, v in by_status.items()],
            "rows": rows, "range": {"from": frm, "to": to}}


@frappe.whitelist(methods=["POST"])
@requires_module("claims")
def crm_claim_save(claim=None):
    """Create a claim, or update one when `name` is given."""
    _guard()
    payload = json.loads(claim) if isinstance(claim, str) else (claim or {})
    if not isinstance(payload, dict):
        frappe.throw(_("Malformed claim"))
    name = payload.get("name")
    values = {k: v for k, v in payload.items() if k in EDITABLE}
    if name:
        doc = frappe.get_doc(DOCTYPE, name)
        doc.check_permission("write")
    else:
        doc = frappe.new_doc(DOCTYPE)
        doc.check_permission("create")
        frappe.has_permission("Customer", "read", values.get("customer"), throw=True)
    doc.update(values)
    doc.save()
    row = {f: doc.get(f) for f in ROW_FIELDS}
    row = _decorate([frappe._dict(row)], _settings()["sla_days"])[0]
    return {"claim": row}


@frappe.whitelist()
@requires_module("claims")
def crm_claim_get(name):
    """The whole claim, for the edit form. Table rows leave out the long text
    fields; editing from a row would otherwise write them back blank."""
    _guard()
    if not frappe.has_permission(DOCTYPE, "read", name):
        frappe.throw(_("Not permitted to read this claim"), frappe.PermissionError)
    doc = frappe.get_doc(DOCTYPE, name)
    row = frappe._dict({f: doc.get(f) for f in ROW_FIELDS + ["description", "root_cause", "resolution"]})
    return {"claim": _decorate([row], _settings()["sla_days"])[0]}


@frappe.whitelist()
@requires_module("claims")
def crm_claim_references(customer, kind="Sales Invoice", search=None):
    """The customer's recent invoices / deliveries / orders, for the claim form."""
    _guard()
    if kind not in REFERENCE_KINDS:
        frappe.throw(_("Unknown order type {0}").format(kind), frappe.ValidationError)
    frappe.has_permission("Customer", "read", customer, throw=True)
    if not frappe.has_permission(kind, "read"):
        return {"rows": [], "no_access": True}
    date_col = "transaction_date" if kind == "Sales Order" else "posting_date"
    filters = {"customer": customer, "docstatus": 1}
    if search:
        filters["name"] = ["like", f"%{search}%"]
    rows = frappe.get_all(kind, filters=filters, fields=["name", "customer", f"{date_col} as date", "base_grand_total"],
                          order_by=f"{date_col} desc", limit=30)
    for r in rows:
        r["date"] = str(r["date"]) if r.get("date") else None
    return {"rows": rows, "no_access": False}


@frappe.whitelist()
@requires_module("claims")
def crm_customer_claims(name):
    """One customer's claims, newest first, for the customer page."""
    _guard()
    frappe.has_permission("Customer", "read", name, throw=True)
    cfg = _settings()
    if not _available():
        return {"rows": [], "available": False, "types": cfg["types"], "sla_days": cfg["sla_days"]}
    rows = frappe.get_all(DOCTYPE, filters={"customer": name}, fields=ROW_FIELDS,
                          order_by="raised_on desc", limit=200)
    return {"rows": _decorate(rows, cfg["sla_days"]), "available": True, "types": cfg["types"],
            "sla_days": cfg["sla_days"], "currency": _company_currency()}
