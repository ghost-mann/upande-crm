# CRM Events & Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the CRM SPA desk-equivalent Event and Task management — create, edit, assign, unassign, mark complete, a month/week calendar, participants, recurrence, and Google Calendar sync.

**Architecture:** All writes live in a new `upande_crm/api/activity.py`, kept separate from the read-only `api/crm.py` so "reads degrade, writes fail loudly" is structural. The module delegates to Frappe core wherever core already owns the concern: `frappe.desk.form.assign_to` for assignment and `_assign` upkeep, `frappe.desk.doctype.event.event.get_events` for recurrence expansion, and the core `Event` controller for Google Calendar push. The React side splits the read-only `sections/Events.jsx` into a folder of focused components and adds a reusable `LinkSearch` combobox that spec 3 (WhatsApp) will reuse.

**Tech Stack:** Frappe v16 / Python 3.14, React 18 + Zustand + Vite, Tailwind, Radix primitives, Material Symbols icons.

## Global Constraints

- Reads may degrade to empty/zero; **writes must throw**. Never wrap a write in a bare `except`.
- No `ignore_permissions=True` on user-initiated writes in `activity.py`. Core helpers that use it internally (`assign_to`) are fine.
- Every endpoint calls `_guard()` first (imported from `api/crm.py` — single source of truth for the CRM role gate).
- Doctype allowlists are mandatory on every reference/participant field. Off-list → `frappe.PermissionError`.
- **Add no new npm dependencies.** `vite.config.js` documents that chunk-splitting mistakes here cause blank-screen crashes from circular vendor chunks. The calendar is hand-rolled.
- Frontend must be rebuilt to be visible: `cd frontend && yarn build`.
- Existing style vocabulary only: `.tbl`, `.bdg`, `.crm-empty`, `.cell-id`, `.list`, `.k-trend`, `.iconbtn`, `.datepill`, and the `ink`/`gold`/`surface`/`hairline` Tailwind tokens.
- Test command: `bench --site kaitet.local run-tests --app upande_crm`
- Site for manual verification: `http://localhost:8002/customer-relationship-management` (port 8002, not 8000; `kaitet.local` does not resolve).

## File Structure

