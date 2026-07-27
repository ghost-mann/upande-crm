"""Whitelisted CRM *write* endpoints for Events and Tasks (ToDo).

Deliberately separate from `api/crm.py`. That module is a read layer whose house
style is defensive degradation — a missing doctype yields an empty chart rather
than an error. This module is the inverse: **every failure must surface.** A
swallowed exception here means a meeting or task the user believes they saved was
silently dropped. Never add a bare `except` around a write.

Design rule: delegate, don't reimplement.
  * assignment + `_assign` upkeep + notifications -> frappe.desk.form.assign_to
  * recurrence expansion for the calendar         -> frappe.desk.doctype.event.event.get_events
  * Google Calendar push, Meet links, repeat validation -> core Event controller
We own the role gate, the doctype allowlists, the completion rule, and the UI.
"""

import json

import frappe
from frappe import _
from frappe.utils import getdate, strip_html

from upande_crm.api.crm import CRM_ROLES, _guard

# Roles allowed to close a task that is not their own. Desk restricts completion
# to the assignee; a dashboard exists for oversight, so managers get an override.
MANAGER_ROLES = {"System Manager", "Sales Manager", "CRM Manager"}

# What a CRM task may reference. `Event` is included because assigning an Event
# creates a ToDo pointing at it.
TASK_REF_DOCTYPES = {
    "Lead",
    "Opportunity",
    "Prospect",
    "Customer",
    "Quotation",
    "Contact",
    "Sales Order",
    "Event",
}

# Event participants may additionally be people.
PARTICIPANT_DOCTYPES = TASK_REF_DOCTYPES | {"Employee", "User"}

# Fields accepted from the client. Anything else in the payload is dropped rather
# than written, so a crafted request cannot set `owner`, `docstatus`, or another
# app's custom field.
EVENT_FIELDS = {
    "subject",
    "event_category",
    "event_type",
    "starts_on",
    "ends_on",
    "all_day",
    "status",
    "description",
    "location",
    "color",
    "send_reminder",
    "repeat_this_event",
    "repeat_on",
    "repeat_till",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "sync_with_google_calendar",
    "google_calendar",
    "add_video_conferencing",
}

TASK_FIELDS = {
    "description",
    "date",
    "priority",
    "status",
    "color",
    "reference_type",
    "reference_name",
    "allocated_to",
}

EVENT_STATUSES = {"Open", "Completed", "Closed", "Cancelled"}
TASK_STATUSES = {"Open", "Closed", "Cancelled"}


# ---------------------------------------------------------------- helpers
def _is_manager(user=None):
    return bool(set(frappe.get_roles(user or frappe.session.user)) & MANAGER_ROLES)


def _check_ref(doctype, allowed):
    """Reject any reference/participant doctype outside `allowed`.

    Keeps these endpoints from becoming a generic write API for arbitrary
    doctypes. Raises rather than returning a flag so a caller cannot forget to
    check the result.
    """
    if not doctype:
        return
    if doctype not in allowed:
        frappe.throw(_("Cannot link CRM activity to {0}").format(doctype), frappe.PermissionError)


def _pick(payload, allowed):
    """Whitelist-filter a client payload down to writable fields."""
    return {k: v for k, v in (payload or {}).items() if k in allowed}


def _load(payload):
    """Accept either a JSON string (form-encoded POST) or an already-parsed value."""
    if isinstance(payload, str):
        try:
            return json.loads(payload or "null")
        except ValueError:
            frappe.throw(_("Malformed request payload"))
    return payload


# ---------------------------------------------------------------- pickers
@frappe.whitelist()
def crm_assignable_users():
    """Enabled users holding a CRM role — the assignment picker's option list."""
    _guard()
    rows = frappe.get_all(
        "Has Role",
        filters={"role": ["in", sorted(CRM_ROLES)], "parenttype": "User"},
        fields=["parent"],
        distinct=True,
    )
    names = sorted({r.parent for r in rows})
    if not names:
        return []
    users = frappe.get_all(
        "User",
        filters={"name": ["in", names], "enabled": 1},
        fields=["name", "full_name"],
        order_by="full_name asc",
    )
    return [{"name": u.name, "full_name": u.full_name or u.name} for u in users]


