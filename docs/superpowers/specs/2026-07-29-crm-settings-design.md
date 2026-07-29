# CRM Settings — Design

**Date:** 2026-07-29
**Status:** Approved design
**Scope:** Spec 4. Siblings: Events & Tasks (spec 1, delivered), Sales analytics (spec 2, delivered),
WhatsApp (spec 3, delivered).

## Problem

The CRM has grown three feature areas — WhatsApp, sales analytics, Events & Tasks — and every
one of them is hardcoded. There is no place to say *what this business is aiming at* or *how
this CRM should behave*, and no place to see whether the integrations it depends on are
actually working.

Concretely, today:

- **Settings are per-browser only.** `SettingsSheet.jsx` writes four keys to `localStorage`
  (`crm_settings`). Nothing is shared, so "the default range is 30 days" is an opinion each
  browser holds separately, and a sales target — inherently an organisational fact — has
  nowhere to live at all.
- **Business vocabulary is baked into Python.** `crm.py` decides an open Lead is one of
  `Lead, Open, Replied, Interested` and an open Opportunity is one of `Open, Quotation,
  Replied`, in four separate literal lists. A site that renames a status silently gets wrong
  KPIs.
- **There is no target, so no attainment.** The dashboard reports 638M KES booked in 2026
  without ever saying whether that is good. Target-vs-actual is the single most standard
  thing a sales dashboard does and it is absent.
- **Integration failures are invisible.** 82 of 191 outgoing WhatsApp messages on this site
  have `status='failed'` — a 43% failure rate that appears nowhere except as small red
  markers deep inside individual threads. Whether a default outgoing Email Account exists at
  all (it does: *Karen Roses Notifications*) is likewise unknowable from the CRM.
- **New Event/Task dialogs open empty**, so the same priority and the same rough due date get
  re-picked by hand every time.

## Goals

1. One **Settings section** in the SPA — a real page with tabs, reached from the sidebar and
   from the user footer, replacing the slide-over sheet.
2. Organisation-wide settings **persisted server-side**, editable by managers, readable by
   every CRM user.
3. Every setting must **change observable behaviour**. No inert toggles.
4. An **Integrations** tab that answers "is this thing actually working?" for sales data,
   email, WhatsApp, and activity — including the failure rate above.

### Non-goals

Per-user server-side preferences (view prefs stay in `localStorage` — they are per-device by
nature), role/permission administration (that stays in desk), editing WhatsApp credentials or
templates (owned by `frappe_whatsapp`), and per-rep individual quotas (one company-wide target
only; per-rep targets need a child table and a rep-attribution story this site does not have —
`sales_person` is unpopulated, which is why `_rep_performance` groups by `owner`).

## Hard constraints discovered on this site

### 1. `CRM Settings` is taken

ERPNext ships `CRM Settings` (module CRM) and Frappe CRM adds `FCRM Settings`, `ERPNext CRM
Settings`, `CRM Twilio Settings`, `CRM Exotel Settings` — all installed here.

**Decision:** the doctype is named **`Upande CRM Settings`**. It is the first doctype this app
has ever defined; module `Upande CRM` already exists as a Module Def, and `upande_crm/upande_crm/`
is its (currently doctype-less) module folder.

### 2. `CRM Manager` and `CRM User` roles do not exist here

`api/crm.py::CRM_ROLES` lists five roles, but only `System Manager`, `Sales Manager` and
`Sales User` exist on this site (193 / 327 / 225 holders). A DocPerm referencing a missing role
breaks `migrate`.

**Decision:** DocPerms name only the three roles that exist. `CRM Manager` stays in the Python
role gate (harmless, and correct on a site that does define it) but never appears in the
doctype JSON.

### 3. `WhatsApp Settings` exists as a DocType with no table

`frappe.db.exists("DocType", "WhatsApp Settings")` returns truthy, but
`select * from tabWhatsApp Settings` fails with *table doesn't exist* — a leftover from
`frappe_whatsapp`'s migration to multi-account `WhatsApp Account`. So `_has()`, which only
checks the DocType row, is **not** a safe gate for reading it.

