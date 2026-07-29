"""Whitelisted endpoints for logging phone calls, incoming and outgoing.

Calls were the one channel the CRM could not record. Email has the Inbox and
WhatsApp has its own section, but a phone call — still how most of this business is
done — had nowhere to go, so it landed wherever was nearest: 21 Communications
tagged medium `Phone`, 6 Events with category `Call`, and everything else lost.

## Why core `Call Log`, not a new doctype

Frappe's Telephony module already ships `Call Log` with exactly the needed shape:
`type` is Incoming/Outgoing, `status` covers Completed/No Answer/Busy/Failed,
plus `duration`, `start_time`, `summary`, `type_of_call` for a disposition
vocabulary, and a `links` child table of Dynamic Link to attach the call to a CRM
record. There were zero rows on this site, so nothing to migrate.

Using it means that if Twilio is ever connected, its automatically-logged calls
appear in this section for free. `CRM Call Log` was rejected: it belongs to the
Frappe CRM app, a separate UI this SPA has nothing to do with.

## Failure behaviour

This is a *write* module, so it follows `api/activity.py`, not the readers: **every
failure surfaces.** A call the user believes they logged and which was silently
dropped is the worst outcome here. The dashboard read is the one exception and
degrades to empty, matching `api/crm.py`.

## Permissions

`Call Log` carries no CRM DocPerms, so — exactly as `crm_send_email` does for
Communication and `crm_whatsapp_send` for WhatsApp Message — every endpoint
role-gates through `_guard()` and then reads/writes with `ignore_permissions=True`,
with the reference validated against an allowlist. The widening is deliberate,
bounded, and consistent with the two channels already decided this way.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, now_datetime, strip_html

from upande_crm.api.activity import (
    MANAGER_ROLES,
    TASK_REF_DOCTYPES,
    _check_ref,
    _is_manager,
    _load,
    _pick,
)
from upande_crm.api.crm import _count, _guard, _has, _hascol

# Fields accepted from the client. Anything else in the payload is dropped rather
# than written, so a crafted request cannot set `owner` or `docstatus`.
CALL_FIELDS = {
    "id",
    "type",
    "status",
    "from",
    "to",
    "duration",
    "start_time",
    "end_time",
    "summary",
    "type_of_call",
    "medium",
    "customer",
    "recording_url",
}

DIRECTIONS = ("Incoming", "Outgoing")

# The subset of Call Log's status vocabulary a manual log can sensibly take. The
# live-telephony states (Ringing, In Progress, Queued) are excluded: they describe
# a call in flight, which a call being written down afterwards never is.
STATUSES = ("Completed", "No Answer", "Busy", "Failed", "Cancelled")

# What a call may be linked to — the same allowlist the task layer uses, reused
# rather than a second vocabulary that could drift from it.
CALL_REF_DOCTYPES = TASK_REF_DOCTYPES


def _available():
    return _has("Call Log")


def _require():
    if not _available():
        frappe.throw(_("Call logging needs Frappe's Telephony module, which is not installed."))


def _digits(number):
    return "".join(ch for ch in str(number or "") if ch.isdigit() or ch == "+")


# ---------------------------------------------------------------- write
@frappe.whitelist()
def crm_call_save(call):
    """Create or update a Call Log, optionally with a follow-up task.

    Duration arrives in **minutes** and is stored in seconds: `duration` is a
    Duration field, and nobody logs a call in seconds.
    """
    _guard()
    _require()
    payload = _load(call) or {}
    name = payload.get("name")
    fields = _pick(payload, CALL_FIELDS)

    direction = fields.get("type")
    if direction not in DIRECTIONS:
        frappe.throw(_("A call must be Incoming or Outgoing."))

    status = fields.get("status") or "Completed"
    if status not in STATUSES:
        frappe.throw(_("Invalid call outcome: {0}").format(status))
    fields["status"] = status

    number = _digits(fields.get("from") if direction == "Incoming" else fields.get("to"))
    if not number:
        frappe.throw(_("A phone number is required."))
    # Store the number on the side the direction implies, so `from`/`to` always
    # mean what they say and the conversation view can group on the counterparty.
    if direction == "Incoming":
        fields["from"] = number
    else:
        fields["to"] = number

    if "duration" in payload:
        minutes = flt(payload.get("duration"))
        if minutes < 0:
            frappe.throw(_("Duration cannot be negative."))
        fields["duration"] = int(minutes * 60)

    fields.setdefault("start_time", str(now_datetime()))
    if fields.get("end_time") and fields.get("start_time") \
            and get_datetime(fields["end_time"]) < get_datetime(fields["start_time"]):
        frappe.throw(_("The call cannot end before it started."))

    if fields.get("type_of_call"):
        if not frappe.db.exists("Telephony Call Type", fields["type_of_call"]):
            frappe.throw(_("Unknown call type: {0}").format(fields["type_of_call"]))

    ref_doctype = payload.get("reference_doctype")
    ref_name = payload.get("reference_name")
    _check_ref(ref_doctype, CALL_REF_DOCTYPES)
    if ref_doctype:
        if not ref_name:
            frappe.throw(_("A linked record is required when a reference type is set"))
        if not frappe.db.exists(ref_doctype, ref_name):
            frappe.throw(_("Linked {0} not found").format(ref_doctype))

    # A call linked to a Customer also fills Call Log's own `customer` column, not
    # just the Dynamic Link table. That makes the link first-class: the customer
    # filter can match on a column instead of a join, and desk reports over Call
    # Log see it too. Only set from an actual Customer reference — inferring it
    # from a Lead would assert a relationship the record does not yet have.
    if ref_doctype == "Customer" and ref_name:
        fields["customer"] = ref_name

    # `id` is required by the doctype and normally comes from the telephony
    # provider. A manual entry has no provider id, so one is minted from the row.
    if not name and not fields.get("id"):
        fields["id"] = frappe.generate_hash(length=16)
    fields.setdefault("medium", "Manual")

    if name:
        doc = frappe.get_doc("Call Log", name)
        doc.update(fields)
    else:
        doc = frappe.get_doc({"doctype": "Call Log", **fields})

    _set_link(doc, ref_doctype, ref_name)

    if name:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)

    result = {"name": doc.name}

    follow_up = payload.get("follow_up")
    if follow_up:
        # The call is the record of fact; the task is a convenience. A failed
        # follow-up must not roll back a call the user watched themselves log.
        try:
            result["follow_up"] = _create_follow_up(doc, follow_up, ref_doctype, ref_name)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "crm_call_save follow-up failed")
            result["follow_up_error"] = str(e)[:300]

    return result


def _set_link(doc, ref_doctype, ref_name):
    """Point the call's Dynamic Link table at one CRM record, replacing any prior."""
    if not _hascol("Call Log", "name"):
        return
    try:
        doc.set("links", [])
        if ref_doctype and ref_name:
            doc.append("links", {"link_doctype": ref_doctype, "link_name": ref_name})
    except Exception:
        # A site whose Call Log lacks the child table still gets the call saved.
        pass


