"""Whitelisted CRM *write* endpoints for capturing a lead.

Same contract as `api/activity.py`, and the inverse of `api/crm.py`'s: the
dashboards degrade to an empty chart when something is missing, but **every
failure here must surface.** A lead the user believes they saved and which was
silently dropped is the worst outcome this module can produce. Never add a bare
`except` around a write.

## Capture here, movement in `api/advance.py`

This module used to own conversion too, and grew into two jobs. It now keeps one:
creating and editing a Lead, and serving the options the capture dialogs need.
Every hop between doctypes — lead to opportunity, quotation, prospect or customer,
and everything downstream of those — lives in `api/advance.py`, which imports
`_payload`, `_pick` and `_require` from here.

## Permissions are checked here, unlike everywhere else in this app

The CRM dashboards deliberately read past record-level permissions so a manager
sees the whole pipeline. Writes do not inherit that. Holding a CRM role is enough
to *see* every lead on the Overview; it is not enough to create one. Every
endpoint below asks `frappe.has_permission` and lets the refusal through.

## Why the item lines exist at all

`api/demand.py` reads what clients are asking for from Opportunity Item and
Quotation Item lines. There were six such lines on the whole site, because there
was no way to enter one without opening the desk. `crm_flower_search` below is the
picker that fixed that; the lines themselves are validated in `api/advance.py`,
where the documents that carry them are built.
"""

import json
import re

import frappe
from frappe import _

from upande_crm.api.crm import _guard

# Fields never writable from here, whatever the site's schema says. This is the
# half of the allowlist that does not move: a crafted request cannot set `owner`,
# `docstatus`, timestamps, or the assignment/tag internals.
PROTECTED_FIELDS = {
    "name",
    "owner",
    "docstatus",
    "idx",
    "parent",
    "parenttype",
    "parentfield",
    "creation",
    "modified",
    "modified_by",
    "naming_series",
    "amended_from",
    "_user_tags",
    "_comments",
    "_assign",
    "_liked_by",
    "doctype",
}

# Fieldtypes that hold no writable scalar.
NON_INPUT_FIELDTYPES = {
    "Section Break", "Column Break", "Tab Break", "HTML", "Heading", "Fold",
    "Button", "Image", "Table", "Table MultiSelect", "Read Only",
}

# The base set of Lead fields this app offers. Anything else in the payload is
# dropped rather than written.
#
# It is a *base*, not the whole story, because the allowlist has to survive a
# customised site. This install has made `country`, `city`, `whatsapp_no`,
# `custom_business_unit` and `custom_business_registration_number` mandatory on
# Lead; a frozen list meant every create failed on MandatoryError with no way for
# the dialog to even ask for the values. `_lead_fields()` below adds whatever this
# site actually requires, and `PROTECTED_FIELDS` still holds the line.
LEAD_FIELDS = {
    "lead_name",
    "first_name",
    "last_name",
    "salutation",
    "company_name",
    "email_id",
    "mobile_no",
    "phone",
    "website",
    "source",
    "territory",
    "industry",
    "market_segment",
    "lead_owner",
    "status",
    "no_of_employees",
    "annual_revenue",
    "job_title",
    "request_type",
    "type",
}

def _payload(raw, what="payload"):
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError):
        frappe.throw(_("Malformed {0}").format(what))
    if not isinstance(parsed, dict):
        frappe.throw(_("Malformed {0}").format(what))
    return parsed


def _pick(payload, allowed):
    """Only the allowlisted keys, and only those actually supplied."""
    return {k: v for k, v in payload.items() if k in allowed}


def _required_lead_fields():
    """Mandatory Lead fields on *this* site, as form descriptors.

    Read from the meta rather than assumed, because mandatory-ness is a site
    decision. Returns the descriptors the dialog needs to render an input, so a
    farm that requires `custom_business_unit` gets asked for it instead of getting
    a MandatoryError after pressing save.
    """
    try:
        meta = frappe.get_meta("Lead")
    except Exception:
        return []
    out = []
    for f in meta.fields:
        if not f.reqd or f.fieldname in PROTECTED_FIELDS:
            continue
        if f.fieldtype in NON_INPUT_FIELDTYPES:
            continue
        out.append({
            "fieldname": f.fieldname,
            "label": f.label or f.fieldname,
            "fieldtype": f.fieldtype,
            "options": f.options or "",
            "default": f.default or "",
        })
    return out


def _lead_fields():
    """The base allowlist, widened by whatever this site has made mandatory."""
    return LEAD_FIELDS | {f["fieldname"] for f in _required_lead_fields()}


def _require(doctype, ptype, name=None):
    if not frappe.has_permission(doctype, ptype, doc=name):
        frappe.throw(
            _("Not permitted to {0} {1}").format(ptype, _(doctype)),
            frappe.PermissionError,
        )