@frappe.whitelist()
def crm_my_calendars():
    """The signed-in user's *authorized* Google Calendars.

    Only calendars holding both a refresh token and a calendar id can actually
    receive a push. Returning just these lets the UI hide the sync toggle rather
    than offer a control that would silently fail.
    """
    _guard()
    if not frappe.db.exists("DocType", "Google Calendar"):
        return []
    rows = frappe.get_all(
        "Google Calendar",
        filters={"user": frappe.session.user, "enable": 1},
        fields=["name", "calendar_name", "refresh_token", "google_calendar_id"],
    )
    return [
        {"name": r.name, "calendar_name": r.calendar_name or r.name}
        for r in rows
        if r.refresh_token and r.google_calendar_id
    ]


# ---------------------------------------------------------------- events
@frappe.whitelist()
def crm_event_save(event):
    """Create or update an Event.

    Participants are replaced wholesale: the client always sends the full list,
    so removing a row client-side removes it here. Recurrence and Google fields
    are handed to the core controller, which owns their validation and push.
    """
    _guard()
    payload = _load(event) or {}
    name = payload.get("name")
    fields = _pick(payload, EVENT_FIELDS)

    if not str(fields.get("subject") or "").strip():
        frappe.throw(_("Subject is required"))
    if not fields.get("starts_on"):
        frappe.throw(_("A start date and time is required"))
    if fields.get("ends_on") and str(fields["ends_on"]) < str(fields["starts_on"]):
        frappe.throw(_("End must be on or after the start"))

    fields.setdefault("event_type", "Private")
    fields.setdefault("status", "Open")

    # Google sync is only honoured when the user actually has an authorized
    # calendar. Otherwise drop the request rather than create an Event doomed to
    # fail on push.
    if fields.get("sync_with_google_calendar"):
        allowed = {c["name"] for c in crm_my_calendars()}
        if fields.get("google_calendar") not in allowed:
            fields["sync_with_google_calendar"] = 0
            fields["google_calendar"] = None

    participants = payload.get("participants") or []
    for p in participants:
        _check_ref(p.get("reference_doctype"), PARTICIPANT_DOCTYPES)

    if name:
        doc = frappe.get_doc("Event", name)
        doc.update(fields)
    else:
        doc = frappe.get_doc({"doctype": "Event", **fields})

    doc.set("event_participants", [])
    for p in participants:
        if p.get("reference_doctype") and p.get("reference_docname"):
            doc.append(
                "event_participants",
                {
                    "reference_doctype": p["reference_doctype"],
                    "reference_docname": p["reference_docname"],
                },
            )

    if name:
        doc.save()
    else:
        doc.insert()
    return {"name": doc.name}


@frappe.whitelist()
def crm_event_status(name, status):
    """Set an Event's status. Used by the 'mark complete' row action."""
    _guard()
    if status not in EVENT_STATUSES:
        frappe.throw(_("Invalid event status: {0}").format(status))
    doc = frappe.get_doc("Event", name)
    doc.status = status
    doc.save()
    return {"name": doc.name, "status": doc.status}


# ---------------------------------------------------------------- tasks
def _assert_may_close(doc):
    """Desk allows only the assignee to complete a to-do; we add a manager override.

    Raises PermissionError for anyone else, so the UI surfaces "not your task"
    instead of appearing to succeed.
    """
    user = frappe.session.user
    if doc.allocated_to == user or doc.assigned_by == user or doc.owner == user:
        return
    if _is_manager(user):
        return
    frappe.throw(
        _("Only the assignee or a sales manager can change this task."),
        frappe.PermissionError,
    )


@frappe.whitelist()
def crm_task_save(task):
    """Create or update a ToDo.

    `allocated_to` is set directly rather than routed through assign_to.add —
    that helper creates a *new* ToDo referencing a target document, which for a
    task would mean a second ToDo pointing at the first.
    """
    _guard()
    payload = _load(task) or {}
    name = payload.get("name")
    fields = _pick(payload, TASK_FIELDS)

    if not strip_html(fields.get("description") or "").strip():
        frappe.throw(_("Description is required"))

    _check_ref(fields.get("reference_type"), TASK_REF_DOCTYPES)
    if fields.get("reference_type") and not fields.get("reference_name"):
        frappe.throw(_("A linked record is required when a reference type is set"))

    fields.setdefault("status", "Open")
    fields.setdefault("priority", "Medium")

    if name:
        doc = frappe.get_doc("ToDo", name)
        if fields.get("status") and fields["status"] != doc.status:
            _assert_may_close(doc)
        doc.update(fields)
        doc.save()
    else:
        fields["assigned_by"] = frappe.session.user
        doc = frappe.get_doc({"doctype": "ToDo", **fields})
        doc.insert()
    return {"name": doc.name}