**Created:**
| File | Responsibility |
|---|---|
| `upande_crm/api/activity.py` | All Event/ToDo write endpoints + calendar read + picker helpers |
| `upande_crm/tests/__init__.py` | Test package marker |
| `upande_crm/tests/test_activity.py` | Permission, allowlist, and completion-rule tests |
| `frontend/src/components/ui/textarea.jsx` | Textarea primitive |
| `frontend/src/components/ui/checkbox.jsx` | Checkbox primitive (native input, no new dep) |
| `frontend/src/components/LinkSearch.jsx` | Debounced link combobox over `frappe.desk.search.search_link` |
| `frontend/src/components/EventDialog.jsx` | Create/edit Event |
| `frontend/src/components/TaskDialog.jsx` | Create/edit Task |
| `frontend/src/components/AssignControl.jsx` | Assign/unassign users on a record |
| `frontend/src/sections/Events/index.jsx` | Routes on `table` |
| `frontend/src/sections/Events/Dashboard.jsx` | KPIs + charts (today's content, moved) |
| `frontend/src/sections/Events/EventsTable.jsx` | Event list + row actions |
| `frontend/src/sections/Events/TasksTable.jsx` | Task list + inline complete + assign |
| `frontend/src/sections/Events/Calendar.jsx` | Month grid + week strip |

**Modified:**
| File | Change |
|---|---|
| `upande_crm/api/crm.py` | `crm_dashboard_events_tasks`: CRM-scope the ToDo query, return extra form fields |
| `frontend/src/api.js` | Add activity endpoint wrappers |
| `frontend/src/store.js` | Add write actions + calendar slice |
| `frontend/src/nav.js` | Add Calendar sub-item |
| `frontend/src/App.jsx` | Register the new dialogs |
| `frontend/src/sections/Events.jsx` | Deleted, replaced by `sections/Events/` |

**Interfaces produced by the backend (consumed by every frontend task):**

```
upande_crm.api.activity.crm_event_save(event: json)         -> {"name": str}
upande_crm.api.activity.crm_event_status(name, status)      -> {"name": str, "status": str}
upande_crm.api.activity.crm_task_save(task: json)           -> {"name": str}
upande_crm.api.activity.crm_task_status(name, status)       -> {"name": str, "status": str}
upande_crm.api.activity.crm_assign(doctype, name, assign_to: json, description=None, date=None, priority=None)
                                                            -> {"assignees": [str]}
upande_crm.api.activity.crm_unassign(doctype, name, assign_to) -> {"assignees": [str]}
upande_crm.api.activity.crm_calendar(start, end)            -> [{name, subject, starts_on, ends_on, all_day, status, event_category, color}]
upande_crm.api.activity.crm_assignable_users()              -> [{"name": email, "full_name": str}]
upande_crm.api.activity.crm_my_calendars()                  -> [{"name": str, "calendar_name": str}]
```

---

### Task 1: Backend foundations — module, allowlists, picker helpers

**Files:**
- Create: `upande_crm/api/activity.py`
- Create: `upande_crm/tests/__init__.py`
- Create: `upande_crm/tests/test_activity.py`

**Interfaces:**
- Consumes: `_guard` from `upande_crm.api.crm`
- Produces: `TASK_REF_DOCTYPES`, `PARTICIPANT_DOCTYPES`, `MANAGER_ROLES`, `_is_manager()`, `_check_ref()`, `crm_assignable_users()`, `crm_my_calendars()`

- [ ] **Step 1: Write the failing test**

```python
# upande_crm/tests/test_activity.py
import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import activity


class TestActivityHelpers(FrappeTestCase):
    def test_allowlists_cover_crm_doctypes(self):
        for dt in ("Lead", "Opportunity", "Customer", "Prospect", "Quotation", "Contact", "Sales Order", "Event"):
            self.assertIn(dt, activity.TASK_REF_DOCTYPES)
        # Participants may additionally be people.
        self.assertIn("Employee", activity.PARTICIPANT_DOCTYPES)
        self.assertIn("User", activity.PARTICIPANT_DOCTYPES)

    def test_check_ref_rejects_off_allowlist(self):
        with self.assertRaises(frappe.PermissionError):
            activity._check_ref("Sales Invoice", activity.TASK_REF_DOCTYPES)
        with self.assertRaises(frappe.PermissionError):
            activity._check_ref("Animal Event", activity.TASK_REF_DOCTYPES)

    def test_check_ref_allows_allowlisted(self):
        activity._check_ref("Lead", activity.TASK_REF_DOCTYPES)  # must not raise

    def test_assignable_users_returns_crm_role_holders(self):
        users = activity.crm_assignable_users()
        self.assertTrue(all("name" in u and "full_name" in u for u in users))
        # Administrator holds System Manager, which is in CRM_ROLES.
        self.assertIn("Administrator", [u["name"] for u in users])

    def test_my_calendars_only_returns_authorized(self):
        for cal in activity.crm_my_calendars():
            doc = frappe.db.get_value(
                "Google Calendar", cal["name"], ["refresh_token", "google_calendar_id"], as_dict=True
            )
            self.assertTrue(doc.refresh_token)
            self.assertTrue(doc.google_calendar_id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site kaitet.local run-tests --app upande_crm`
Expected: FAIL — `ModuleNotFoundError: No module named 'upande_crm.api.activity'`

- [ ] **Step 3: Write minimal implementation**

```python
# upande_crm/api/activity.py
"""Whitelisted CRM *write* endpoints for Events and Tasks (ToDo).

Deliberately separate from `api/crm.py`. That module is a read layer whose house
style is defensive degradation — a missing doctype yields an empty chart rather
than an error. This module is the inverse: **every failure must surface.** A
swallowed exception here means a meeting or task the user believes they saved
was silently dropped. Never add a bare `except` around a write.

Design rule: delegate, don't reimplement.
  * assignment + `_assign` upkeep + notifications -> frappe.desk.form.assign_to
  * recurrence expansion for the calendar        -> frappe.desk.doctype.event.event.get_events
  * Google Calendar push, Meet links, repeat validation -> core Event controller
We own the role gate, the doctype allowlists, the completion rule, and the UI.
"""

import json

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime

from upande_crm.api.crm import CRM_ROLES, _guard

# Roles allowed to close a task that is not their own. A dashboard exists for
# oversight, so managers get an override on the desk assignee-only rule.
MANAGER_ROLES = {"System Manager", "Sales Manager", "CRM Manager"}

# What a CRM task may reference. `Event` is included because assigning an Event
# creates a ToDo pointing at it.
TASK_REF_DOCTYPES = {
    "Lead", "Opportunity", "Prospect", "Customer",
    "Quotation", "Contact", "Sales Order", "Event",
}

# Event participants may additionally be people.
PARTICIPANT_DOCTYPES = TASK_REF_DOCTYPES | {"Employee", "User"}

# Fields we accept from the client for each doctype. Anything else in the
# payload is dropped rather than written, so a crafted request cannot set
# `owner`, `docstatus`, or another app's custom field.
EVENT_FIELDS = {
    "subject", "event_category", "event_type", "starts_on", "ends_on", "all_day",
    "status", "description", "location", "color", "send_reminder",
    "repeat_this_event", "repeat_on", "repeat_till",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "sync_with_google_calendar", "google_calendar", "add_video_conferencing",
}
TASK_FIELDS = {
    "description", "date", "priority", "status", "color",
    "reference_type", "reference_name", "allocated_to",
}


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
    """Accept either a JSON string (form-encoded POST) or an already-parsed dict."""
    if isinstance(payload, str):
        payload = json.loads(payload or "{}")
    return payload or {}


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site kaitet.local run-tests --app upande_crm`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add upande_crm/api/activity.py upande_crm/tests/
git commit -m "feat(activity): CRM write-endpoint module with doctype allowlists and picker helpers"
```

---

### Task 2: Backend — Event save and status

**Files:**
- Modify: `upande_crm/api/activity.py`
- Modify: `upande_crm/tests/test_activity.py`

**Interfaces:**
- Consumes: `_guard`, `_check_ref`, `_pick`, `_load`, `EVENT_FIELDS`, `PARTICIPANT_DOCTYPES`, `crm_my_calendars` (Task 1)
- Produces: `crm_event_save(event) -> {"name": str}`, `crm_event_status(name, status) -> {"name": str, "status": str}`

- [ ] **Step 1: Write the failing test**

```python
class TestEventSave(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_create_event_minimal(self):
        r = activity.crm_event_save({
            "subject": "Test CRM meeting",
            "starts_on": "2026-08-01 10:00:00",
            "ends_on": "2026-08-01 11:00:00",
        })
        self.assertTrue(r["name"])
        doc = frappe.get_doc("Event", r["name"])
        self.assertEqual(doc.subject, "Test CRM meeting")
        self.assertEqual(doc.event_type, "Private")   # defaulted

    def test_ends_before_starts_is_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            activity.crm_event_save({
                "subject": "Backwards",
                "starts_on": "2026-08-01 11:00:00",
                "ends_on": "2026-08-01 10:00:00",
            })

    def test_subject_required(self):
        with self.assertRaises(frappe.ValidationError):
            activity.crm_event_save({"starts_on": "2026-08-01 10:00:00"})

    def test_participant_doctype_allowlisted(self):
        with self.assertRaises(frappe.PermissionError):
            activity.crm_event_save({
                "subject": "Bad participant",
                "starts_on": "2026-08-01 10:00:00",
                "participants": [{"reference_doctype": "Animal Event", "reference_docname": "x"}],
            })

    def test_update_event_replaces_participants(self):
        cust = frappe.get_all("Customer", limit=1)
        if not cust:
            self.skipTest("no Customer on site")
        r = activity.crm_event_save({
            "subject": "With participant",
            "starts_on": "2026-08-01 10:00:00",
            "participants": [{"reference_doctype": "Customer", "reference_docname": cust[0].name}],
        })
        doc = frappe.get_doc("Event", r["name"])
        self.assertEqual(len(doc.event_participants), 1)
        # Saving again with an empty list clears them.
        activity.crm_event_save({"name": r["name"], "subject": "With participant",
                                 "starts_on": "2026-08-01 10:00:00", "participants": []})
        doc.reload()
        self.assertEqual(len(doc.event_participants), 0)

    def test_sync_dropped_when_no_authorized_calendar(self):
        # Administrator has no authorized Google Calendar on this site.
        r = activity.crm_event_save({
            "subject": "No sync for me",
            "starts_on": "2026-08-01 10:00:00",
            "sync_with_google_calendar": 1,
            "google_calendar": "Nonexistent Calendar",
        })
        doc = frappe.get_doc("Event", r["name"])
        self.assertFalse(doc.sync_with_google_calendar)
        self.assertFalse(doc.google_calendar)

    def test_event_status_change(self):
        r = activity.crm_event_save({"subject": "To close", "starts_on": "2026-08-01 10:00:00"})
        activity.crm_event_status(r["name"], "Completed")
        self.assertEqual(frappe.db.get_value("Event", r["name"], "status"), "Completed")

    def test_event_status_rejects_unknown(self):
        r = activity.crm_event_save({"subject": "Bad status", "starts_on": "2026-08-01 10:00:00"})
        with self.assertRaises(frappe.ValidationError):
            activity.crm_event_status(r["name"], "Nonsense")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site kaitet.local run-tests --app upande_crm --module upande_crm.tests.test_activity`
Expected: FAIL — `AttributeError: module 'upande_crm.api.activity' has no attribute 'crm_event_save'`

- [ ] **Step 3: Write minimal implementation**

Append to `activity.py`:

```python
EVENT_STATUSES = {"Open", "Completed", "Closed", "Cancelled"}


@frappe.whitelist()
def crm_event_save(event):
    """Create or update an Event.

    Participants are replaced wholesale: the client always sends the full list,
    so removing a row client-side removes it here. Recurrence and Google fields
    are handed to the core controller, which owns their validation and push.
    """
    _guard()
    payload = _load(event)
    name = payload.get("name")
    fields = _pick(payload, EVENT_FIELDS)

    if not (fields.get("subject") or "").strip():
        frappe.throw(_("Subject is required"))
    if not fields.get("starts_on"):
        frappe.throw(_("A start date and time is required"))
    if fields.get("ends_on") and fields["ends_on"] < fields["starts_on"]:
        frappe.throw(_("End must be on or after the start"))

    fields.setdefault("event_type", "Private")
    fields.setdefault("status", "Open")

    # Google sync is only honoured when the user actually has an authorized
    # calendar. Otherwise we drop the request rather than create an Event that
    # is doomed to fail on push.
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
            doc.append("event_participants", {
                "reference_doctype": p["reference_doctype"],
                "reference_docname": p["reference_docname"],
            })

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site kaitet.local run-tests --app upande_crm --module upande_crm.tests.test_activity`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add upande_crm/api/activity.py upande_crm/tests/test_activity.py
git commit -m "feat(activity): Event create/update with participants, recurrence, guarded gcal sync"
```

---

### Task 3: Backend — Task save and the completion rule

**Files:**
- Modify: `upande_crm/api/activity.py`
- Modify: `upande_crm/tests/test_activity.py`

**Interfaces:**
- Consumes: `_guard`, `_check_ref`, `_pick`, `_load`, `TASK_FIELDS`, `TASK_REF_DOCTYPES`, `_is_manager` (Task 1)
- Produces: `crm_task_save(task) -> {"name": str}`, `crm_task_status(name, status) -> {"name": str, "status": str}`

- [ ] **Step 1: Write the failing test**

```python
class TestTaskSave(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_create_bare_task(self):
        r = activity.crm_task_save({"description": "Call the client", "priority": "High"})
        doc = frappe.get_doc("ToDo", r["name"])
        self.assertEqual(doc.priority, "High")
        self.assertEqual(doc.status, "Open")
        self.assertEqual(doc.assigned_by, frappe.session.user)

    def test_description_required(self):
        with self.assertRaises(frappe.ValidationError):
            activity.crm_task_save({"priority": "High"})

    def test_reference_type_allowlisted(self):
        with self.assertRaises(frappe.PermissionError):
            activity.crm_task_save({"description": "x", "reference_type": "Animal Event",
                                    "reference_name": "y"})

    def test_assignee_can_close_own_task(self):
        r = activity.crm_task_save({"description": "Mine to close",
                                    "allocated_to": frappe.session.user})
        activity.crm_task_status(r["name"], "Closed")
        self.assertEqual(frappe.db.get_value("ToDo", r["name"], "status"), "Closed")

    def test_manager_can_close_another_users_task(self):
        # Administrator holds System Manager, which is in MANAGER_ROLES.
        other = "Guest"
        r = activity.crm_task_save({"description": "Someone else's", "allocated_to": other})
        activity.crm_task_status(r["name"], "Closed")
        self.assertEqual(frappe.db.get_value("ToDo", r["name"], "status"), "Closed")

    def test_non_assignee_non_manager_is_refused(self):
        r = activity.crm_task_save({"description": "Not yours", "allocated_to": "Guest"})
        todo = frappe.get_doc("ToDo", r["name"])
        # Simulate a plain Sales User: assignee mismatch and no manager role.
        original = activity._is_manager
        activity._is_manager = lambda user=None: False
        try:
            frappe.set_user("Guest")  # not the assignee path we want; force mismatch
            with self.assertRaises(frappe.PermissionError):
                activity._assert_may_close(todo)
        finally:
            activity._is_manager = original
            frappe.set_user("Administrator")

    def test_task_status_rejects_unknown(self):
        r = activity.crm_task_save({"description": "Bad status"})
        with self.assertRaises(frappe.ValidationError):
            activity.crm_task_status(r["name"], "Nonsense")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site kaitet.local run-tests --app upande_crm --module upande_crm.tests.test_activity`
Expected: FAIL — no attribute `crm_task_save`

- [ ] **Step 3: Write minimal implementation**

Append to `activity.py`:

```python
TASK_STATUSES = {"Open", "Closed", "Cancelled"}


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
    payload = _load(task)
    name = payload.get("name")
    fields = _pick(payload, TASK_FIELDS)

    if not frappe.utils.strip_html(fields.get("description") or "").strip():
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site kaitet.local run-tests --app upande_crm --module upande_crm.tests.test_activity`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add upande_crm/api/activity.py upande_crm/tests/test_activity.py
git commit -m "feat(activity): ToDo create/update and completion rule with manager override"
```

---

### Task 4: Backend — assign and unassign

**Files:**
- Modify: `upande_crm/api/activity.py`
- Modify: `upande_crm/tests/test_activity.py`

**Interfaces:**
- Consumes: `_guard`, `_check_ref`, `TASK_REF_DOCTYPES` (Task 1)
- Produces: `crm_assign(doctype, name, assign_to, description=None, date=None, priority=None) -> {"assignees": [str]}`, `crm_unassign(doctype, name, assign_to) -> {"assignees": [str]}`

- [ ] **Step 1: Write the failing test**

```python
class TestAssign(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def _a_lead(self):
        rows = frappe.get_all("Lead", limit=1)
        if not rows:
            self.skipTest("no Lead on site")
        return rows[0].name

    def test_assign_creates_todo_and_stamps_assign(self):
        lead = self._a_lead()
        r = activity.crm_assign("Lead", lead, ["Administrator"], description="Follow up")
        self.assertIn("Administrator", r["assignees"])
        todo = frappe.get_all("ToDo", filters={"reference_type": "Lead", "reference_name": lead,
                                               "allocated_to": "Administrator", "status": "Open"})
        self.assertTrue(todo)
        self.assertIn("Administrator", frappe.db.get_value("Lead", lead, "_assign") or "")

    def test_unassign_clears_assign(self):
        lead = self._a_lead()
        activity.crm_assign("Lead", lead, ["Administrator"])
        activity.crm_unassign("Lead", lead, "Administrator")
        self.assertNotIn("Administrator", frappe.db.get_value("Lead", lead, "_assign") or "")

    def test_assign_rejects_off_allowlist_doctype(self):
        with self.assertRaises(frappe.PermissionError):
            activity.crm_assign("Sales Invoice", "x", ["Administrator"])

    def test_assign_requires_users(self):
        lead = self._a_lead()
        with self.assertRaises(frappe.ValidationError):
            activity.crm_assign("Lead", lead, [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site kaitet.local run-tests --app upande_crm --module upande_crm.tests.test_activity`
Expected: FAIL — no attribute `crm_assign`

- [ ] **Step 3: Write minimal implementation**

Append to `activity.py`:

```python
def _assignees(doctype, name):
    rows = frappe.get_all(
        "ToDo",
        filters={"reference_type": doctype, "reference_name": str(name),
                 "status": ["not in", ("Cancelled", "Closed")]},
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

    assign_add({
        "doctype": doctype,
        "name": name,
        "assign_to": users,
        "description": description or "",
        "priority": priority or "Medium",
        "date": date or None,
        "assigned_by": frappe.session.user,
    })
    return {"assignees": _assignees(doctype, name)}


@frappe.whitelist()
def crm_unassign(doctype, name, assign_to):
    """Remove one user's assignment from a record (core sets the ToDo Cancelled)."""
    _guard()
    _check_ref(doctype, TASK_REF_DOCTYPES)
    from frappe.desk.form.assign_to import remove as assign_remove

    assign_remove(doctype, name, assign_to)
    return {"assignees": _assignees(doctype, name)}
```

Note: `assign_add` receives `date: None` when unset; core defaults it to `nowdate()` only when the key is
absent, so pass `date or None` and let `args.get("date", nowdate())` handle it — confirm the ToDo lands with
today's date in the test above.

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site kaitet.local run-tests --app upande_crm --module upande_crm.tests.test_activity`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add upande_crm/api/activity.py upande_crm/tests/test_activity.py
git commit -m "feat(activity): assign/unassign delegating to frappe assign_to"
```

---

### Task 5: Backend — calendar window

**Files:**
- Modify: `upande_crm/api/activity.py`
- Modify: `upande_crm/tests/test_activity.py`

**Interfaces:**
- Consumes: `_guard` (Task 1)
- Produces: `crm_calendar(start, end) -> [{name, subject, starts_on, ends_on, all_day, status, event_category, color}]`

- [ ] **Step 1: Write the failing test**

```python
class TestCalendar(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_returns_event_in_window(self):
        r = activity.crm_event_save({"subject": "In window", "starts_on": "2026-08-15 09:00:00",
                                     "ends_on": "2026-08-15 10:00:00"})
        rows = activity.crm_calendar("2026-08-01", "2026-08-31")
        self.assertIn(r["name"], [x["name"] for x in rows])

    def test_excludes_event_outside_window(self):
        r = activity.crm_event_save({"subject": "Outside", "starts_on": "2026-12-15 09:00:00"})
        rows = activity.crm_calendar("2026-08-01", "2026-08-31")
        self.assertNotIn(r["name"], [x["name"] for x in rows])

    def test_expands_weekly_recurrence(self):
        # A weekly Saturday event starting 2026-08-01 (a Saturday) recurs across August.
        activity.crm_event_save({
            "subject": "Weekly standup", "starts_on": "2026-08-01 09:00:00",
            "ends_on": "2026-08-01 09:30:00",
            "repeat_this_event": 1, "repeat_on": "Weekly", "repeat_till": "2026-08-31",
            "saturday": 1,
        })
        rows = [x for x in activity.crm_calendar("2026-08-01", "2026-08-31")
                if x["subject"] == "Weekly standup"]
        # Core expands one occurrence per matching weekday, not a single row.
        self.assertGreater(len(rows), 1)

    def test_shape_has_required_keys(self):
        activity.crm_event_save({"subject": "Shape", "starts_on": "2026-08-10 09:00:00"})
        rows = activity.crm_calendar("2026-08-01", "2026-08-31")
        self.assertTrue(rows)
        for k in ("name", "subject", "starts_on", "status"):
            self.assertIn(k, rows[0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site kaitet.local run-tests --app upande_crm --module upande_crm.tests.test_activity`
Expected: FAIL — no attribute `crm_calendar`

- [ ] **Step 3: Write minimal implementation**

Append to `activity.py`:

```python
CALENDAR_KEYS = ("name", "subject", "starts_on", "ends_on", "all_day",
                 "status", "event_category", "color")


@frappe.whitelist()
def crm_calendar(start, end):
    """Events between `start` and `end`, with recurrences expanded.

    Wraps core's whitelisted `get_events`, which already handles Daily / Weekly
    (incl. per-weekday checks) / Monthly / Quarterly / Half Yearly / Yearly
    expansion. Writing that arithmetic here would duplicate ~80 lines of core
    logic and drift from what desk's calendar shows.

    The window is the month or week being viewed and is deliberately independent
    of the dashboard's date-range pill.
    """
    _guard()
    from frappe.desk.doctype.event.event import get_events

    rows = get_events(getdate(start), getdate(end))
    out = []
    for r in rows:
        out.append({k: r.get(k) for k in CALENDAR_KEYS})
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site kaitet.local run-tests --app upande_crm --module upande_crm.tests.test_activity`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add upande_crm/api/activity.py upande_crm/tests/test_activity.py
git commit -m "feat(activity): calendar window wrapping core get_events for recurrence expansion"
```

---

### Task 6: Read layer — CRM-scope the tasks and widen the fields

**Files:**
- Modify: `upande_crm/api/crm.py:406-441` (`crm_dashboard_events_tasks`)
- Modify: `upande_crm/tests/test_activity.py`

**Interfaces:**
- Consumes: `TASK_REF_DOCTYPES` (Task 1) — imported inside the function to avoid a circular import at module load, since `activity.py` imports `_guard` from `crm.py`.
- Produces: `crm_dashboard_events_tasks` returning `todos` scoped to CRM references, and Events carrying `ends_on`, `all_day`, `description`, `location`, `color`, plus `participants` per event.

- [ ] **Step 1: Write the failing test**

```python
class TestEventsTasksReader(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_todos_exclude_non_crm_reference_types(self):
        from upande_crm.api.crm import crm_dashboard_events_tasks

        data = crm_dashboard_events_tasks(date_from="2000-01-01", date_to="2100-01-01")
        seen = {t.get("reference_type") for t in data["todos"]}
        self.assertNotIn("Issue", seen)
        self.assertNotIn("Animal Event", seen)
        self.assertNotIn("Task", seen)

    def test_todos_keep_unlinked_tasks(self):
        from upande_crm.api.crm import crm_dashboard_events_tasks

        r = activity.crm_task_save({"description": "Bare task kept"})
        data = crm_dashboard_events_tasks(date_from="2000-01-01", date_to="2100-01-01")
        self.assertIn(r["name"], [t["name"] for t in data["todos"]])

    def test_events_carry_form_fields(self):
        from upande_crm.api.crm import crm_dashboard_events_tasks

        activity.crm_event_save({"subject": "Fields check", "starts_on": "2026-08-05 09:00:00",
                                 "ends_on": "2026-08-05 10:00:00", "location": "Nairobi"})
        data = crm_dashboard_events_tasks(date_from="2026-08-01", date_to="2026-08-31")
        row = next(e for e in data["events"] if e["subject"] == "Fields check")
        for k in ("ends_on", "all_day", "location", "description"):
            self.assertIn(k, row)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site kaitet.local run-tests --app upande_crm --module upande_crm.tests.test_activity`
Expected: FAIL — Issue/Task reference types still present; `location` missing from event rows

- [ ] **Step 3: Write minimal implementation**

Replace the `todos` and `events` blocks in `crm_dashboard_events_tasks`. The ToDo filter needs an OR
between "reference_type in the allowlist" and "reference_type is null", which a filters-dict cannot
express, so use an explicit `or_filters`-style two-part fetch via `frappe.get_all` with a list filter:

```python
    # Tasks are scoped to CRM work. The site's ToDo table is dominated by other
    # apps (Issue, Task, Animal Event); showing all of them made this view ~96%
    # noise. Unlinked personal tasks are kept.
    from upande_crm.api.activity import TASK_REF_DOCTYPES

    todo_filters = {**tdo, "status": "Open"}
    todos = []
    if _has("ToDo"):
        cols = set(frappe.db.get_table_columns("ToDo"))
        tfields = [f for f in ("name", "description", "priority", "allocated_to", "owner",
                              "_assign", "status", "reference_type", "reference_name",
                              "date", "assigned_by", "color") if f in cols or f == "name"]
        try:
            todos = frappe.get_all(
                "ToDo",
                fields=tfields,
                filters={**todo_filters, "reference_type": ["in", sorted(TASK_REF_DOCTYPES)]},
                order_by="creation desc", limit=300,
            ) + frappe.get_all(
                "ToDo",
                fields=tfields,
                filters={**todo_filters, "reference_type": ["is", "not set"]},
                order_by="creation desc", limit=100,
            )
        except Exception:
            todos = []
```

and widen the Event fetch:

```python
        "events": _rows("Event", [
            "name", "subject", "event_category", "event_type", "starts_on", "ends_on",
            "all_day", "status", "description", "location", "color",
            "repeat_this_event", "repeat_on", "repeat_till",
            "sync_with_google_calendar", "google_calendar",
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
            "owner", "_assign",
        ], filters=ev, order_by="starts_on desc", limit=300),
```

Then attach participants in one extra query rather than N:

```python
    ev_names = [e["name"] for e in events_rows]
    parts = {}
    if ev_names and _has("Event Participants"):
        try:
            for p in frappe.get_all("Event Participants",
                                    filters={"parent": ["in", ev_names]},
                                    fields=["parent", "reference_doctype", "reference_docname"]):
                parts.setdefault(p.parent, []).append(
                    {"reference_doctype": p.reference_doctype, "reference_docname": p.reference_docname})
        except Exception:
            parts = {}
    for e in events_rows:
        e["participants"] = parts.get(e["name"], [])
```

Also update the `tasks_open` / `tasks_high` KPIs to use the same CRM scope so the numbers match the list.

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site kaitet.local run-tests --app upande_crm --module upande_crm.tests.test_activity`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add upande_crm/api/crm.py upande_crm/tests/test_activity.py
git commit -m "fix(crm): scope dashboard tasks to CRM references and widen event fields"
```

---

### Task 7: Frontend — endpoint wrappers and store actions

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/store.js`

**Interfaces:**
- Consumes: every endpoint from Tasks 1-5
- Produces store actions: `saveEvent(payload)`, `setEventStatus(name, status)`, `saveTask(payload)`, `setTaskStatus(name, status)`, `assign(doctype, name, users, opts)`, `unassign(doctype, name, user)`, `reloadSection(key)`, `loadCalendar(monthStartISO)`, and state `calMonth`, `calRows`, `calLoading`, `eventDialog`, `taskDialog`, plus `openEventDialog(ev)`, `closeEventDialog()`, `openTaskDialog(t)`, `closeTaskDialog()`

- [ ] **Step 1: Add the wrappers to `api.js`**

```js
const A = 'upande_crm.api.activity.';
export const saveEventApi      = (payload) => api(A + 'crm_event_save', { event: JSON.stringify(payload) });
export const eventStatusApi    = (name, status) => api(A + 'crm_event_status', { name, status });
export const saveTaskApi       = (payload) => api(A + 'crm_task_save', { task: JSON.stringify(payload) });
export const taskStatusApi     = (name, status) => api(A + 'crm_task_status', { name, status });
export const assignApi         = (doctype, name, users, o = {}) => api(A + 'crm_assign', {
  doctype, name, assign_to: JSON.stringify(users),
  description: o.description || '', date: o.date || '', priority: o.priority || 'Medium',
});
export const unassignApi       = (doctype, name, assign_to) => api(A + 'crm_unassign', { doctype, name, assign_to });
export const calendarApi       = (start, end) => api(A + 'crm_calendar', { start, end });
export const assignableUsersApi = () => api(A + 'crm_assignable_users', {});
export const myCalendarsApi    = () => api(A + 'crm_my_calendars', {});
```

- [ ] **Step 2: Add the store slice and actions to `store.js`**

```js
  // dialogs: null = closed, object = open (empty object = create mode)
  eventDialog: null,
  taskDialog: null,
  // calendar owns its own month, independent of the header date-range pill
  calMonth: null,
  calRows: [],
  calLoading: false,

  openEventDialog(ev = {}) { set({ eventDialog: ev }); },
  closeEventDialog() { set({ eventDialog: null }); },
  openTaskDialog(t = {}) { set({ taskDialog: t }); },
  closeTaskDialog() { set({ taskDialog: null }); },

  // Refetch one section rather than the whole dashboard after a write.
  async reloadSection(key) {
    const loader = SECTION_LOADERS[key];
    if (!loader) return;
    const args = { date_from: get().dateFrom, date_to: get().dateTo };
    if (get().customerFilter) args.customer = get().customerFilter;
    try {
      const v = await loader(args);
      if (v && !v.error) set({ data: { ...get().data, [key]: v }, lastUpdated: new Date() });
    } catch {}
  },

  async saveEvent(payload) {
    const r = await saveEventApi(payload);
    await get().reloadSection('evt');
    if (get().calMonth) await get().loadCalendar(get().calMonth);
    return r;
  },

  async saveTask(payload) {
    const r = await saveTaskApi(payload);
    await get().reloadSection('evt');
    return r;
  },

  // Optimistic: flip the row locally, revert if the server refuses. Mirrors the
  // markRead/toggleStar pattern already used for mail.
  async setTaskStatus(name, status) {
    const E = get().data.evt;
    const prev = E?.todos?.find((t) => t.name === name)?.status;
    if (E?.todos) {
      set({ data: { ...get().data, evt: { ...E,
        todos: E.todos.map((t) => (t.name === name ? { ...t, status } : t)) } } });
    }
    try {
      await taskStatusApi(name, status);
      await get().reloadSection('evt');
    } catch (e) {
      const cur = get().data.evt;
      if (cur?.todos && prev) {
        set({ data: { ...get().data, evt: { ...cur,
          todos: cur.todos.map((t) => (t.name === name ? { ...t, status: prev } : t)) } } });
      }
      throw e;
    }
  },

  async setEventStatus(name, status) {
    await eventStatusApi(name, status);
    await get().reloadSection('evt');
    if (get().calMonth) await get().loadCalendar(get().calMonth);
  },

  async assign(doctype, name, users, opts) {
    const r = await assignApi(doctype, name, users, opts);
    await get().reloadSection('evt');
    return r;
  },

  async unassign(doctype, name, user) {
    const r = await unassignApi(doctype, name, user);
    await get().reloadSection('evt');
    return r;
  },

  async loadCalendar(monthStart) {
    const d = new Date(monthStart + 'T00:00:00');
    const start = new Date(d.getFullYear(), d.getMonth(), 1);
    const end = new Date(d.getFullYear(), d.getMonth() + 1, 0);
    const iso = (x) => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`;
    set({ calLoading: true, calMonth: iso(start) });
    try {
      const rows = await calendarApi(iso(start), iso(end));
      set({ calRows: rows || [], calLoading: false });
    } catch {
      set({ calRows: [], calLoading: false });
    }
  },
```

- [ ] **Step 3: Verify the bundle still builds**

Run: `cd frontend && yarn build`
Expected: build succeeds, no unresolved imports

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api.js frontend/src/store.js
git commit -m "feat(crm-ui): activity endpoint wrappers and Event/Task store actions"
```

---

### Task 8: Frontend — form primitives and LinkSearch

**Files:**
- Create: `frontend/src/components/ui/textarea.jsx`
- Create: `frontend/src/components/ui/checkbox.jsx`
- Create: `frontend/src/components/LinkSearch.jsx`

**Interfaces:**
- Produces: `<Textarea />`, `<Checkbox checked onCheckedChange label />`, `<LinkSearch doctype value onChange placeholder />` (calls `frappe.desk.search.search_link`, 250 ms debounce, keyboard up/down/enter/escape)

- [ ] **Step 1: Write `textarea.jsx`**

```jsx
import * as React from 'react';
import { cn } from '@/lib/utils';

const Textarea = React.forwardRef(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      'flex min-h-[72px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
      className,
    )}
    {...props}
  />
));
Textarea.displayName = 'Textarea';

export { Textarea };
```

- [ ] **Step 2: Write `checkbox.jsx`** — native input, deliberately no new Radix dependency

```jsx
import { cn } from '@/lib/utils';

// Native checkbox, styled. Avoids adding @radix-ui/react-checkbox: vite.config.js
// documents that growing the vendor chunk here has caused blank-screen crashes.
export function Checkbox({ checked, onCheckedChange, label, className, disabled }) {
  return (
    <label className={cn('inline-flex items-center gap-2 text-[13px] text-ink-2 select-none', disabled && 'opacity-50', className)}>
      <input
        type="checkbox"
        checked={!!checked}
        disabled={disabled}
        onChange={(e) => onCheckedChange?.(e.target.checked)}
        className="h-3.5 w-3.5 rounded border-input accent-[var(--gold)] cursor-pointer"
      />
      {label}
    </label>
  );
}
```

- [ ] **Step 3: Write `LinkSearch.jsx`**

```jsx
import { useEffect, useRef, useState } from 'react';
import { api } from '@shared/api';
import { cn } from '@/lib/utils';
import Icon from './Icon';

// Debounced combobox over Frappe's whitelisted link search. Used for event
// participants, task references, and the user picker — and reused by the
// WhatsApp section for contact lookup.
export default function LinkSearch({ doctype, value, onChange, placeholder = 'Search…', className, disabled }) {
  const [q, setQ] = useState('');
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0);
  const box = useRef(null);

  useEffect(() => {
    function onDoc(e) { if (box.current && !box.current.contains(e.target)) setOpen(false); }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  useEffect(() => {
    if (!open || !doctype) return;
    const t = setTimeout(async () => {
      try {
        const r = await api('frappe.desk.search.search_link', { doctype, txt: q, page_length: 10 });
        setRows(Array.isArray(r) ? r : (r?.results || []));
        setHi(0);
      } catch { setRows([]); }
    }, 250);
    return () => clearTimeout(t);
  }, [q, doctype, open]);

  function pick(r) {
    onChange?.(r.value, r);
    setQ('');
    setOpen(false);
  }

  function onKey(e) {
    if (!open) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setHi((h) => Math.min(h + 1, rows.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHi((h) => Math.max(h - 1, 0)); }
    else if (e.key === 'Enter' && rows[hi]) { e.preventDefault(); pick(rows[hi]); }
    else if (e.key === 'Escape') { setOpen(false); }
  }

  return (
    <div className={cn('relative', className)} ref={box}>
      <div className="flex items-center gap-1.5 rounded-md border border-input px-2.5 h-9">
        <Icon name="search" className="text-[15px] text-ink-mute" />
        <input
          disabled={disabled}
          value={open ? q : (value || '')}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKey}
          placeholder={placeholder}
          className="flex-1 bg-transparent outline-none text-sm min-w-0"
        />
        {value && !open && (
          <button type="button" onClick={() => onChange?.('', null)} className="text-ink-3 hover:text-bad" title="Clear">
            <Icon name="close" className="text-[15px]" />
          </button>
        )}
      </div>
      {open && rows.length > 0 && (
        <div className="absolute z-50 mt-1 w-full max-h-60 overflow-y-auto rounded-md border border-line bg-surface shadow-lg">
          {rows.map((r, i) => (
            <button
              type="button"
              key={r.value}
              onMouseEnter={() => setHi(i)}
              onClick={() => pick(r)}
              className={cn('w-full text-left px-3 py-2 text-[13px]', i === hi ? 'bg-hover' : '')}
            >
              <div className="text-ink truncate">{r.value}</div>
              {r.description && <div className="text-[11px] text-ink-mute truncate">{r.description}</div>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Verify the build**

Run: `cd frontend && yarn build`
Expected: success

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/textarea.jsx frontend/src/components/ui/checkbox.jsx frontend/src/components/LinkSearch.jsx
git commit -m "feat(crm-ui): textarea, checkbox, and reusable LinkSearch combobox"
```

---

### Task 9: Frontend — EventDialog

**Files:**
- Create: `frontend/src/components/EventDialog.jsx`

**Interfaces:**
- Consumes: `useStore().eventDialog`, `saveEvent`, `closeEventDialog`, `myCalendarsApi` (Task 7); `Textarea`, `Checkbox`, `LinkSearch` (Task 8)
- Produces: a modal that saves an Event. Create mode when `eventDialog` is `{}`; edit mode when it carries a `name`.

Field set: subject (required), event_category, event_type, starts_on, ends_on, all_day, status,
location, description, participants (add/remove rows via `LinkSearch` over a doctype `Select`), and a
collapsed Repeat block (`repeat_this_event` → `repeat_on`, `repeat_till`, weekday checkboxes when Weekly).
The Google sync block renders only when `myCalendarsApi()` returns at least one calendar.

- [ ] **Step 1: Write the component**

Follow the `ComposeDialog.jsx` chrome conventions: fixed overlay, `bg-grad-ink` header bar, `border-hairline`
panel, footer with a gold primary button and a status line. Key logic:

```jsx
const [form, setForm] = useState({});
const [parts, setParts] = useState([]);
const [cals, setCals] = useState([]);
const [err, setErr] = useState('');
const [saving, setSaving] = useState(false);

useEffect(() => {
  if (!ev) return;
  setForm({
    name: ev.name, subject: ev.subject || '', event_category: ev.event_category || 'Meeting',
    event_type: ev.event_type || 'Private', starts_on: toLocalInput(ev.starts_on),
    ends_on: toLocalInput(ev.ends_on), all_day: ev.all_day || 0, status: ev.status || 'Open',
    location: ev.location || '', description: stripHtml(ev.description || ''),
    repeat_this_event: ev.repeat_this_event || 0, repeat_on: ev.repeat_on || 'Weekly',
    repeat_till: ev.repeat_till || '',
    monday: ev.monday||0, tuesday: ev.tuesday||0, wednesday: ev.wednesday||0, thursday: ev.thursday||0,
    friday: ev.friday||0, saturday: ev.saturday||0, sunday: ev.sunday||0,
    sync_with_google_calendar: ev.sync_with_google_calendar || 0,
    google_calendar: ev.google_calendar || '', add_video_conferencing: ev.add_video_conferencing || 0,
  });
  setParts(ev.participants || []);
  setErr('');
  myCalendarsApi().then((c) => setCals(c || [])).catch(() => setCals([]));
}, [ev]);

async function submit() {
  if (!form.subject.trim()) { setErr('Subject is required.'); return; }
  if (!form.starts_on) { setErr('Pick a start date and time.'); return; }
  if (form.ends_on && form.ends_on < form.starts_on) { setErr('End must be on or after the start.'); return; }
  setSaving(true); setErr('');
  try {
    await saveEvent({ ...form,
      starts_on: fromLocalInput(form.starts_on),
      ends_on: form.ends_on ? fromLocalInput(form.ends_on) : null,
      description: form.description ? `<div>${escapeHtml(form.description).replace(/\n/g, '<br>')}</div>` : '',
      participants: parts });
    closeEventDialog();
  } catch (e) { setErr(e.message || 'Could not save the event.'); }
  finally { setSaving(false); }
}
```

Helpers local to this file — `datetime-local` inputs need `YYYY-MM-DDTHH:mm` while Frappe stores
`YYYY-MM-DD HH:mm:ss`:

```jsx
function toLocalInput(s) { return s ? String(s).replace(' ', 'T').slice(0, 16) : ''; }
function fromLocalInput(s) { return s ? s.replace('T', ' ') + ':00' : null; }
function stripHtml(s) { return String(s || '').replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, '').trim(); }
function escapeHtml(s) { return String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c])); }
```

Participants row UI: a `Select` of `PARTICIPANT_DOCTYPES` labels (Customer, Lead, Opportunity, Prospect,
Contact, Quotation, Sales Order, Employee, User) plus a `LinkSearch` bound to it; an "Add participant"
button appends `{reference_doctype, reference_docname}`; each row has a remove button.

- [ ] **Step 2: Build and verify**

Run: `cd frontend && yarn build`
Expected: success

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/EventDialog.jsx
git commit -m "feat(crm-ui): Event create/edit dialog with participants, repeat, and gcal sync"
```

---

### Task 10: Frontend — TaskDialog

**Files:**
- Create: `frontend/src/components/TaskDialog.jsx`

**Interfaces:**
- Consumes: `useStore().taskDialog`, `saveTask`, `closeTaskDialog`, `assignableUsersApi`; `Textarea`, `LinkSearch`
- Produces: a modal that saves a ToDo. Fields: description (required), date, priority, status, reference_type + reference_name, allocated_to.

`allocated_to` is a plain `Select` over `assignableUsersApi()` — **not** an assign action. Per the spec, a
task's own assignee is its `allocated_to` field; routing it through assignment would create a second ToDo
pointing at the first.

- [ ] **Step 1: Write the component**

Same dialog chrome as Task 9. Submit:

```jsx
async function submit() {
  if (!form.description.trim()) { setErr('Description is required.'); return; }
  if (form.reference_type && !form.reference_name) { setErr('Pick the linked record, or clear the reference type.'); return; }
  setSaving(true); setErr('');
  try {
    await saveTask({ ...form,
      description: `<div>${escapeHtml(form.description).replace(/\n/g, '<br>')}</div>` });
    closeTaskDialog();
  } catch (e) { setErr(e.message || 'Could not save the task.'); }
  finally { setSaving(false); }
}
```

Reference type options: the eight `TASK_REF_DOCTYPES` values, plus a blank "— none —" entry that clears
both reference fields.

- [ ] **Step 2: Build and verify**

Run: `cd frontend && yarn build`
Expected: success

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TaskDialog.jsx
git commit -m "feat(crm-ui): Task create/edit dialog"
```

---

### Task 11: Frontend — AssignControl

**Files:**
- Create: `frontend/src/components/AssignControl.jsx`

**Interfaces:**
- Consumes: `assignableUsersApi`, `useStore().assign`, `unassign`; `FilterPopover`
- Produces: `<AssignControl doctype name assigned={[emails]} />` — shows current assignees as removable chips and a picker to add more.

`assigned` is parsed from the row's `_assign` JSON-array string by the caller.

- [ ] **Step 1: Write the component**

```jsx
import { useEffect, useState } from 'react';
import FilterPopover from './FilterPopover';
import Icon from './Icon';
import { useStore } from '../store';
import { assignableUsersApi } from '../api';
import { shortUser } from '@/lib/crm';

export function parseAssign(v) {
  try { const a = JSON.parse(v || '[]'); return Array.isArray(a) ? a : []; } catch { return []; }
}

export default function AssignControl({ doctype, name, assigned = [] }) {
  const assign = useStore((s) => s.assign);
  const unassign = useStore((s) => s.unassign);
  const [users, setUsers] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => { assignableUsersApi().then((u) => setUsers(u || [])).catch(() => setUsers([])); }, []);

  async function add(u, close) {
    setBusy(true); setErr('');
    try { await assign(doctype, name, [u]); close(); }
    catch (e) { setErr(e.message || 'Could not assign'); }
    finally { setBusy(false); }
  }

  async function drop(u) {
    setBusy(true); setErr('');
    try { await unassign(doctype, name, u); }
    catch (e) { setErr(e.message || 'Could not unassign'); }
    finally { setBusy(false); }
  }

  const free = users.filter((u) => !assigned.includes(u.name));

  return (
    <div className="flex items-center gap-1 flex-wrap" onClick={(e) => e.stopPropagation()}>
      {assigned.map((u) => (
        <span key={u} className="bdg bdg-other inline-flex items-center gap-1 normal-case">
          {shortUser(u)}
          <button disabled={busy} onClick={() => drop(u)} className="hover:text-bad" title={`Unassign ${u}`}>
            <Icon name="close" className="text-[12px]" />
          </button>
        </span>
      ))}
      <FilterPopover width={240} trigger={
        <button className="text-ink-3 hover:text-gold-text" title="Assign a user">
          <Icon name="person_add" className="text-[16px]" />
        </button>
      }>
        {({ close }) => (
          <div className="grid gap-1 max-h-64 overflow-y-auto">
            <div className="text-[10px] uppercase tracking-wide text-ink-mute font-medium">Assign to</div>
            {err && <div className="text-[11px] text-bad">{err}</div>}
            {free.length ? free.map((u) => (
              <button key={u.name} disabled={busy} onClick={() => add(u.name, close)}
                className="text-left text-[13px] px-2 py-1.5 rounded-lg hover:bg-hover truncate">
                {u.full_name}<span className="text-ink-mute text-[11px] block">{u.name}</span>
              </button>
            )) : <div className="text-[12px] text-ink-mute px-2 py-1.5">Everyone is already assigned</div>}
          </div>
        )}
      </FilterPopover>
    </div>
  );
}
```

- [ ] **Step 2: Build and verify**

Run: `cd frontend && yarn build`
Expected: success

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AssignControl.jsx
git commit -m "feat(crm-ui): assign/unassign control with removable assignee chips"
```

---

### Task 12: Frontend — split the Events section, add row actions

**Files:**
- Create: `frontend/src/sections/Events/index.jsx`
- Create: `frontend/src/sections/Events/Dashboard.jsx`
- Create: `frontend/src/sections/Events/EventsTable.jsx`
- Create: `frontend/src/sections/Events/TasksTable.jsx`
- Delete: `frontend/src/sections/Events.jsx`

**Interfaces:**
- Consumes: `EventDialog`, `TaskDialog`, `AssignControl`/`parseAssign`, store actions
- Produces: `default export Events` routing on `table` — `''` → Dashboard, `events`/`mine_events` → EventsTable, `todos`/`mine_todos` → TasksTable, `calendar` → Calendar (Task 13), `emails` → existing `EmailsTable`

`Dashboard.jsx` is the current KPI + charts body moved verbatim from `Events.jsx`, plus "New Event" and
"New Task" buttons wired to `openEventDialog({})` / `openTaskDialog({})`.

`EventsTable.jsx` keeps the existing columns and adds an actions column: edit (opens `EventDialog` with the
row), mark complete (`setEventStatus(name, 'Completed')`, hidden when already Completed/Closed), and
`AssignControl` for `doctype="Event"`.

`TasksTable.jsx` keeps the existing columns and adds: a complete checkbox calling
`setTaskStatus(name, 'Closed')`, an edit button, a due-date column, and `AssignControl` on the referenced
record when the task has one. Because a table row is clickable (it opens the desk record), every action
control must call `e.stopPropagation()`.

- [ ] **Step 1: Create the four files, moving the existing dashboard body unchanged**

- [ ] **Step 2: Delete the old section file**

```bash
git rm frontend/src/sections/Events.jsx
```

- [ ] **Step 3: Update the lazy import in `App.jsx`**

```jsx
const Events = lazy(() => import('./sections/Events/index.jsx'));
```

and register the dialogs beside `ComposeDialog`:

```jsx
const EventDialog = lazy(() => import('./components/EventDialog'));
const TaskDialog = lazy(() => import('./components/TaskDialog'));
// …inside the trailing <Suspense>
<EventDialog />
<TaskDialog />
```

- [ ] **Step 4: Build and verify**

Run: `cd frontend && yarn build`
Expected: success

- [ ] **Step 5: Commit**

```bash
git add -A frontend/src/sections frontend/src/App.jsx
git commit -m "feat(crm-ui): split Events section into focused components with row actions"
```

---

### Task 13: Frontend — Calendar

**Files:**
- Create: `frontend/src/sections/Events/Calendar.jsx`
- Modify: `frontend/src/nav.js`

**Interfaces:**
- Consumes: `loadCalendar`, `calRows`, `calMonth`, `calLoading`, `openEventDialog`
- Produces: a month grid with a week strip toggle. Clicking a day opens `EventDialog` prefilled with that
  date at 09:00; clicking an event opens it for edit.

- [ ] **Step 1: Write the component**

CSS-grid month view, 7 columns. Key structure:

```jsx
const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function monthMatrix(monthStart) {
  const d = new Date(monthStart + 'T00:00:00');
  const first = new Date(d.getFullYear(), d.getMonth(), 1);
  // Monday-first offset
  const lead = (first.getDay() + 6) % 7;
  const days = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < lead; i++) cells.push(null);
  for (let i = 1; i <= days; i++) cells.push(new Date(d.getFullYear(), d.getMonth(), i));
  while (cells.length % 7) cells.push(null);
  return cells;
}
```

Group `calRows` by `starts_on.slice(0,10)` into a map, render up to three chips per day with a
"+N more" affordance, and colour each chip by `event_category` using the existing `PAL` palette. Header
carries ‹ / › month navigation calling `loadCalendar` with the shifted month, a "Today" button, and the
month label. Mount effect:

```jsx
useEffect(() => { if (!calMonth) loadCalendar(todayISO()); }, [calMonth, loadCalendar]);
```

- [ ] **Step 2: Add the nav entry** — in `nav.js`, inside the Events & Tasks group's `subs`, after
`{ table: '', label: 'Dashboard' }`:

```js
{ table: 'calendar', label: 'Calendar' },
```

- [ ] **Step 3: Build and verify**

Run: `cd frontend && yarn build`
Expected: success

- [ ] **Step 4: Commit**

```bash
git add frontend/src/sections/Events/Calendar.jsx frontend/src/nav.js
git commit -m "feat(crm-ui): hand-rolled month calendar with its own month navigation"
```

---

### Task 14: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the whole backend suite**

Run: `bench --site kaitet.local run-tests --app upande_crm`
Expected: all tests pass, zero failures/errors

- [ ] **Step 2: Rebuild the frontend**

Run: `cd frontend && yarn build`
Expected: success; `upande_crm/www/customer-relationship-management.html` regenerated

- [ ] **Step 3: Confirm the page still serves**

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8002/customer-relationship-management`
Expected: `403` unauthenticated (the role gate), i.e. the route resolves rather than 404/500

- [ ] **Step 4: Check the built bundle has no chunk cycle**

Confirm the emitted `assets/` contains exactly one `react-*.js` and one `vendor-*.js`, matching the
`manualChunks` contract in `vite.config.js`. A third library chunk means the splitting rule was violated
and risks the documented blank-screen crash.

- [ ] **Step 5: Commit any regenerated build artefacts**

```bash
git add upande_crm/public/frontend upande_crm/www/customer-relationship-management.html
git commit -m "build: rebuild CRM bundle with Events & Tasks management"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| Create/edit Events incl. category, type, start/end, all-day, status, description, location | 2, 9 |
| Participants | 2, 9 |
| Recurrence | 2, 9 |
| Google Calendar sync, hidden without an authorized calendar | 1, 2, 9 |
| Create/edit Tasks | 3, 10 |
| Assign / unassign | 4, 11 |
| Mark complete + desk rule + manager override | 3, 12 |
| Month/week calendar | 5, 13 |
| CRM-scoped task list | 6 |
| New `api/activity.py`, reads-degrade/writes-throw split | 1 |
| Doctype allowlists | 1 |
| Real Frappe permissions, no `ignore_permissions` | 1-4 |
| `LinkSearch` reusable by spec 3 | 8 |
| Hand-rolled calendar, no new deps | 8, 13 |
| Calendar independent of the date pill | 7, 13 |
| Optimistic update with rollback | 7 |
| First tests in the app | 1-6 |
| Error handling: inline + banner | 9, 10, 11 |

No gaps.

**Placeholder scan:** none — every code step carries real code; no "TBD", no "add error handling".

**Type consistency:** `crm_event_save`/`crm_task_save` return `{"name"}` and the store's `saveEvent`/`saveTask`
consume exactly that. `crm_assign`/`crm_unassign` return `{"assignees": [...]}`; `AssignControl` re-reads
assignees from the reloaded section rather than the return value, so the shape is only informational — noted
so no later task assumes otherwise. `parseAssign` is exported from `AssignControl.jsx` and imported by
`EventsTable`/`TasksTable` in Task 12. `_assert_may_close` is defined in Task 3 and referenced by that
task's own test only.
