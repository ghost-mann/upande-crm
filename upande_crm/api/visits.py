"""Visits: customers at the farm, and sales staff at the customer.

Reads degrade to empty structures on a site that has not migrated the doctype;
writes throw. Follow-up actions are turned into ToDos by the CRM Visit
controller, so saving here is all a caller has to do.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, now_datetime, nowdate

from upande_crm.api.crm import _guard, _has, _range
from upande_crm.modules import requires_module

DOCTYPE = "CRM Visit"
VISIT_TYPES = ("Customer visit to farm", "Sales visit to customer")
EDITABLE = {"visit_type", "party_type", "party", "visit_date", "status", "purpose", "location",
            "staff", "customer_attendees", "outcome"}
ACTION_FIELDS = {"name", "action", "assigned_to", "due_date"}
ROW_FIELDS = ["name", "visit_type", "party_type", "party", "visit_date", "status", "purpose", "location",
              "staff", "customer_attendees", "outcome"]


def _purposes():
    from upande_crm.api.settings import DEFAULTS, get_settings, parse_lines

    return parse_lines(get_settings().get("visit_purposes")) or parse_lines(DEFAULTS["visit_purposes"])


def _available():
    return _has(DOCTYPE) and frappe.has_permission(DOCTYPE, "read")


def _serialise(doc):
    out = {f: doc.get(f) for f in ROW_FIELDS}
    out["visit_date"] = str(doc.visit_date) if doc.visit_date else None
    out["actions"] = [{"name": a.name, "action": a.action, "assigned_to": a.assigned_to,
                       "due_date": str(a.due_date) if a.due_date else None,
                       "todo": frappe.db.get_value("CRM Visit Action", a.name, "todo") or a.todo}
                      for a in doc.actions or []]
    return out


def readable_parties(rows, type_key="party_type", name_key="party"):
    """Drop rows whose party the user cannot read. User Permissions do not apply
    to Dynamic Link fields, so a user restricted to their own customers would
    otherwise see every visit (or opportunity) on the list."""
    seen = {}
    out = []
    for r in rows:
        key = (r.get(type_key), r.get(name_key))
        if key not in seen:
            seen[key] = bool(key[0] and key[1] and frappe.has_permission(key[0], "read", key[1]))
        if seen[key]:
            out.append(r)
    return out


def _with_actions(rows):
    """Attach each visit's follow-ups, and how many are still open, in two queries."""
    if not rows:
        return rows
    names = [r.name for r in rows]
    acts = frappe.get_all("CRM Visit Action", filters={"parent": ["in", names], "parenttype": DOCTYPE},
                          fields=["name", "parent", "action", "assigned_to", "due_date", "todo"], order_by="idx asc",
                          limit=0)
    todos = [a.todo for a in acts if a.todo]
    status = dict(frappe.get_all("ToDo", filters={"name": ["in", todos]}, fields=["name", "status"],
                                 as_list=True)) if todos else {}
    by_parent = {}
    for a in acts:
        a["todo_status"] = status.get(a.todo)
        a["due_date"] = str(a.due_date) if a.due_date else None
        by_parent.setdefault(a.parent, []).append(a)
    for r in rows:
        r["actions"] = by_parent.get(r.name, [])
        r["open_actions"] = sum(1 for a in r["actions"] if a["todo_status"] == "Open")
        r["visit_date"] = str(r.visit_date) if r.visit_date else None
    return rows