@frappe.whitelist()
def crm_task_status(name, status):
    """Complete / reopen / cancel a task under the completion rule.

    For an assignment ToDo being closed by its assignee we route through
    `assign_to.close` so core's side effects fire. The manager-override path
    cannot use it (it refuses non-assignees by design), so it saves directly —
    which is still correct: ToDo.validate emits the "Assignment of X removed by
    Y" comment and on_update -> update_in_reference() refreshes `_assign` on the
    referenced document.
    """
    _guard()
    if status not in TASK_STATUSES:
        frappe.throw(_("Invalid task status: {0}").format(status))

    doc = frappe.get_doc("ToDo", name)
    _assert_may_close(doc)

    is_assignee = doc.allocated_to == frappe.session.user
    if status == "Closed" and is_assignee and doc.reference_type and doc.reference_name:
        from frappe.desk.form.assign_to import close as assign_close

        assign_close(doc.reference_type, doc.reference_name, doc.allocated_to)
        return {"name": doc.name, "status": "Closed"}

    doc.status = status
    doc.save()
    return {"name": doc.name, "status": doc.status}


# ---------------------------------------------------------------- assignment
def _assignees(doctype, name):
    rows = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": doctype,
            "reference_name": str(name),
            "status": ["not in", ("Cancelled", "Closed")],
        },
        fields=["allocated_to"],
    )
    return sorted({r.allocated_to for r in rows if r.allocated_to})


@frappe.whitelist()
def crm_assign(doctype, name, assign_to, description=None, date=None, priority=None):
    """Assign a CRM record (or Event) to one or more users.

    Delegates to frappe.desk.form.assign_to.add, which creates the ToDo, stamps
    `_assign`, shares the document if the assignee lacks access, and sends the
    assignment notification. Reimplementing any of that would drift from desk.
    """
    _guard()
    _check_ref(doctype, TASK_REF_DOCTYPES)

    users = _load(assign_to) if isinstance(assign_to, str) else assign_to
    if isinstance(users, str):
        users = [users]
    users = [u for u in (users or []) if u]
    if not users:
        frappe.throw(_("Select at least one user to assign"))
    if not frappe.db.exists(doctype, name):
        frappe.throw(_("{0} {1} not found").format(doctype, name))

    from frappe.desk.form.assign_to import add as assign_add

    args = {
        "doctype": doctype,
        "name": name,
        "assign_to": users,
        "description": description or "",
        "priority": priority or "Medium",
        "assigned_by": frappe.session.user,
    }
    # Only pass `date` when set: core defaults it to nowdate() on a missing key,
    # but would write a literal empty value if we passed one.
    if date:
        args["date"] = date

    assign_add(args)
    return {"assignees": _assignees(doctype, name)}


@frappe.whitelist()
def crm_unassign(doctype, name, assign_to):
    """Remove one user's assignment from a record (core sets the ToDo Cancelled)."""
    _guard()
    _check_ref(doctype, TASK_REF_DOCTYPES)

    from frappe.desk.form.assign_to import remove as assign_remove

    assign_remove(doctype, name, assign_to)
    return {"assignees": _assignees(doctype, name)}


# ---------------------------------------------------------------- calendar
CALENDAR_KEYS = (
    "name",
    "subject",
    "starts_on",
    "ends_on",
    "all_day",
    "status",
    "event_category",
    "color",
)


@frappe.whitelist()
def crm_calendar(start, end):
    """Events between `start` and `end`, with recurrences expanded.

    Wraps core's whitelisted `get_events`, which already handles Daily / Weekly
    (incl. per-weekday checks) / Monthly / Quarterly / Half Yearly / Yearly
    expansion. Writing that arithmetic here would duplicate core logic and drift
    from what desk's calendar shows.

    The window is the month or week being viewed and is deliberately independent
    of the dashboard's date-range pill.
    """
    _guard()
    from frappe.desk.doctype.event.event import get_events

    rows = get_events(getdate(start), getdate(end))
    return [{k: r.get(k) for k in CALENDAR_KEYS} for r in rows]
