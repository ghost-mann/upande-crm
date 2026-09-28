# CRM Modules, Customer Page & Theme — Design

**Date:** 2026-09-28
**Status:** Approved design
**Scope:** Sub-project 0 + 1 of the client CRM feature list, plus a theme rework.
Later sub-projects (each its own spec): Claims tracking, Quotations, Visit logging,
Pipeline stages & lead qualification, remaining reporting gaps.

## Problem

A client feature list asks for nine CRM capabilities and says every one of them must be
switchable from settings. Mapping the list against the app:

| Requested | Today |
|---|---|
| Centralized customer record | **Missing.** Customers is a list plus dashboards; a row opens the desk. |
| Communication logging | Mail, Calls, WhatsApp, Events exist — but no per-customer timeline and no notes. |
| Order history | Only a top-revenue list. No per-customer history. |
| Lead capture, pipeline, reporting | Largely present; gaps go to later specs. |
| Quotations, claims, visits | Partial or absent; later specs. |

And nothing can be switched off except WhatsApp (`whatsapp_enabled`).

Separately, the Theme tab offers two shipped presets (`upande`, `karen_roses`) over eight
seed colours. The user wants presets removed and replaced by in-depth palette, font and
shape customisation matching `upande_webstore`, explained so a non-designer can use it.

Order history is sourced from ERPNext only (Sales Order, Delivery Note, Sales Invoice).
"DXP" named in the client list is out of scope.

## Data facts (kaitet.local, the site with upande_crm installed)

- 888 Customers; 360 have `default_price_list`. **0** customer-specific Item Prices, **0**
  Pricing Rules — "agreed pricing" can only mean the price list.
- **0** Contracts.
- 11,323 Sales Orders, 13,841 Sales Invoices, 114 Delivery Notes — history must page.
- 38,003 Communications, 171 Events, 3 Call Logs.
- No `Customer Feedback` doctype on this site (1,837 Issues) — relevant to the Claims spec only.

## Goals

1. A **Modules** tab in Settings: one switch per CRM area, enforced server-side.
2. A **Customer page** inside the SPA — header card plus lazily-loaded tabs — covering the
   centralized record, communication timeline (with notes) and order history.
3. A **Theme** tab with no presets: brand, neutral and status colours, fonts and corner
   shape, a live preview, contrast warnings, and plain-English help on every field.

## Non-goals

- Claims, Quotations, Visits, pipeline stages, lead qualification (later specs; their
  module switches ship as disabled placeholders).
- DXP integration.
- Theme export/import (the CRM never had it; not adding it).
- Per-user module visibility (switches are org-wide; roles still gate as today).

---

## 1. Module switches

### Registry

New `upande_crm/modules.py` — the single source of truth:

```python
MODULES = [
  # key, settings field, label, nav sections owned, help, available
  Module("customer_page", "module_customer_page", "Customer page", ("custpage",), "...", True),
  Module("leads", "module_leads", "Leads", ("leads",), "...", True),
  Module("opps", "module_opps", "Opportunities", ("opps",), ...),
  Module("prosp", "module_prosp", "Prospects", ("prosp",), ...),
  Module("mail", "module_mail", "Mail", ("mail",), ...),
  Module("calls", "module_calls", "Calls", ("calls",), ...),
  Module("wa", "whatsapp_enabled", "WhatsApp", ("wa",), ...),   # existing field reused
  Module("evt", "module_events", "Events & Tasks", ("evt",), ...),
  Module("campaigns", "module_campaigns", "Campaigns", ("campaigns",), ...),
  Module("analytics", "module_analytics", "Sales analytics", ("analytics",), ...),
  Module("reports", "module_reports", "Reports", ("reports",), ...),
  Module("territories", "module_territories", "Territories", ("territories",), ...),
  Module("correspondence", "module_correspondence", "Correspondence", ("correspondence",), ...),
  Module("claims", "module_claims", "Claims", (), ..., available=False),
  Module("quotations", "module_quotations", "Quotations", (), ..., available=False),
  Module("visits", "module_visits", "Visits", (), ..., available=False),
]
```