**Decision:** the health check reads `WhatsApp Account` (rows: `james@upande.com` Active and
default in/out, `administrator` Inactive) and never touches `WhatsApp Settings`. Every health
probe is individually try-guarded so one broken integration cannot blank the panel.

### 4. A target is not range-scoped

The header date pill drives every other number in the CRM. A monthly target is a property of
the calendar month, not of "last 7 days" — computing attainment inside an arbitrary window
would produce a meaningless percentage.

**Decision:** attainment is always month-to-date and year-to-date, ignoring the picker, exactly
as `_aging()` already ignores it. The UI says so on the card.

### 5. Defaults must exist without the doctype

`api/crm.py`'s house style is that a missing doctype degrades rather than raises. Settings must
follow it: a site that has the app's Python but has not migrated the doctype yet must still
render.

**Decision:** `DEFAULTS` is a plain dict in `api/settings.py`, and `get_settings()` falls back
to it on any failure. The doctype JSON's field defaults mirror that dict; the dict is the
authority for reads.

## Backend

### DocType `Upande CRM Settings` (Single, module Upande CRM)

| Field | Type | Default | Effect |
|---|---|---|---|
| `revenue_target_monthly` | Currency | 0 | month-to-date attainment |
| `revenue_target_annual` | Currency | 0 | year-to-date attainment |
| `target_basis` | Select `Billed`/`Booked` | Billed | Sales Invoice vs Sales Order as the measured series |
| `default_date_range` | Select `7d`/`30d`/`90d`/`ytd` | 30d | seeds the header pill for users who never chose one |
| `top_n` | Int | 8 | rows in every top-N chart (reps, products, territories, sources, statuses) |
| `auto_refresh` | Check | 1 | seeds the auto-refresh preference |
| `refresh_interval_sec` | Int | 60 | seeds the interval |
| `lead_open_statuses` | Small Text | `Lead, Open, Replied, Interested` | what "open leads" counts |
| `opportunity_open_statuses` | Small Text | `Open, Quotation, Replied` | what "open opportunities" counts |
| `default_task_priority` | Select High/Medium/Low | Medium | new-task dialog |
| `default_task_due_days` | Int | 3 | new-task due date = today + n |
| `default_event_category` | Select | Meeting | new-event dialog |
| `default_event_duration_mins` | Int | 60 | auto-fills the event end time |
| `whatsapp_enabled` | Check | 1 | shows/hides the WhatsApp nav group and its dashboard query |
| `default_whatsapp_template` | Data | — | preselected in the composer |
| `whatsapp_fail_rate_alert` | Percent | 20 | threshold that turns the WhatsApp health check to a warning |

`default_whatsapp_template` is **Data, not Link**. A Link to `WhatsApp Templates` would make
this doctype unloadable on a site without `frappe_whatsapp`; the controller validates the value
against APPROVED templates when the doctype is present, and the UI offers a picker.

The controller validates and **throws** — bounds on the numerics (interval 15–3600, top-N 3–20,
due days 0–365, duration 5–1440, percent 0–100), non-negative targets, at least one status in
each status list, and template existence + APPROVED status. Silent clamping would leave the
user believing they had set something they had not.

### `upande_crm/api/settings.py`

Mixed read/write, following the split the app already uses: reads degrade, writes throw.

| Endpoint | Returns |
|---|---|
| `crm_settings()` | `{settings, can_edit, currency, options}` — never raises past the role gate |
| `crm_settings_save(settings)` | `{settings}`; throws on validation or permission failure |
| `crm_integration_status()` | `{company, currency, user, storage, checks: [...]}` |

