"""Price catalogues shared with buyers by link (CRM side).

See docs/superpowers/specs/2026-10-25-crm-catalogues-design.md. The buyer's
side — the guest page and its submissions — is api/catalogue_public.py; the
Excel import is api/catalogue_import.py.

Reads follow the rest of the CRM and degrade to empty past the role gate. Writes
throw. Any CRM user may build a catalogue; only its owner and CRM managers may
change it afterwards. That rule lives here rather than in DocPerms because the
CRM roles' permissions are granted per site by `setup.ensure_crm_role_permissions`.
"""

import json

import frappe
from frappe import _
from frappe.query_builder.functions import Count
from frappe.utils import get_url

from upande_crm.api.crm import _guard, _has
from upande_crm.modules import requires_module

DOCTYPE = "CRM Catalogue"
LINK = "CRM Catalogue Link"
INTEREST = "CRM Catalogue Interest"
MANAGER_ROLES = {"System Manager", "Sales Manager", "CRM Manager"}
STATUSES = ("Draft", "Live", "Closed")
EDITABLE = {"title", "company", "status", "valid_from", "valid_to", "currencies", "volume_tier_qty", "terms"}
LINE_FIELDS = ("item", "grade", "box_type", "color", "vbn", "pack_qty", "bunch", "weight", "info_url", "prices")
ROW_FIELDS = ["name", "title", "company", "status", "valid_from", "valid_to", "currencies", "owner", "views",
              "public_token", "modified"]


def catalogue_url(token):
    return get_url(f"/catalogue/{token}")


def is_manager(user=None):
    return bool(set(frappe.get_roles(user or frappe.session.user)) & MANAGER_ROLES)


def can_edit(doc):
    return doc.owner == frappe.session.user or is_manager()


def _check_edit(doc):
    if not can_edit(doc):
        frappe.throw(_("Only the catalogue's owner or a sales manager can change it."), frappe.PermissionError)


def _available():
    return _has(DOCTYPE) and frappe.has_permission(DOCTYPE, "read")


def _counts(doctype, names, where=None):
    """{catalogue: count} for `doctype` rows pointing at `names`."""
    if not names:
        return {}
    t = frappe.qb.DocType(doctype)
    q = (frappe.qb.from_(t).select(t.catalogue, Count("*")).where(t.catalogue.isin(names))
         .groupby(t.catalogue))
    if where is not None:
        q = q.where(where(t))
    return dict(q.run())


def _serialise(doc):
    out = {f: doc.get(f) for f in ROW_FIELDS + ["volume_tier_qty", "terms"]}
    for k in ("valid_from", "valid_to", "modified"):
        out[k] = str(out[k]) if out.get(k) else None
    out["lines"] = []
    for line in doc.lines or []:
        row = {f: line.get(f) for f in LINE_FIELDS}
        row["name"] = line.name
        row["item_name"] = line.item_name
        row["prices"] = json.loads(line.prices) if isinstance(line.prices, str) and line.prices else (line.prices or {})
        out["lines"].append(row)
    out["can_edit"] = can_edit(doc)
    return out


@frappe.whitelist()
@requires_module("cat")
def crm_catalogues():
    """Every catalogue the user can read, with how far each has travelled."""
    _guard()
    if not _available():
        return {"rows": [], "available": False}
    rows = frappe.get_list(DOCTYPE, fields=ROW_FIELDS, order_by="modified desc", limit=500)
    names = [r.name for r in rows]
    links = _counts(LINK, names)
    opened = _counts(LINK, names, lambda t: t.open_count > 0)
    interests = _counts(INTEREST, names)
    lines = {}
    if names:
        ln = frappe.qb.DocType("CRM Catalogue Line")
        lines = dict(frappe.qb.from_(ln).select(ln.parent, Count("*"))
                     .where((ln.parent.isin(names)) & (ln.parenttype == DOCTYPE)).groupby(ln.parent).run())
    me, manager = frappe.session.user, is_manager()
    for r in rows:
        r["links"] = links.get(r.name, 0)
        r["opened"] = opened.get(r.name, 0)
        r["interests"] = interests.get(r.name, 0)
        r["lines"] = lines.get(r.name, 0)
        r["public_url"] = catalogue_url(r.public_token)
        r["can_edit"] = manager or r.owner == me
        for k in ("valid_from", "valid_to", "modified"):
            r[k] = str(r[k]) if r.get(k) else None
    return {"rows": rows, "available": True}


@frappe.whitelist()
@requires_module("cat")
def crm_catalogue_get(name):
    _guard()
    frappe.has_permission(DOCTYPE, "read", name, throw=True)
    doc = frappe.get_doc(DOCTYPE, name)
    return {"catalogue": _serialise(doc), "public_url": catalogue_url(doc.public_token)}


@frappe.whitelist(methods=["POST"])
@requires_module("cat")
def crm_catalogue_save(catalogue=None):
    """Create a catalogue, or update one when `name` is given. `lines`, when
    present, replaces the catalogue's lines wholesale."""
    _guard()
    payload = json.loads(catalogue) if isinstance(catalogue, str) else (catalogue or {})
    if not isinstance(payload, dict):
        frappe.throw(_("Malformed catalogue"))
    name = payload.get("name")
    if name:
        doc = frappe.get_doc(DOCTYPE, name)
        _check_edit(doc)
    else:
        doc = frappe.new_doc(DOCTYPE)
    doc.update({k: v for k, v in payload.items() if k in EDITABLE})
    if "lines" in payload:
        doc.set("lines", [])
        for line in payload.get("lines") or []:
            row = {k: line.get(k) for k in LINE_FIELDS if k in line}
            if isinstance(row.get("prices"), dict):
                row["prices"] = json.dumps(row["prices"])
            doc.append("lines", row)
    # Ownership is enforced above; DocPerms for the CRM roles vary by site.
    doc.save(ignore_permissions=True) if name else doc.insert(ignore_permissions=True)
    return {"catalogue": _serialise(doc), "public_url": catalogue_url(doc.public_token)}


@frappe.whitelist(methods=["POST"])
@requires_module("cat")
def crm_catalogue_status(name, status):
    _guard()
    if status not in STATUSES:
        frappe.throw(_("Unknown status {0}").format(status), frappe.ValidationError)
    doc = frappe.get_doc(DOCTYPE, name)
    _check_edit(doc)
    doc.status = status
    doc.save(ignore_permissions=True)
    return {"status": doc.status}


@frappe.whitelist(methods=["POST"])
@requires_module("cat")
def crm_catalogue_duplicate(name):
    """A Draft copy with its own link; the copy belongs to whoever made it."""
    _guard()
    frappe.has_permission(DOCTYPE, "read", name, throw=True)
    new = frappe.copy_doc(frappe.get_doc(DOCTYPE, name))
    new.status = "Draft"
    new.title = _("{0} (copy)").format(new.title)
    new.insert(ignore_permissions=True)
    return {"name": new.name}