(Section keys are whatever `nav.js` already uses; the plan confirms each.)

`is_enabled(key, settings=None)` → bool. An unavailable module is always False.
`enabled_map(settings=None)` → `{key: bool}` for the boot payload.

WhatsApp keeps its existing `whatsapp_enabled` field so current sites keep their value;
the Modules tab simply shows it alongside the rest. The WhatsApp tab's own toggle is
removed in favour of the Modules tab (one control, one place).

### Settings fields

Added to `Upande CRM Settings` (a new "Modules" section): one `Check` per module field
above, default `1` for available modules, `0` for placeholders. Customer page options:

- `custpage_tabs` — `Small Text`, newline list of enabled tabs, default
  `overview\ntimeline\norders\npricing\ncontracts`.
- `custpage_default_tab` — `Select` of the same keys, default `overview`.

`get_settings()` defaults and `crm_settings_save` allow-list gain these keys.

### Enforcement

- **Server:** `@requires_module("key")` decorator in `modules.py`, applied beneath
  `@frappe.whitelist()` on each module's endpoints. Off → `frappe.throw(_("This module is
  switched off in CRM Settings."), frappe.PermissionError)`. Shared dashboard endpoints
  (`crm_dashboard_overview` etc.) skip the work for a disabled module's cards instead of
  throwing.