Plus `get_settings()` for internal callers, reading through `frappe.get_cached_doc` (Frappe
invalidates the Single's cache on save) and falling back to `DEFAULTS`.

**Write gate:** `System Manager`, `Sales Manager`, `CRM Manager`. A Sales User reads the
settings and is refused the save with an explicit message — the UI renders the whole section
read-only for them rather than letting them type into a form that will reject.

**Import direction:** `settings.py` imports helpers from `crm.py`. `crm.py` and `analytics.py`
therefore import `get_settings` *inside* the functions that need it — a module-level import
either way would be a cycle.

Health checks, each independently guarded: sales data (Sales Order / Sales Invoice presence +
submitted counts), pipeline doctypes, outgoing email (a `default_outgoing` Email Account, else
any `enable_outgoing`, else off), incoming email, WhatsApp (an Active default-outgoing
`WhatsApp Account`, APPROVED template count, 30-day send failure rate against the threshold),
Events & Tasks, and settings storage (is the doctype installed, or are defaults in use).

### Wiring into the existing readers

- `crm_dashboard_overview` / `crm_dashboard_leads` / `crm_dashboard_opportunities`: the four
  hardcoded status lists become `settings["lead_open_statuses"]` /
  `["opportunity_open_statuses"]`.
- `_group()` and the analytics top-N helpers take their default limit from `top_n`.
- `crm_sales_analytics` gains a `targets` block: `{monthly, annual, basis, mtd, ytd, mtd_pct,
  ytd_pct}` — computed over the current calendar month and year, not the picker range.

Both additions are additive keys, so the existing response contract and its tests hold.

## Frontend

```
sections/Settings/index.jsx     tab router on `table`
  General.jsx                   personal prefs (localStorage) + org dashboard defaults
  Targets.jsx                   targets + basis, with live attainment preview
  Pipeline.jsx                  open-status vocabularies + top-N
  Activity.jsx                  task/event defaults
  WhatsApp.jsx                  enable, default template, alert threshold
  Integrations.jsx              health panel
components/SettingsSheet.jsx    DELETED — replaced by the section
```

Nav gains a **Workspace** group (`section: 'set'`) with those six tabs. The gear in the user
footer and the top bar now navigate to it instead of opening a sheet, so there is exactly one
settings surface.

Store gains `org` (server settings), `orgMeta` (`can_edit`, `currency`, `options`), and
`health`. `App` awaits `loadOrg()` before the first `loadAll()`: org defaults have to be in
hand before the date range is resolved, and one extra ~50ms round-trip is cheaper than loading
every section twice.

Personal prefs stay in `localStorage` but are now *layered*: `DEFAULT_SETTINGS` ←
`org` defaults ← whatever the user has explicitly stored. So an org changing its default range
moves every user who never overrode it, and nobody else.

Behaviour changes visible in the app:

- **Overview** gains a target-attainment card in the sales band (MTD and YTD bars). With no
  target set it shows a one-line prompt that navigates to Settings → Targets.
- **TaskDialog** opens new tasks with the configured priority and due date.
- **EventDialog** opens with the configured category and auto-fills the end time from the
  configured duration when the user picks a start and leaves the end blank.
- **WaComposer** preselects the default template.
- **Sidebar / `loadAll`** drop the WhatsApp group and its analytics query when
  `whatsapp_enabled` is off; if WhatsApp is the open section when it is switched off, the app
  falls back to Overview.

No new npm dependency (the `vite.config.js` vendor-chunk hazard still applies).

## Testing

`upande_crm/tests/test_settings.py`:

- `get_settings()` returns every `DEFAULTS` key, and falls back to defaults when the doctype
  read fails (patched).
- `_parse_list` splits on commas, trims, drops blanks, and preserves multi-word statuses.
- Round-trip: save a target, read it back through `crm_settings()`.
- Validation throws for a below-minimum refresh interval, out-of-range top-N, a negative
  target, an empty status list, and an unknown WhatsApp template.
- `crm_settings_save` raises `PermissionError` for a Sales User and `can_edit` is False for
  them; `_guard` rejects Guest on both endpoints.
- `crm_integration_status()` returns a check per documented key, every check carries a
  `status` from the known set, and it does not raise even though `WhatsApp Settings` has no
  table.
- Overview honours a configured lead-status list (set one status, count matches a direct
  query).
- `crm_sales_analytics()["targets"]` is present, and `mtd_pct` is 0 rather than a
  ZeroDivisionError when no target is set.

Existing suites (`test_analytics`, `test_whatsapp`, `test_activity`) must still pass unchanged.

## Verification

`bench --site kaitet.local run-tests --app upande_crm`, `cd frontend && npm run build`, then at
`http://localhost:8002/customer-relationship-management`: the Settings section saves a monthly
target, the Overview attainment card appears with it, and the Integrations tab reports the 43%
WhatsApp failure rate as a warning.