@frappe.whitelist()
@requires_module("visits")
def crm_dashboard_visits(date_from=None, date_to=None, customer=None):
    _guard()
    empty = {"kpis": {}, "by_type": [], "by_purpose": [], "rows": [], "upcoming": [],
             "purposes": _purposes(), "types": list(VISIT_TYPES), "available": False}
    if not _available():
        return empty
    frm, to = _range(date_from, date_to)
    base = {"party_type": "Customer", "party": customer} if customer else {}
    rows = frappe.get_list(DOCTYPE, filters={**base, "visit_date": ["between", [f"{frm} 00:00:00", f"{to} 23:59:59"]]},
                          fields=ROW_FIELDS, order_by="visit_date desc", limit=500)
    upcoming = frappe.get_list(DOCTYPE, filters={**base, "status": "Planned", "visit_date": [">=", str(now_datetime())]},
                              fields=ROW_FIELDS, order_by="visit_date asc", limit=20)
    rows = readable_parties(rows)
    upcoming = readable_parties(upcoming)
    _with_actions(rows)
    _with_actions(upcoming)
    by_type, by_purpose = {}, {}
    for r in rows:
        by_type[r.visit_type] = by_type.get(r.visit_type, 0) + 1
        by_purpose[r.purpose] = by_purpose.get(r.purpose, 0) + 1
    return {**empty, "available": True,
            "kpis": {
                "planned": sum(1 for r in rows if r.status == "Planned"),
                "completed": sum(1 for r in rows if r.status == "Completed"),
                "farm_visits": sum(1 for r in rows if r.visit_type == VISIT_TYPES[0]),
                "sales_visits": sum(1 for r in rows if r.visit_type == VISIT_TYPES[1]),
                "open_followups": sum(r["open_actions"] for r in rows),
                "upcoming": len(upcoming),
            },
            "by_type": [{"label": k, "count": v} for k, v in by_type.items()],
            "by_purpose": [{"label": k, "count": v} for k, v in sorted(by_purpose.items(), key=lambda x: -x[1])],
            "rows": rows, "upcoming": upcoming, "range": {"from": frm, "to": to}}


@frappe.whitelist(methods=["POST"])
@requires_module("visits")
def crm_visit_save(visit=None):
    """Create a visit, or update one when `name` is given. `actions`, when sent,
    replaces the follow-up list; rows that already have a task keep it."""
    _guard()
    payload = json.loads(visit) if isinstance(visit, str) else (visit or {})
    if not isinstance(payload, dict):
        frappe.throw(_("Malformed visit"))
    if payload.get("visit_type") and payload["visit_type"] not in VISIT_TYPES:
        frappe.throw(_("Visit type must be one of: {0}.").format(", ".join(VISIT_TYPES)))
    name = payload.get("name")
    if name:
        doc = frappe.get_doc(DOCTYPE, name)
        doc.check_permission("write")
    else:
        doc = frappe.new_doc(DOCTYPE)
        doc.check_permission("create")
    values = {k: v for k, v in payload.items() if k in EDITABLE}
    party_type = values.get("party_type") or doc.party_type or "Customer"
    party = values.get("party") or doc.party
    if party:
        frappe.has_permission(party_type, "read", party, throw=True)
    doc.update(values)
    if "actions" in payload:
        existing = {a.name: a for a in doc.actions or []}
        rows = []
        for a in payload.get("actions") or []:
            a = {k: v for k, v in (a or {}).items() if k in ACTION_FIELDS}
            keep = existing.get(a.get("name"))
            if keep:
                keep.update({k: v for k, v in a.items() if k != "name"})
                rows.append(keep)
            else:
                rows.append({k: v for k, v in a.items() if k != "name"})
        doc.set("actions", [])
        for r in rows:
            doc.append("actions", r if isinstance(r, dict) else r.as_dict())
    doc.save()
    doc.reload()
    return {"visit": _serialise(doc)}


@frappe.whitelist()
@requires_module("visits")
def crm_customer_visits(name):
    _guard()
    frappe.has_permission("Customer", "read", name, throw=True)
    if not _available():
        return {"rows": [], "available": False, "purposes": _purposes(), "types": list(VISIT_TYPES)}
    rows = frappe.get_list(DOCTYPE, filters={"party_type": "Customer", "party": name}, fields=ROW_FIELDS,
                          order_by="visit_date desc", limit=200)
    return {"rows": _with_actions(rows), "available": True, "purposes": _purposes(), "types": list(VISIT_TYPES)}