- **Client:** `crm_settings` returns `modules: enabled_map()`. `nav.js` filters groups whose
  section is off (generalising today's `waOff`); `CaptureBar`, row links to the customer
  page, and Overview cards consult `useStore().modules`. `store.js` stops loading data for
  disabled sections (generalising the existing `wa` filter at store.js:595).
- **Editing:** existing `_can_edit`. Saving module changes shows "Reload to apply".

### UI

`Settings/Modules.jsx`: grouped list (Pipeline · Communication · Insight · Coming soon),
each row a switch, label, one plain-English sentence. Unavailable rows render disabled
with a "Coming soon" badge. Customer page row expands to its tab checkboxes and default
tab. Added to the Settings `TABS` map as `modules`.

### Tests (`tests/test_modules.py`)

- Every registry field exists on the doctype.
- Each decorated endpoint raises `PermissionError` when its module is off, works when on.
- Unavailable modules report False even if their field is 1.
- `enabled_map` reflects saved settings; `whatsapp_enabled` round-trips.

---

## 2. Customer page

### Navigation

The SPA has no URL routing today (`store.select(section, table)`). Add minimal hash sync:
`#<section>/<table>` and, for records, `#custpage/<urlencoded customer name>`. The store
gains `record` (`{doctype, name}` or null) and `openCustomer(name)`; `hashchange` and
initial load parse the hash, so the page is bookmarkable and Back returns to the list.

`openCustomer` is wired into: Customers "All/My" and "Top Revenue" tables, `crm_search`
customer hits, territory pinned-detail customer rows, and Opportunity/Prospect rows whose
party is a Customer. Each falls back to the current desk link when the module is off.
The page also offers "Open in desk".

### Header card — `crm_customer_header(name)`

Name, customer group, territory, default price list, account owner (`account_manager`,
falling back to owner), enabled state. Figures: lifetime revenue and revenue in the global
date range (submitted Sales Invoice `base_grand_total`, company currency), order count
(submitted Sales Orders), average order value, last order date with "N days ago", open
quotations (`party_name`, docstatus 1, status Open/Replied). Quick actions reuse existing
dialogs: Log call, Email (ComposeDialog), WhatsApp, New event, Add note — each hidden if
its module is off.

### Tabs — one endpoint each, loaded on first open

1. **Overview** — `crm_customer_overview(name)`: 12-month revenue trend, top 10 items by
   invoiced amount, next upcoming Event, open ToDos referencing the customer, five latest
   timeline entries.
2. **Timeline** — `crm_customer_timeline(name, kinds=None, before=None, limit=50)`: union,
   newest first, of Communication (email; `reference_doctype='Customer'` or linked via
   Contact / Dynamic Link — reusing `scope.py` resolution), Call Log (`customer` column or
   Dynamic Link), WhatsApp Message (by customer's contact numbers — reusing whatsapp.py
   lookup), Event (participants), ToDo, Comment (`comment_type='Comment'`). Each item:
   `{kind, when, title, snippet, who, ref_doctype, ref_name}`. Keyset paging on `when`.
   Filter chips per kind. **Add note** → `crm_customer_add_note(name, content)` inserts a
   standard Comment on the Customer (visible in the desk timeline too).
3. **Orders** — `crm_customer_orders(name, kind='Sales Order', status=None, start=0,
   page_len=25)`: kind ∈ Sales Order / Delivery Note / Sales Invoice; rows date, name,
   status, grand total, outstanding (invoices); total count for the pager. Summary strip:
   orders per month over the last 12 months, total outstanding.
4. **Pricing** — `crm_customer_pricing(name, search=None, start=0, page_len=50)`: Item
   Price rows for `default_price_list` (falling back to the customer group's
   `default_price_list`), each with the last invoiced rate to this customer for that item
   and its date. The header states which price list is shown. No list → explanatory empty
   state.
5. **Contracts** — `crm_customer_contracts(name)`: Contract where `party_type='Customer'`,
   status, start/end, signed. Empty state explains contracts are entered in ERPNext.
6. **Claims** — not in this spec; appears when the Claims module is built and on.

Only tabs listed in `custpage_tabs` render; `custpage_default_tab` opens first.

### Permissions & scope

Every endpoint: `@requires_module("customer_page")`, the existing `_guard()`, then
`frappe.has_permission("Customer", "read", name, throw=True)`. Sub-queries respect
`scope.py` so a user sees what they would in the desk.

### Performance

All queries filter on one customer via indexed columns (`customer` on SO/DN/SI,
`reference_name` / `timeline_name` on Communication, `party_name` on Quotation). Lists
page; the header issues one aggregate query per figure. No endpoint returns unbounded rows.

### Frontend

`sections/CustomerPage/` — `index.jsx` (header + tab strip, reads `record`), `Header.jsx`,
`Overview.jsx`, `Timeline.jsx`, `Orders.jsx`, `Pricing.jsx`, `Contracts.jsx`,
`lib/customer.js` for the API calls. Reuses `DataTable`, `Kpi`, `ChartCard`, charts.

### Tests (`tests/test_customer_page.py`)

Per endpoint: module off → PermissionError; user without Customer read → PermissionError;
paging bounds; unknown customer; a customer with no activity returns empty structures,
not errors. Header figures checked against direct SQL for a fixture customer. Add-note
creates a Comment. Manual check on kaitet.local: one real customer's header matches desk.

---

## 3. Theme

### Removed

`theme/transfer.py`, `theme/presets/`, `crm_theme_apply_preset`, the `theme_preset`
field, the preset cards in `Settings/Theme.jsx`, and their tests. `crm_theme_reset` now
clears every theme field — blank means shipped default, so a reset site emits no
override `<style>` at all.

### Seeds

Existing: `theme_accent`, `theme_ink`, `theme_ink_muted`, `theme_canvas`,
`theme_success`, `theme_warning`, `theme_danger`, `theme_info`.

New colour seeds: `theme_accent_dark`, `theme_accent_soft`, `theme_accent_primary`
(Check), `theme_wash`, `theme_border`, `theme_border_strong`.

New fonts: `theme_font_sans`, `theme_font_display`, `theme_font_mono` (Select: blank,
bundled families, Custom), `theme_font_sans_name`, `theme_font_display_name`,
`theme_font_mono_name` (Data), `theme_google_fonts_url` (Data).

New shape: `theme_radius`, `theme_radius_card`, `theme_radius_panel` (Data, CSS length).

Advanced: `theme_custom_css` (Code, CSS).

### Derivation (`theme/tokens.py`)

Blank seed = today's derivation, unchanged. Set seed = pins that token:

| Seed | Pins (instead of deriving) |
|---|---|
| accent_dark | `--gold-2`, `--gold-text`, gradient deep stop |
| accent_soft | `--gold-soft`, `--selected` |
| accent_primary | `--primary`/`--on-accent`/active-nav tokens take the accent ramp |
| wash | `--surface-3`, `--hover` base |
| border | `--line`, `--border`, `--input`, `--hairline` |
| border_strong | `--line-2` |

Fonts via `theme/fonts.py`, ported from `upande_webstore/theme/fonts.py`: bundled
families Poppins, Inter, IBM Plex Sans, Space Grotesk (sans); Fraunces (display); IBM
Plex Mono (mono). woff2 files copied into `upande_crm/public/fonts/` with `@font-face` in
`index.css`; the Google Fonts `<link>` for Poppins/Fraunces is removed from both HTML
entry points (Material Symbols link stays). Custom URL accepted only if `https` and host
exactly `fonts.googleapis.com`; otherwise it is refused on save.

Shape: introduce `--r-sm`, `--r-card`, `--r-panel` in `index.css` (defaults matching
today: 9px, 14px, 18px — confirmed in the plan by auditing each rule) and replace the
hard-coded `border-radius` values on controls, cards/tables and dialogs. `999px` pills
and `50%` avatars stay literal. Radius seeds validated as CSS lengths
(`^\d+(\.\d+)?(px|rem|em)$` or `0`).

Custom CSS appended last inside `:root`; `</style` rejected on save.

The existing test that seeding the shipped values reproduces the shipped palette stays;
extended so blank new seeds change nothing and each new seed pins exactly its tokens.

### UI (`Settings/Theme.jsx`)

Two columns: form left, sticky **live preview** right (collapses above the form on narrow
screens). Preview is built from real CRM components — sidebar snippet, KPI tile, primary
and outline buttons, the four status badges, a table row with hover, a small bar chart,
an input — rendered inside a wrapper whose CSS variables are computed client-side from the
draft, so it updates before Save. A shared JS port of the derivation (`lib/theme.js`)
keeps preview and server in agreement; a test fixture compares both on the same seeds.

Sections: Brand colours · Neutral colours · Status colours · Fonts · Shape · Advanced
(collapsed, labelled "for developers"). Every field shows a plain-English line (what you
will see change) and a smaller "Technically:" line (what it drives), e.g.

- **Ink** — "The main text colour. It also tints every grey and every shadow, so this one
  choice changes the feel of the whole app." / Technically: text, 7-step grey scale,
  shadows.
- **Use accent for main buttons** — "Off: main buttons are near-black and your brand colour
  is just trim. On: buttons and the active menu item use your brand colour."

Blank colour fields show the derived value as a faded swatch with "worked out for you".

**Contrast check:** WCAG ratio badges for text-on-canvas, muted-on-canvas,
text-on-accent (when accent drives buttons), status-text-on-soft. ≥4.5 ✓ readable,
3–4.5 ⚠ "hard to read for small text", <3 ⚠ "hard to read". Warns, never blocks.

### Tests

`test_theme.py` updated: presets gone; reset clears all fields; each new seed pins its
tokens; fonts URL allow-list; radius and custom-CSS validation; empty settings emit no CSS.

---

## Build order

1. Modules registry, fields, decorator, Modules tab, nav filtering.
2. Hash routing + customer page header and tabs.
3. Theme: remove presets, new seeds + derivation, fonts, radius variables, new Theme tab.

Each step leaves the app working and is committed separately.