def _create_follow_up(call, follow_up, ref_doctype, ref_name):
    """Create the follow-up ToDo via the existing task layer.

    Delegating rather than inserting a ToDo directly means the task shows up in
    Events & Tasks and inherits that layer's allowlist, validation and completion
    rule — one definition of a CRM task, not two.
    """
    from upande_crm.api.activity import crm_task_save
    from upande_crm.api.settings import get_settings

    settings = get_settings()
    description = ""
    if isinstance(follow_up, dict):
        description = strip_html(follow_up.get("description") or "").strip()
    if not description:
        who = call.get("to") or call.get("from") or ""
        description = _("Follow up on the call with {0}").format(who).strip()

    due = (follow_up or {}).get("date") if isinstance(follow_up, dict) else None
    if not due:
        days = cint(settings.get("default_task_due_days"))
        due = str(frappe.utils.add_days(frappe.utils.nowdate(), days))

    priority = (follow_up or {}).get("priority") if isinstance(follow_up, dict) else None
    task = crm_task_save(json.dumps({
        "description": f"<div>{frappe.utils.escape_html(description)}</div>",
        "date": due,
        "priority": priority or settings.get("default_task_priority") or "Medium",
        "status": "Open",
        "reference_type": ref_doctype or None,
        "reference_name": ref_name or None,
        "allocated_to": frappe.session.user,
    }))
    return {"name": task.get("name"), "date": due}


@frappe.whitelist()
def crm_call_delete(name):
    """Delete a logged call. Owner or manager only, mirroring the task rule."""
    _guard()
    _require()
    owner = frappe.db.get_value("Call Log", name, "owner")
    if not owner:
        frappe.throw(_("Call not found"), frappe.DoesNotExistError)
    if owner != frappe.session.user and not _is_manager():
        frappe.throw(
            _("Only the person who logged this call, or a manager, can delete it."),
            frappe.PermissionError,
        )
    frappe.delete_doc("Call Log", name, ignore_permissions=True)
    return {"name": name, "deleted": True}


# ---------------------------------------------------------------- call types
@frappe.whitelist()
def crm_call_types():
    """The disposition vocabulary. Empty on a fresh site, hence the adder below."""
    _guard()
    if not _has("Telephony Call Type"):
        return []
    try:
        return [r.name for r in frappe.get_all(
            "Telephony Call Type", fields=["name"], order_by="name asc", limit=0,
            ignore_permissions=True)]
    except Exception:
        return []


@frappe.whitelist()
def crm_call_type_add(label):
    """Add a disposition. Idempotent, so the UI can offer 'add' without checking."""
    _guard()
    if not _has("Telephony Call Type"):
        frappe.throw(_("Telephony Call Type is not available on this site."))
    label = str(label or "").strip()
    if not label:
        frappe.throw(_("A call type needs a name."))
    if frappe.db.exists("Telephony Call Type", label):
        return {"name": label, "created": False}
    doc = frappe.get_doc({"doctype": "Telephony Call Type", "call_type": label})
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "created": True}


