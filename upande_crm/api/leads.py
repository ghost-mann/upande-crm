"""Whitelisted CRM *write* endpoints for capturing a lead and moving it along.

Same contract as `api/activity.py`, and the inverse of `api/crm.py`'s: the
dashboards degrade to an empty chart when something is missing, but **every
failure here must surface.** A lead the user believes they saved and which was
silently dropped is the worst outcome this module can produce. Never add a bare
`except` around a write.

Design rule: delegate, don't reimplement.
  * Lead -> Opportunity   -> erpnext.crm.doctype.lead.lead.make_opportunity
  * Prospect -> Opportunity -> erpnext.crm.doctype.prospect.prospect.make_opportunity
  * Lead -> existing Prospect -> erpnext.crm.doctype.lead.lead.add_lead_to_prospect
  * Lead -> new Prospect  -> the Lead controller's own `create_prospect`
We own the role gate, the field allowlist, the item lines, and the UI. The field
mapping between doctypes is ERPNext's, and stays ERPNext's.

## Permissions are checked here, unlike everywhere else in this app

The CRM dashboards deliberately read past record-level permissions so a manager
sees the whole pipeline. Writes do not inherit that. Holding a CRM role is enough
to *see* every lead on the Overview; it is not enough to create one. Every
endpoint below asks `frappe.has_permission` and lets the refusal through.

## Why the item lines are here at all

`api/demand.py` reads what clients are asking for from Opportunity Item and
Quotation Item lines. There were six such lines on the whole site, because there
was no way to enter one without opening the desk. Adding varieties at the moment
of conversion — where the salesperson already knows what was asked for — is what
gives that card anything to show.
"""

import json
import re

import frappe
from frappe import _
from frappe.utils import flt, getdate

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

# Opportunity header fields a conversion may set. `party_name`,
# `opportunity_from` and `company` come from the mapper and are not overridable.
OPPORTUNITY_FIELDS = {
    "opportunity_type",
    "sales_stage",
    "expected_closing",
    "probability",
    "opportunity_amount",
    "territory",
    "contact_email",
    "contact_mobile",
    "opportunity_owner",
}

# What an item line may carry. Rate is optional; qty is not.
ITEM_FIELDS = ("item_code", "qty", "rate", "uom", "description")

MAX_ITEMS = 50


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


def _items(payload):
    """Validated item lines. Returns [] when none were supplied.

    An unknown `item_code` is rejected rather than dropped: silently discarding a
    variety the salesperson typed would make the demand card lie about what was
    asked for, which is the one thing it exists to report.
    """
    raw = payload.get("items") or []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            frappe.throw(_("Malformed item lines"))
    if not isinstance(raw, list):
        frappe.throw(_("Malformed item lines"))
    if len(raw) > MAX_ITEMS:
        frappe.throw(_("At most {0} item lines").format(MAX_ITEMS))

    out = []
    for i, row in enumerate(raw, start=1):
        if not isinstance(row, dict):
            frappe.throw(_("Malformed item line {0}").format(i))
        code = (row.get("item_code") or "").strip()
        if not code:
            frappe.throw(_("Item line {0} has no variety").format(i))
        if not frappe.db.exists("Item", code):
            frappe.throw(_("Item line {0}: {1} is not an item").format(i, code))
        qty = flt(row.get("qty"))
        if qty <= 0:
            frappe.throw(_("Item line {0}: quantity must be more than zero").format(i))
        line = {"item_code": code, "qty": qty}
        if row.get("rate") not in (None, ""):
            line["rate"] = flt(row.get("rate"))
        for extra in ("uom", "description"):
            if row.get(extra):
                line[extra] = row[extra]
        out.append(line)
    return out


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


# ---------------------------------------------------------------- lead -> prospect
@frappe.whitelist()
def crm_lead_to_prospect(lead, prospect=None, company_name=None):
    """Attach a Lead to a Prospect, creating the Prospect when none is named."""
    _guard()
    lead = (lead or "").strip()
    if not lead or not frappe.db.exists("Lead", lead):
        frappe.throw(_("Lead not found"))
    _require("Lead", "read", lead)

    prospect = (prospect or "").strip()
    if prospect:
        if not frappe.db.exists("Prospect", prospect):
            frappe.throw(_("Prospect not found"))
        _require("Prospect", "write", prospect)
        if frappe.db.exists("Prospect Lead", {"parent": prospect, "lead": lead}):
            frappe.throw(_("That lead is already on this prospect"))
        from erpnext.crm.doctype.lead.lead import add_lead_to_prospect

        add_lead_to_prospect(lead, prospect)
        return {"prospect": prospect, "created": False}

    _require("Prospect", "create")
    doc = frappe.get_doc("Lead", lead)
    title = (company_name or doc.company_name or doc.lead_name or "").strip()
    if not title:
        frappe.throw(_("A prospect needs a company name"))
    # Prospect is named by `company_name`, so a clash is a real collision the user
    # has to resolve — offer the existing record rather than a naming error.
    if frappe.db.exists("Prospect", title):
        frappe.throw(_("Prospect {0} already exists — add the lead to it instead").format(title))

    # The controller's own method: it carries employees, industry, territory,
    # owner and notes across, and appends the lead to the child table.
    doc.create_prospect(title)
    return {"prospect": title, "created": True}


# ---------------------------------------------------------------- -> opportunity
def _build_opportunity(doc, payload):
    """Apply the header fields and item lines a conversion supplied, then insert."""
    header = _pick(payload, OPPORTUNITY_FIELDS)
    if header.get("expected_closing"):
        try:
            header["expected_closing"] = str(getdate(header["expected_closing"]))
        except Exception:
            frappe.throw(_("Expected closing is not a date"))
    doc.update(header)

    for line in _items(payload):
        doc.append("items", line)

    doc.insert()
    return {
        "name": doc.name,
        "party_name": doc.party_name,
        "opportunity_from": doc.opportunity_from,
        "items": len(doc.get("items") or []),
    }


@frappe.whitelist()
def crm_lead_to_opportunity(lead, opportunity=None):
    """Convert a Lead into an Opportunity, optionally with the flowers asked for."""
    _guard()
    lead = (lead or "").strip()
    if not lead or not frappe.db.exists("Lead", lead):
        frappe.throw(_("Lead not found"))
    _require("Lead", "read", lead)
    _require("Opportunity", "create")

    from erpnext.crm.doctype.lead.lead import make_opportunity

    # If this throws, nothing has been written and the Lead is untouched — the
    # mapper builds an in-memory document and `_build_opportunity` inserts it as
    # the last step.
    return _build_opportunity(make_opportunity(lead), _payload(opportunity, "opportunity"))


@frappe.whitelist()
def crm_prospect_to_opportunity(prospect, opportunity=None):
    """Convert a Prospect into an Opportunity, optionally with item lines."""
    _guard()
    prospect = (prospect or "").strip()
    if not prospect or not frappe.db.exists("Prospect", prospect):
        frappe.throw(_("Prospect not found"))
    _require("Prospect", "read", prospect)
    _require("Opportunity", "create")

    from erpnext.crm.doctype.prospect.prospect import make_opportunity

    return _build_opportunity(make_opportunity(prospect), _payload(opportunity, "opportunity"))


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
        "users": users,
        # What this site insists on. The dialog renders one input per entry, so a
        # customised Lead is fillable from here rather than only from the desk.
        "required_fields": _required_lead_fields(),
        "can_create_lead": bool(frappe.has_permission("Lead", "create")),
        "can_create_prospect": bool(frappe.has_permission("Prospect", "create")),
        "can_create_opportunity": bool(frappe.has_permission("Opportunity", "create")),
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
