# CRM Calls — Design

**Date:** 2026-07-29
**Status:** Approved scope (confirmed in conversation), design not separately reviewed
**Scope:** Spec 7, the last of the set. Siblings 1–6 all delivered.

## Problem

Calls are the one channel the CRM cannot record. Email has the Inbox, WhatsApp has
its own section, meetings and tasks have Events & Tasks — but a phone call, still
how most of this business is actually done, has nowhere to go. Today it gets
written into whatever is nearest: 21 Communications are tagged medium `Phone`, 6
Events carry category `Call`, and the rest is lost.

Requested: log a call, **incoming or outgoing**, with an outcome; create a
follow-up task from it; log one straight from a Lead or Customer row; and see the
whole thing on a dashboard.

## What already exists

Frappe core ships **`Call Log`** (Telephony module) and it is almost exactly the
right shape:

| Field | Use |
|---|---|
| `type` | `Incoming` / `Outgoing` — the requested distinction, already there |
| `status` | Ringing / In Progress / **Completed** / **Failed** / **Busy** / **No Answer** / Queued / Cancelled |
| `from`, `to` | the numbers |
| `duration` | Duration (seconds) |
| `start_time`, `end_time` | when |
| `summary` | Small Text — what was said |
| `type_of_call` | Link to `Telephony Call Type` — the disposition vocabulary |
| `links` | child table of Dynamic Link — attaches the call to any CRM record |
| `customer`, `call_received_by`, `employee_user_id`, `recording_url`, `medium`, `id` | telephony extras |

**0 Call Log rows exist**, so there is nothing to migrate and no legacy shape to
respect. `Telephony Call Type` is also empty, so the disposition list starts blank.
`Twilio Settings` and `Voice Call Settings` exist but no telephony is wired up, so
every call today is a manual entry.

**Decision: log into core `Call Log`.** Not `CRM Call Log` (that belongs to the
Frappe CRM app, a separate UI this SPA has nothing to do with, also 0 rows), and
not a new doctype. If Twilio is ever connected, its automatically-created calls
land in the same section for free — which a bespoke doctype would not give.

## Backend — `upande_crm/api/calls.py`

Mixed read/write, so it follows `api/activity.py`'s rule rather than the readers':
**every write failure surfaces.** A call the user believes they logged and which
was silently dropped is the worst outcome this module can produce.

| Endpoint | Behaviour |
|---|---|
| `crm_call_save(call)` | create or update; returns the saved name. Throws. |
| `crm_call_delete(name)` | only the owner or a manager, mirroring the task rule |
| `crm_call_types()` | the disposition vocabulary |
| `crm_call_type_add(label)` | create a `Telephony Call Type` — the list starts empty, so the UI must be able to seed it |
| `crm_dashboard_calls(date_from, date_to, customer)` | KPIs, direction/outcome mixes, daily trend, per-rep counts, and the rows |

Writes are whitelist-filtered to `CALL_FIELDS` exactly as `activity.py` filters
Event and ToDo payloads, so a crafted request cannot set `owner` or `docstatus`.
Reference links are validated against the same `TASK_REF_DOCTYPES` allowlist the
task layer already uses, reusing that decision rather than inventing a second one.

`Call Log` has no CRM DocPerms, so — consistent with `Communication` and
`WhatsApp Message` — reads and writes go through with `ignore_permissions=True`
after `_guard()`, with the reference validated. This widening is deliberate and
bounded, and matches the recorded decision for the other two channels.

**Follow-up task on log.** When the payload carries `follow_up`, the same request
creates a ToDo through `api/activity.py`'s existing `crm_task_save`, linked to the
call's own reference, with the configured default priority and due-in days from
`Upande CRM Settings`. Delegating rather than reimplementing means the task appears
in Events & Tasks and obeys the same allowlist and validation. If the task fails,
**the call is still saved** and the response says the follow-up did not stick — the
call is the record of fact, the task is a convenience.

**Duration** is entered as minutes in the UI and stored as seconds, because
`Duration` is a seconds field and nobody logs a call in seconds.

`customer` filtering reuses `api/scope.py`: a call belongs to a customer when its
links point at anything in that customer's resolved scope, the same definition the
rest of the CRM now uses.

## Frontend

```
sections/Calls/index.jsx     tab router
  Dashboard.jsx              KPIs, direction/outcome mix, trend, per-rep
  CallsTable.jsx             the log, with "mine" filtering
components/CallDialog.jsx    log or edit a call
```

Nav gains a **Calls** group under Activity, icon `call`, with tabs Dashboard /
Log / My calls, and a count badge of calls in range.

`CallDialog` fields: direction (Incoming/Outgoing as a two-button toggle, since it
is the first thing you know), number, contact, when, duration in minutes, outcome
(`status`), disposition (`type_of_call`, with an inline "add" for the empty
vocabulary), summary, linked record via the existing `LinkSearch`, and a follow-up
block — a checkbox that reveals a description and due date, prefilled from
settings.

A **"Log call"** action appears on Lead, Prospect, Customer and Opportunity rows,
prefilling the reference and the record's phone number. Reuses the `AssignControl`
row-action pattern already in the tables.

## Testing

`upande_crm/tests/test_calls.py`:

- A logged call round-trips: direction, status, disposition, duration and summary.
- Minutes → seconds conversion, both ways.
- An off-allowlist reference doctype is refused.
- A reference naming a record that does not exist is refused.
- Missing number, missing direction and an unknown status are each refused.
- `follow_up` creates a linked ToDo with the configured priority and due date, and
  that ToDo is visible to `crm_dashboard_events_tasks`.
- **A failing follow-up leaves the call saved** and reports the failure.
- Dashboard KPIs count direction and outcome correctly, and `fail_rate` is 0 rather
  than a ZeroDivisionError with no calls.
- Customer filtering narrows the log via `scope.py`, and an unrelated customer
  yields none rather than all.
- `crm_call_type_add` creates a type, is idempotent on an existing label, and
  refuses an empty one.
- Delete is refused for a non-owner non-manager.
- `_guard` rejects Guest on every endpoint.

## Verification

`bench --site kaitet.local run-tests --app upande_crm`, `npm run build`, then log a
call from a Lead row, confirm it appears in the Calls log and dashboard, and
confirm its follow-up task appears under Events & Tasks.