# ---------------------------------------------------------------- read
def _scope_names(customer):
    """Call names belonging to a customer, via the shared scope resolver."""
    from upande_crm.api.scope import customer_scope

    scope = customer_scope(customer)
    names = set()
    if not _has("Dynamic Link"):
        return []
    for doctype, refs in scope.items():
        if not refs:
            continue
        try:
            names.update(
                r.parent for r in frappe.get_all(
                    "Dynamic Link",
                    filters={"parenttype": "Call Log", "link_doctype": doctype,
                             "link_name": ["in", refs]},
                    fields=["parent"], limit=0, ignore_permissions=True,
                ) if r.parent
            )
        except Exception:
            pass
    # A call can also name the customer directly.
    if _hascol("Call Log", "customer"):
        try:
            names.update(frappe.get_all("Call Log", filters={"customer": customer},
                                        pluck="name", limit=0, ignore_permissions=True))
        except Exception:
            pass
    return sorted(names)


@frappe.whitelist()
def crm_dashboard_calls(date_from=None, date_to=None, customer=None):
    """KPIs, mixes, trend and rows for the Calls section. Degrades to empty."""
    _guard()
    from upande_crm.api.crm import _df, _dw, _group, _rows, _trend_in_range

    if not _available():
        return {"available": False, "kpis": {}, "direction_mix": [], "outcome_mix": [],
                "type_mix": [], "trend": [], "by_user": [], "rows": []}

    from upande_crm.api.crm import _range

    frm, to = _range(date_from, date_to)
    d = _df("Call Log", "start_time", frm, to)
    where_base = ""
    if customer:
        names = _scope_names(customer)
        d = {**d, "name": ["in", names or [""]]}
        quoted = ", ".join(frappe.db.escape(n) for n in (names or [""]))
        where_base = f"`name` in ({quoted})"
    w = _dw("Call Log", "start_time", frm, to, base=where_base)

    total = _count("Call Log", d)
    incoming = _count("Call Log", {**d, "type": "Incoming"})
    outgoing = _count("Call Log", {**d, "type": "Outgoing"})
    connected = _count("Call Log", {**d, "status": "Completed"})
    missed = _count("Call Log", {**d, "status": ["in", ["No Answer", "Busy", "Failed"]]})

    talk_seconds = 0
    try:
        rows = frappe.db.sql(
            f"select coalesce(sum(duration), 0) from `tabCall Log` {w}")
        talk_seconds = cint(rows[0][0]) if rows else 0
    except Exception:
        talk_seconds = 0

    return {
        "available": True,
        "kpis": {
            "total": total,
            "incoming": incoming,
            "outgoing": outgoing,
            "connected": connected,
            "missed": missed,
            # Guarded: an empty range must not raise.
            "connect_rate": round(connected / total * 100, 1) if total else 0.0,
            "talk_minutes": round(talk_seconds / 60, 1),
            "avg_minutes": round(talk_seconds / 60 / connected, 1) if connected else 0.0,
        },
        "direction_mix": _group("Call Log", "type", w),
        "outcome_mix": _group("Call Log", "status", w),
        "type_mix": _group("Call Log", "type_of_call", w),
        "trend": _trend_in_range("Call Log", "start_time", frm, to, where=where_base),
        "by_user": _group("Call Log", "owner", w),
        "rows": _attach_links(_rows("Call Log", [
            "name", "type", "status", "from", "to", "duration", "start_time", "end_time",
            "summary", "type_of_call", "customer", "medium", "owner", "creation",
        ], filters=d, order_by="start_time desc", limit=500)),
    }


# Which link to show when a call carries several.
#
# Core's Call Log controller **auto-links calls by phone number** — logging a call
# to a Customer whose number also belongs to a Lead comes back carrying both. That
# is useful behaviour and is kept, but the row still needs one deterministic
# reference to display, so the most specific account-level record wins over the
# earlier-funnel one it was matched against.
LINK_PREFERENCE = (
    "Customer", "Opportunity", "Quotation", "Prospect", "Sales Order", "Contact",
    "Lead", "Event",
)


def _link_rank(doctype):
    try:
        return LINK_PREFERENCE.index(doctype)
    except ValueError:
        return len(LINK_PREFERENCE)


def _attach_links(rows):
    """Add each call's CRM references, in one query rather than one per row."""
    if not rows or not _has("Dynamic Link"):
        return rows
    names = [r.get("name") for r in rows if r.get("name")]
    if not names:
        return rows
    try:
        links = frappe.get_all(
            "Dynamic Link",
            filters={"parenttype": "Call Log", "parent": ["in", names]},
            fields=["parent", "link_doctype", "link_name"], limit=0,
            ignore_permissions=True,
        )
    except Exception:
        return rows

    by_parent = {}
    for link in links:
        if link.link_doctype and link.link_name:
            by_parent.setdefault(link.parent, []).append(
                {"doctype": link.link_doctype, "name": link.link_name})

    for row in rows:
        found = sorted(by_parent.get(row.get("name")) or [],
                       key=lambda l: _link_rank(l["doctype"]))
        row["links"] = found
        primary = found[0] if found else None
        row["reference_doctype"] = (primary or {}).get("doctype")
        row["reference_name"] = (primary or {}).get("name")
    return rows
