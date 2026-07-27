# CRM Events & Tasks — Design

**Date:** 2026-07-27
**Status:** Approved design, ready for implementation planning
**Scope:** Spec 1 of 3. Siblings: sales analytics on Overview (spec 2), WhatsApp integration (spec 3).

## Problem

`upande_crm`'s Events section is read-only. It renders tables and charts, and every row
deep-links out to the Frappe desk. A sales user cannot create a meeting, raise a task,
assign work, or tick something off without leaving the CRM.

Two concrete defects make the current view worse than it looks:

1. **Task noise.** `crm_dashboard_events_tasks` returns every open ToDo on the site.
   Of 2,420 open ToDos, only 57 are CRM-related (Lead 33, Customer 27, Sales Order 3,
   unlinked 3). The rest are Issue (1,254), Task (880), and Animal Event (543)
   assignments belonging to other apps. The CRM task list is ~96% irrelevant rows.

2. **Wrong linkage assumption.** The reader exposes `Event.reference_doctype`, but all
   170 Events on the site have it empty. Real CRM linkage lives in the
   `Event Participants` child table: Customer 144, Employee 81, Lead 15, Prospect 11,
   User 4, Opportunity 3, Contact 1.

## Goals

Desk-equivalent Event and Task management inside the CRM SPA:

- Create and edit Events: subject, category, type, start/end, all-day, status,
  description, location, participants, recurrence, Google Calendar sync.
- Create and edit Tasks (ToDo): description, due date, priority, status, CRM reference.
- Assign Events and Tasks to users; unassign.
- Mark complete, honouring desk's assignee rule plus a manager override.
- A month/week calendar view of Events.
- Scope the task list to CRM work.

### Non-goals

Event attachments and comments; bulk task operations; a frontend test runner;
WhatsApp (spec 3); sales analytics (spec 2).

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Task list scope | CRM-referenced + unlinked only | Removes the 96% noise. CRM section stays about CRM. |
| Event↔CRM linkage | `Event Participants` | Matches the 259 participant rows already on the site; `reference_doctype` is unused. |
| Completion rule | Desk rule + manager override | Assignees close their own work; managers get oversight, which is a dashboard's purpose. |
| Write permissions | Real Frappe permissions | Writes must not grant access the user lacks. Differs deliberately from the read dashboards, which bypass record-level perms by design. |
| Recurrence | Included | Core already implements it end to end; cost is form fields only, not logic. |
| Calendar | Hand-rolled | Avoids the vendor-chunk hazard documented in `vite.config.js`. |

## Architecture

### Why a new module

Write endpoints go in a **new `upande_crm/api/activity.py`**, not into `api/crm.py`.

`crm.py` is 680 lines whose entire house style is defensive degradation — `_has`,
`_hascol`, `except: return 0`. That is correct for dashboard reads: a missing doctype
should render an empty chart, not a stack trace. It is actively dangerous for writes,
where a swallowed exception means silent data loss. Separate modules make
**"reads degrade, writes fail loudly"** a structural property rather than a convention
someone must remember.

Rejected alternative: calling `frappe.client.insert`/`set_value` from the SPA with no new
backend. That has no doctype allowlist, cannot express the manager-override rule, and
cannot wrap `assign_to`, so notifications and `_assign` would drift out of sync.

### Guiding principle: delegate, don't reimplement

| Concern | Owner |
|---|---|
| Assignment, `_assign` upkeep, notifications | `frappe.desk.form.assign_to` |
| Recurrence expansion for the calendar | `frappe.desk.doctype.event.event.get_events` (whitelisted; expands Daily/Weekly/Monthly/Quarterly/Half Yearly/Yearly, including Weekly weekday checks) |
| Google Calendar push, Meet links | Core `Event` controller + Google Calendar integration |
| Participant validation, repeat validation | Core `Event` controller |
| Link search for pickers | `frappe.desk.search.search_link` (whitelisted) |

We own: the CRM role gate, the doctype allowlist, the completion rule, CRM-scoped
queries, and the UI.

### Endpoints — `upande_crm/api/activity.py`

| Endpoint | Behaviour |
|---|---|
| `crm_event_save(event)` | Create or update an Event. JSON payload. Participants replaced wholesale; repeat and gcal fields passed to core. |
| `crm_event_status(name, status)` | Set Open / Completed / Closed / Cancelled. |
| `crm_task_save(task)` | Create or update a ToDo. |
| `crm_task_status(name, status)` | Complete/reopen/cancel under the completion rule below. |
| `crm_assign(doctype, name, assign_to, description=None, date=None, priority=None)` | Wraps `assign_to.add`. |
| `crm_unassign(doctype, name, assign_to)` | Wraps `assign_to.remove`. |
| `crm_calendar(start, end)` | Wraps core `get_events`; returns occurrences for a month/week window. |
| `crm_assignable_users()` | Enabled users holding a role in `CRM_ROLES`. |
| `crm_my_calendars()` | Current user's Google Calendars having both `refresh_token` and `google_calendar_id`. |

### Assignment semantics

Desk uses one mechanism for two user-facing concepts, so the spec states both explicitly:

- **Assigning an Event** (or any CRM record) means `crm_assign` → `assign_to.add`, which
  creates a ToDo with `reference_type` set to that record and stamps `_assign` on it.
  `Event` is therefore a member of `TASK_REF_DOCTYPES`.
- **A Task's own assignee** is its `allocated_to` field. `crm_task_save` sets it directly
  when creating or editing a task, rather than routing through `assign_to.add`, which
  would create a second ToDo referencing the first.

Consequence for the UI: `AssignControl` appears on Events and CRM records; the Task dialog
has an ordinary "Assigned to" field. The two must not be conflated.

### Allowlists

Extends the existing `LINKABLE_REFS` precedent in `crm.py`:

- `TASK_REF_DOCTYPES` — Lead, Opportunity, Prospect, Customer, Quotation, Contact,
  Sales Order, Event.
- `PARTICIPANT_DOCTYPES` — the above plus Employee, User.

Anything off-list raises `frappe.PermissionError`. This prevents the SPA from becoming a
generic write API for arbitrary doctypes.

### Permission model

1. `_guard()` — imported from `crm.py`, single source of truth for the CRM role gate.
2. Doc-level permissions enforced: `frappe.get_doc(...).insert()` / `.save()` with checks
   **on**. No `ignore_permissions`.
3. `MANAGER_ROLES = {"System Manager", "Sales Manager", "CRM Manager"}` — new constant.

**Completion rule for `crm_task_status`:**

| Actor | Path | Why |
|---|---|---|
| The assignee (`allocated_to == session.user`) | `assign_to.close` | Fires core's side effects. |
| A `MANAGER_ROLES` holder, on someone else's task | `doc.status = …; doc.save()` | `assign_to.close` refuses non-assignees by design. Verified safe: `ToDo.validate` emits *"Assignment of X removed by Y"* and `on_update → update_in_reference()` refreshes `_assign` on the referenced doc. No manual `_assign` handling needed. |
| Anyone else | `frappe.throw` | Explicit "not your task" beats a silent no-op. |

### Change to the read layer

One targeted edit to `crm.py::crm_dashboard_events_tasks`:

- Filter ToDos to `reference_type in TASK_REF_DOCTYPES or reference_type is null`.
- Return the extra fields the forms need: `date`, `assigned_by`, `ends_on`, `all_day`,
  `description`, `location`, and a participant summary per Event.

## Frontend

`sections/Events.jsx` (71 lines, read-only) becomes a folder — it is about to do five
distinct jobs, and one file doing five things is the shape that resists both editing and
comprehension:

```
sections/Events/
  index.jsx         routes on `table`
  Dashboard.jsx     KPIs + charts (today's content)
  Calendar.jsx      month grid + week strip
  EventsTable.jsx   list + row actions
  TasksTable.jsx    list + inline complete + assign
components/
  EventDialog.jsx   create/edit Event
  TaskDialog.jsx    create/edit Task
  AssignControl.jsx user picker + assign/unassign
  LinkSearch.jsx    debounced search_link combobox
  ui/textarea.jsx  ui/checkbox.jsx
```

### LinkSearch is the load-bearing new primitive

Participants, task references, and the user picker all need the same debounced
combobox over `frappe.desk.search.search_link`. **Spec 3 (WhatsApp) reuses it for
contact lookup.** Worth building once, properly, with keyboard navigation.

### Calendar is hand-rolled

`vite.config.js` carries an extensive comment documenting that chunk-splitting mistakes
in this app cause **blank-screen** crashes (`Cannot access 'Pu' before initialization`,
`Cannot read properties of undefined (reading 'useState')`) from circular vendor chunks.
Adding a heavy calendar dependency into that single vendor chunk is precisely the risk
that comment warns about. A month grid plus week strip is roughly 150 lines of CSS grid
with zero dependency risk. Occurrences come from `crm_calendar`, so no client-side
recurrence logic either.

**The calendar navigates its own month**, independent of the header date-range pill. A
pill reading "Last 30 days" must not silently constrain a calendar the user is paging
forward to next March.

### Store

New actions follow the existing optimistic-update-with-rollback pattern already used by
`markRead` and `toggleStar`: apply locally, call the endpoint, revert on rejection.

- `saveEvent`, `saveTask`, `setTaskStatus`, `setEventStatus`, `assign`, `unassign`
- `loadCalendar(monthStart)` with its own `calMonth` / `calData` slice
- `reloadSection('evt')` — refetch one section after a write instead of `loadAll()`

### Navigation

`nav.js` gains a Calendar sub-item under Events & Tasks, and the group gains
`newDoctype`-style actions for New Event / New Task.

## Error handling

Writes fail loudly with actionable messages — the inverse of the read layer. Dialogs show
inline field errors plus a form-level banner. Optimistic row updates roll back on failure.

**Google sync** gets specific handling. The sync toggle renders only when
`crm_my_calendars()` returns an authorized calendar, and `crm_event_save` ignores a sync
request from a user without one rather than creating an Event doomed to fail on push.

Site state as of writing: Google Settings is enabled with client credentials, and several
users hold authorized calendars (anita@upande.com, calvine@karenroses.com,
pmaina@karenroses.com and others). **`james@upande.com` has two Google Calendar records
with no refresh token and no calendar ID**, so the sync control will be correctly hidden
for that account until OAuth is completed in desk. This is expected behaviour, not a bug.

## Testing

First tests in this app. `upande_crm/tests/test_activity.py`, run with:

```bash
bench --site kaitet.local run-tests --app upande_crm
```

Coverage targets logic that can silently cause harm:

- Off-allowlist `reference_type` / participant doctype is rejected.
- Completion rule: assignee closes; manager closes another's; a third party is refused.
- Manager-override close clears `_assign` on the referenced doc and leaves an audit comment.
- `assign` → ToDo created and `_assign` stamped; `unassign` → cleared.
- `ends_on` earlier than `starts_on` is rejected.
- Task query excludes non-CRM `reference_type` and retains unlinked ToDos.
- `crm_calendar` returns recurring occurrences within the window and none outside it.
- `_guard` rejects a user without a CRM role.

No frontend test runner is added; standing up Vitest is separate work and is not smuggled
into this spec.

## Verification

Beyond unit tests, the change is verified in the running app at
`/customer-relationship-management` after `cd frontend && yarn build`, since the SPA is
served from the built bundle in `upande_crm/public/frontend/`.