# ---------------------------------------------------------------- lead
@frappe.whitelist()
def crm_lead_save(lead):
    """Create or update a Lead from the CRM app."""
    _guard()
    data = _payload(lead, "lead")
    name = (data.get("name") or "").strip()
    fields = _pick(data, _lead_fields())

    # ERPNext derives `lead_name` from the name parts, but a lead with neither a
    # person nor a company is an empty row nobody can act on.
    if not name and not any(fields.get(k) for k in ("lead_name", "first_name", "company_name")):
        frappe.throw(_("A lead needs a name or a company"))

    if name:
        _require("Lead", "write", name)
        doc = frappe.get_doc("Lead", name)
        doc.update(fields)
        doc.save()
    else:
        _require("Lead", "create")
        doc = frappe.get_doc({"doctype": "Lead", **fields})
        doc.insert()

    return {
        "name": doc.name,
        "lead_name": doc.lead_name,
        "company_name": doc.company_name,
        "status": doc.status,
    }


# ---------------------------------------------------------------- form options
def _link_options(doctype, limit=100):
    try:
        return frappe.get_all(doctype, pluck="name", limit=limit, order_by="name")
    except Exception:
        return []


def _select_options(doctype, fieldname):
    try:
        meta = frappe.get_meta(doctype)
        field = meta.get_field(fieldname)
        return [o for o in (field.options or "").split("\n") if o] if field else []
    except Exception:
        return []


@frappe.whitelist()
def crm_lead_form_options():
    """Everything the lead and convert dialogs need to render their selects.

    A read, so it degrades: a site without Lead Source should show an empty
    select, not an error dialog on top of the form the user was filling in.
    """
    _guard()
    from upande_crm.api.activity import crm_assignable_users

    try:
        users = crm_assignable_users()
    except Exception:
        users = []

    return {
        "sources": _link_options("Lead Source"),
        "territories": _link_options("Territory", limit=200),
        "industries": _link_options("Industry Type"),
        "market_segments": _link_options("Market Segment"),
        "sales_stages": _link_options("Sales Stage"),
        "opportunity_types": _link_options("Opportunity Type"),
        "lead_statuses": _select_options("Lead", "status"),
        # For the quotation and customer hops in `api/advance.py`.
        "order_types": _select_options("Quotation", "order_type"),
        "customer_groups": _link_options("Customer Group"),
        "customer_types": _select_options("Customer", "customer_type"),
        "users": users,
        # What this site insists on. The dialog renders one input per entry, so a
        # customised Lead is fillable from here rather than only from the desk.
        "required_fields": _required_lead_fields(),
        "can_create_lead": bool(frappe.has_permission("Lead", "create")),
        "can_create_prospect": bool(frappe.has_permission("Prospect", "create")),
        "can_create_opportunity": bool(frappe.has_permission("Opportunity", "create")),
        "can_create_quotation": bool(frappe.has_permission("Quotation", "create")),
        "can_create_customer": bool(frappe.has_permission("Customer", "create")),
    }


@frappe.whitelist()
def crm_flower_search(query="", limit=20):
    """Sellable items, for the variety picker on a conversion."""
    _guard()
    try:
        limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        limit = 20

    filters = {"disabled": 0}
    try:
        meta = frappe.get_meta("Item")
        if meta.get_field("is_sales_item"):
            filters["is_sales_item"] = 1
    except Exception:
        pass

    or_filters = None
    if query:
        like = ["like", f"%{query}%"]
        or_filters = {"name": like, "item_name": like}

    try:
        rows = frappe.get_all(
            "Item",
            filters=filters,
            or_filters=or_filters,
            fields=["name", "item_name", "stock_uom", "item_group"],
            # Over-fetch so the ranking below has something to reorder. Frappe
            # sanitises `order_by`, so ranking cannot be pushed into SQL.
            limit=limit * 5 if query else limit,
            order_by="item_name",
        )
    except Exception:
        return []

    if query:
        # Rank by *where* the match falls, not alphabetically. A substring search
        # is obedient in ways that look broken in a picker: "gis" matches both
        # "Giselle" and "Motor ReGIStration", "rose" matches both "Rose Stems" and
        # "DextROSE 50%". Word-boundary hits come first, then earliest position.
        q = query.lower()
        boundary = re.compile(r"\b" + re.escape(q))

        def rank(r):
            label = (r.item_name or r.name or "").lower()
            code = (r.name or "").lower()
            hits = [s for s in (label, code) if q in s]
            at_word = 0 if any(boundary.search(s) for s in hits) else 1
            best = min((s.find(q) for s in hits), default=9999)
            return (at_word, best, label)

        rows = sorted(rows, key=rank)[:limit]

    return [
        {"value": r.name, "label": r.item_name or r.name,
         "uom": r.stock_uom, "group": r.item_group}
        for r in rows
    ]
