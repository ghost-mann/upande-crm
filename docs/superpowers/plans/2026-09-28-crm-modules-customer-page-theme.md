# CRM Modules, Customer Page & Theme — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Org-wide module switches, a per-customer page inside the CRM SPA, and a preset-free theme editor with colours, fonts and corner shape.

**Architecture:** A `modules.py` registry drives three things: Check fields on `Upande CRM Settings`, a `@requires_module` decorator on whitelisted endpoints, and a `modules` map the SPA uses to filter nav, loaders and links. The customer page is a new SPA section (`custpage`, with the customer name in `table`), served by `api/customer.py`, where each tab has its own paged endpoint. The theme layer drops presets, gains seeds for colours, fonts, radius and custom CSS in `theme/tokens.py` and `theme/fonts.py`, and has a no-save preview endpoint so the live preview uses the server's derivation.

**Tech Stack:** Frappe v16 (Python 3.14), ERPNext, React 18 + Vite + Tailwind + zustand, shadcn-style primitives.

**Spec:** `docs/superpowers/specs/2026-09-28-crm-modules-customer-page-theme-design.md`

## Global Constraints

- Test site: `kaitet.local` (`allow_tests: true`). Run: `bench --site kaitet.local run-tests --app upande_crm --module upande_crm.tests.<module>` from `/home/austin/frappe-v16-bench`. Redis cache (11002) and queue (13002) must be up.
- Settings reads never raise (`get_settings` degrades to `DEFAULTS`); writes throw. `DEFAULTS` must mirror doctype JSON defaults (`test_doctype_json_defaults_match_the_python_defaults`).
- Every query parameterised; customer names come from the client.
- Frontend build: `cd apps/upande_crm/frontend && yarn build` (writes `upande_crm/public/frontend` + the www html). Keep only the react-core leaf manual chunk (memory: circular-chunk crash).
- v16 `get_list` rejects SQL functions in `fields=` — use `frappe.qb` or `frappe.db.sql` for aggregates.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Blank theme seed = today's derivation; no seeds at all = no `<style>` emitted.
- Google font URLs accepted only when `https` and host exactly `fonts.googleapis.com`.

## Review Focus

1. **Module off while a user is on that section** → the SPA must bounce to Overview, not render a broken section (test: `App.jsx` effect generalised; manual check).
2. **Customer name with `/`, `&`, `'` or unicode in the hash** → the page opens the right customer (encodeURIComponent round-trip; test via `crm_customer_header` with such a name).
3. **Customer with zero orders / no price list / no contacts** → every tab shows an explanatory empty state, not an error (test: `test_empty_customer_returns_empty_structures`).
4. **Radius field given `12` (no unit) or `1e3px`** → refused on save with a clear message (test: `test_radius_requires_a_css_length`).
5. **User lacks read on the Customer** → every customer endpoint raises PermissionError (test: `test_customer_endpoints_require_customer_read`).

## Deviation from spec (recorded)

The spec proposed a JS port of the derivation for the live preview, plus a parity fixture. Instead, the preview calls `crm_theme_preview(seeds)`, a no-save endpoint that returns tokens and contrast results from the same Python code. Server and preview then can't disagree, and there's no second derivation to maintain. The spec was updated to match.

---

### Task 1: Module registry, settings fields, and `modules` in the settings payload

**Files:**
- Create: `upande_crm/modules.py`
- Modify: `upande_crm/upande_crm/doctype/upande_crm_settings/upande_crm_settings.json` (new "Modules" section)
- Modify: `upande_crm/api/settings.py` (`DEFAULTS`, `OPTIONS`, `crm_settings`)
- Test: `upande_crm/tests/test_modules.py`

**Interfaces — Produces:**
- `upande_crm.modules.MODULES: tuple[Module]`, `Module(key, field, label, sections, help, group, available)`
- `is_enabled(key: str, settings: dict | None = None) -> bool`
- `enabled_map(settings=None) -> dict[str, bool]`
- `requires_module(key)` decorator (body in Task 2; defined here so imports resolve)
- `crm_settings()` payload gains `"modules": enabled_map()` and `"module_meta": [{key, label, help, group, available, field}]`
- Settings keys: `module_customer_page, module_leads, module_opps, module_prosp, module_mail, module_calls, module_events, module_activity_log, module_campaigns, module_analytics, module_reports, module_territories, module_correspondence, module_claims, module_quotations, module_visits` (Check), `whatsapp_enabled` (existing), `custpage_tabs` (Small Text), `custpage_default_tab` (Select)

Registry (section keys are the SPA's `nav.js` keys):

| key | field | sections | group | available |
|---|---|---|---|---|
| customer_page | module_customer_page | custpage | Customers | ✓ |
| leads | module_leads | leads | Pipeline | ✓ |
| opps | module_opps | opps | Pipeline | ✓ |
| prosp | module_prosp | prosp | Pipeline | ✓ |
| mail | module_mail | mail | Communication | ✓ |
| wa | whatsapp_enabled | wa | Communication | ✓ |
| calls | module_calls | calls | Communication | ✓ |
| evt | module_events | evt | Communication | ✓ |
| act | module_activity_log | act | Communication | ✓ |
| camp | module_campaigns | camp | Marketing | ✓ |
| anl | module_analytics | anl | Insight | ✓ |
| rep | module_reports | rep | Insight | ✓ |
| terr | module_territories | terr | Insight | ✓ |
| corr | module_correspondence | corr | Insight | ✓ |
| claims | module_claims | — | Coming soon | ✗ |
| quotations | module_quotations | — | Coming soon | ✗ |
| visits | module_visits | — | Coming soon | ✗ |

`CUSTPAGE_TABS = ("overview", "timeline", "orders", "pricing", "contracts")`.

- [ ] **Step 1: Write failing tests** (`tests/test_modules.py`)

```python
import json, os
import frappe
from frappe.tests.utils import FrappeTestCase
from upande_crm import modules as M
from upande_crm.api import settings as S

def _clear():
    frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)

def _save(**patch):
    doc = frappe.get_single(S.SETTINGS_DOCTYPE); doc.update(patch)
    doc.save(ignore_permissions=True); _clear()

class TestRegistry(FrappeTestCase):
    def tearDown(self): _clear()

    def test_every_module_field_is_on_the_doctype(self):
        meta = frappe.get_meta(S.SETTINGS_DOCTYPE)
        for m in M.MODULES:
            self.assertTrue(meta.has_field(m.field), m.field)

    def test_every_module_field_has_a_default(self):
        for m in M.MODULES:
            self.assertIn(m.field, S.DEFAULTS)

    def test_keys_and_sections_are_unique(self):
        keys = [m.key for m in M.MODULES]
        self.assertEqual(len(keys), len(set(keys)))
        secs = [s for m in M.MODULES for s in m.sections]
        self.assertEqual(len(secs), len(set(secs)))

    def test_available_modules_default_on_placeholders_off(self):
        for m in M.MODULES:
            self.assertEqual(S.DEFAULTS[m.field], 1 if m.available else 0, m.key)

    def test_unavailable_module_is_never_enabled(self):
        _save(module_claims=1)
        self.assertFalse(M.is_enabled("claims"))

    def test_switching_off_is_reflected(self):
        _save(module_calls=0)
        self.assertFalse(M.is_enabled("calls"))
        self.assertFalse(M.enabled_map()["calls"])
        self.assertTrue(M.enabled_map()["leads"])

    def test_whatsapp_uses_its_existing_field(self):
        _save(whatsapp_enabled=0)
        self.assertFalse(M.is_enabled("wa"))

    def test_unknown_key_is_disabled(self):
        self.assertFalse(M.is_enabled("nope"))

    def test_settings_payload_carries_modules(self):
        frappe.set_user("Administrator")
        out = S.crm_settings()
        self.assertIn("modules", out)
        self.assertEqual(set(out["modules"]), {m.key for m in M.MODULES})
        self.assertTrue(all("label" in r and "help" in r for r in out["module_meta"]))

    def test_custpage_tabs_default_lists_all_tabs(self):
        self.assertEqual(S.parse_lines(S.DEFAULTS["custpage_tabs"]), list(M.CUSTPAGE_TABS))
```

- [ ] **Step 2: Run** — `bench --site kaitet.local run-tests --app upande_crm --module upande_crm.tests.test_modules` → FAIL (`No module named upande_crm.modules`).

- [ ] **Step 3: Implement.**
  - `modules.py`: a `Module` namedtuple, the table above with one plain-English `help` sentence each (e.g. Calls: "Log phone calls against leads and customers, and see who called whom."), `CUSTPAGE_TABS`, `is_enabled` (unknown key → False; `not m.available` → False; otherwise `cint(settings.get(m.field))`, with `settings` defaulting to `get_settings()` imported inside the function to avoid the import cycle), `enabled_map`, `module_meta()`.
  - Doctype JSON: add `sb_modules` Section "Modules" after `sb_whatsapp`, with one Check per new field (default "1" or "0"), plus `custpage_tabs` (Small Text, default `overview\ntimeline\norders\npricing\ncontracts`) and `custpage_default_tab` (Select, options = the 5 tabs, default `overview`). Bump `modified`.
  - `settings.py`: add module fields (int), `custpage_tabs`, `custpage_default_tab` to `DEFAULTS`; add `"custpage_default_tab": list(CUSTPAGE_TABS)` to `OPTIONS`; add `parse_lines(text)` (splits on newlines and commas, trims, drops blanks); in `crm_settings` add `modules` and `module_meta`.
  - Controller: `_validate_custpage()` requires every `custpage_tabs` entry to be in `CUSTPAGE_TABS`, requires at least one, and requires `custpage_default_tab` to be in the list.
- [ ] **Step 4: Migrate and test** — `bench --site kaitet.local migrate` then run `test_modules` and `test_settings` → PASS.
- [ ] **Step 5: Commit** `feat(crm): a registry of switchable modules, stored on CRM Settings`.

---

### Task 2: Enforce module switches on the server

**Files:**
- Modify: `upande_crm/modules.py` (`requires_module`)
- Modify: `api/crm.py`, `api/leads.py`, `api/calls.py`, `api/activity.py`, `api/campaigns.py`, `api/analytics.py`, `api/pipeline.py`, `api/reports.py`, `api/territory.py`, `api/logistics.py`, `api/correspondence.py`, `api/whatsapp.py`
- Test: `upande_crm/tests/test_modules.py` (add class)

**Interfaces — Consumes:** `is_enabled`. **Produces:** `requires_module(key)` → decorator. It raises `frappe.PermissionError` with the message "This module is switched off in CRM Settings." and preserves the signature (`functools.wraps`).

Endpoint → module map (only these are decorated; generic endpoints such as `crm_assign`, `crm_search`, `advance.*` and `crm_correspondent_for_emails` stay open):

```python
GATED = {
  "leads": ["upande_crm.api.crm.crm_dashboard_leads", "upande_crm.api.leads.crm_lead_save"],
  "opps": ["upande_crm.api.crm.crm_dashboard_opportunities"],
  "prosp": ["upande_crm.api.crm.crm_dashboard_prospects"],
  "mail": ["upande_crm.api.crm.crm_mail_data", "upande_crm.api.crm.crm_mark_read",
           "upande_crm.api.crm.crm_send_email"],
  "wa": ["upande_crm.api.whatsapp.crm_whatsapp_conversations", "upande_crm.api.whatsapp.crm_whatsapp_thread",
         "upande_crm.api.whatsapp.crm_whatsapp_send", "upande_crm.api.whatsapp.crm_whatsapp_send_template",
         "upande_crm.api.whatsapp.crm_whatsapp_templates", "upande_crm.api.whatsapp.crm_whatsapp_analytics",
         "upande_crm.api.whatsapp.crm_whatsapp_mark_read", "upande_crm.api.whatsapp.crm_whatsapp_match"],
  "calls": ["upande_crm.api.calls.crm_dashboard_calls", "upande_crm.api.calls.crm_call_save",
            "upande_crm.api.calls.crm_call_delete", "upande_crm.api.calls.crm_call_type_add"],
  "evt": ["upande_crm.api.crm.crm_dashboard_events_tasks", "upande_crm.api.activity.crm_calendar",
          "upande_crm.api.activity.crm_my_calendars", "upande_crm.api.activity.crm_event_save",
          "upande_crm.api.activity.crm_event_status", "upande_crm.api.activity.crm_task_save",
          "upande_crm.api.activity.crm_task_status"],
  "act": ["upande_crm.api.crm.crm_dashboard_activity"],
  "camp": ["upande_crm.api.campaigns.crm_dashboard_campaigns", "upande_crm.api.campaigns.crm_campaign_detail",
           "upande_crm.api.campaigns.crm_campaign_save", "upande_crm.api.campaigns.crm_campaign_enrol",
           "upande_crm.api.campaigns.crm_campaign_cancel", "upande_crm.api.campaigns.crm_campaign_recipients"],
  "anl": ["upande_crm.api.pipeline.crm_analytics_funnel", "upande_crm.api.pipeline.crm_analytics_leads",
          "upande_crm.api.pipeline.crm_analytics_opportunities", "upande_crm.api.pipeline.crm_analytics_revenue"],
  "rep": ["upande_crm.api.reports.crm_reports", "upande_crm.api.reports.crm_report_run",
          "upande_crm.api.reports.crm_report_catalogue"],
  "terr": ["upande_crm.api.territory.crm_territory_map", "upande_crm.api.territory.crm_territory_detail",
           "upande_crm.api.logistics.crm_delivery_points", "upande_crm.api.logistics.crm_delivery_point_detail"],
  "corr": ["upande_crm.api.correspondence.crm_correspondence"],
}
```

(`crm_sales_analytics` feeds the Overview, so it stays ungated; check `SECTION_LOADERS.sales` before deciding. `crm_call_types` is read by the call dialog from other sections, so it stays ungated.)

- [ ] **Step 1: Failing test**

```python
from upande_crm.tests.test_modules_gated import GATED  # the map above, kept in its own module for reuse

class TestEnforcement(FrappeTestCase):
    def setUp(self): frappe.set_user("Administrator")
    def tearDown(self): _clear()

    def test_every_gated_endpoint_refuses_when_its_module_is_off(self):
        for key, paths in GATED.items():
            m = next(x for x in M.MODULES if x.key == key)
            _save(**{m.field: 0})
            for path in paths:
                fn = frappe.get_attr(path)
                with self.assertRaises(frappe.PermissionError, msg=path):
                    fn()
            _save(**{m.field: 1})

    def test_gated_endpoints_stay_whitelisted(self):
        for paths in GATED.values():
            for path in paths:
                self.assertIn(frappe.get_attr(path), frappe.whitelisted, path)

    def test_decorator_preserves_the_signature(self):
        import inspect
        from upande_crm.api.crm import crm_dashboard_leads
        self.assertIn("date_from", inspect.signature(crm_dashboard_leads).parameters)
```

Put `GATED` in `upande_crm/tests/test_modules_gated.py`, which holds only the dict. The decorator must check *before* argument validation, so calling with no args raises PermissionError, not TypeError. Place `@requires_module` **below** `@frappe.whitelist()`; the wrapper takes `*args, **kwargs`.

- [ ] **Step 2: Run** → FAIL (no PermissionError).
- [ ] **Step 3: Implement** the decorator:

```python
def requires_module(key):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not is_enabled(key):
                frappe.throw(_("This module is switched off in CRM Settings."), frappe.PermissionError)
            return fn(*args, **kwargs)
        return wrapper
    return deco
```

  Then apply it to each path in `GATED`: `from upande_crm.modules import requires_module` and add `@requires_module("…")` directly beneath `@frappe.whitelist(...)`.
- [ ] **Step 4: Run** `test_modules`, then the whole app suite: `bench --site kaitet.local run-tests --app upande_crm` → all PASS (existing tests run with modules on by default).
- [ ] **Step 5: Commit** `feat(crm): switched-off modules refuse their endpoints`.

---

### Task 3: Module switches in the SPA (nav, loaders, redirect, Modules tab)

**Files:**
- Modify: `frontend/src/nav.js` (`visibleNav(org, modules)`; add `{ table: 'modules', label: 'Modules' }` to Settings subs after General)
- Modify: `frontend/src/store.js` (`orgMeta.modules`, `orgMeta.moduleMeta`; `moduleOn(key)`; filter `loadAll` keys)
- Modify: `frontend/src/App.jsx` (generalised redirect)
- Modify: `frontend/src/components/Sidebar.jsx` and `SectionTabs.jsx` (pass modules to `visibleNav`)
- Modify: `frontend/src/components/CaptureBar.jsx` (hide actions whose module is off: lead create → `leads`, call → `calls`, event/task → `evt`, email → `mail`, WhatsApp → `wa`)
- Modify: `frontend/src/sections/Overview/index.jsx` (hide cards owned by a disabled module)
- Modify: `frontend/src/sections/Settings/WhatsApp.jsx` (remove the enable toggle; show "Switched on/off in Modules" with a link)
- Create: `frontend/src/sections/Settings/Modules.jsx`
- Modify: `frontend/src/sections/Settings/index.jsx` (`modules: Modules`)

**Interfaces — Consumes:** `crm_settings().modules`, `.module_meta`. **Produces:** `useStore().moduleOn(key) -> bool` (true while unloaded); `SECTION_MODULE` map `{section: moduleKey}` exported from `nav.js`; loader→module map `{leads:'leads', opps:'opps', prosp:'prosp', evt:'evt', act:'act', wa:'wa', calls:'calls', campaigns:'camp'}` (other loaders are always on).

- [ ] **Step 1:** `nav.js`: build `SECTION_MODULE` from a literal `{custpage:'customer_page', leads:'leads', opps:'opps', prosp:'prosp', mail:'mail', wa:'wa', calls:'calls', evt:'evt', act:'act', camp:'camp', anl:'anl', rep:'rep', terr:'terr', corr:'corr'}`. `visibleNav(org, modules)` drops items whose `SECTION_MODULE[section]` maps to `false` in `modules`, then drops empty groups. Keep the `org.whatsapp_enabled` fallback when `modules` is undefined.
- [ ] **Step 2:** `store.js`: `loadOrg` stores `payload.modules` and `payload.module_meta` in `orgMeta`; `saveOrg` refreshes `orgMeta.modules` from a re-fetch of `crm_settings`. Add `moduleOn: (k) => { const m = get().orgMeta?.modules; return !m || m[k] !== false; }`. `loadAll` filters `SECTION_LOADERS` keys through `LOADER_MODULE`.
- [ ] **Step 3:** `App.jsx`: replace the `wa` effect with `if (SECTION_MODULE[section] && !moduleOn(SECTION_MODULE[section])) select('overview')`.
- [ ] **Step 4:** `Modules.jsx`: uses the existing `Panel`/`SaveBar`/form pattern from `Settings/WhatsApp.jsx`. Groups come from `module_meta.group`. Each row has a switch (`button role="switch"`, as in WhatsApp.jsx), the label and the help line. Unavailable rows are disabled with a "Coming soon" badge. The customer-page row expands into tab checkboxes (writing `custpage_tabs` as newline text) and a default-tab select. After a successful save it shows a note: "Reload the page to apply." Read-only when `!orgMeta.can_edit`.
- [ ] **Step 5:** CaptureBar and Overview gating as listed above, grepping each component for the section it opens.
- [ ] **Step 6: Build and verify** — `cd apps/upande_crm/frontend && yarn build` succeeds. Manual: on kaitet.local, switch Calls off in Modules, reload, and confirm Calls is gone from the sidebar and `/api/method/upande_crm.api.calls.crm_dashboard_calls` returns 403. Switch it back on.
- [ ] **Step 7: Commit** `feat(crm): a Modules settings tab, and a sidebar that honours it`.

---

### Task 4: Customer page API — header, overview, orders, pricing, contracts

**Files:**
- Create: `upande_crm/api/customer.py`
- Test: `upande_crm/tests/test_customer_page.py`

**Interfaces — Produces** (all `@frappe.whitelist()` + `@requires_module("customer_page")`, then `_guard()` and `_customer(name)`, which does `frappe.has_permission("Customer","read",name,throw=True)` and raises `DoesNotExistError` for unknown names):
- `crm_customer_header(name, date_from=None, date_to=None) -> {customer:{name, customer_name, customer_group, territory, default_price_list, account_manager, disabled, image}, currency, figures:{lifetime_revenue, range_revenue, order_count, avg_order_value, last_order_date, days_since_last_order, open_quotations}, tabs:[...], default_tab}`
- `crm_customer_overview(name) -> {trend:[{label, amount}] (12 months), top_items:[{item_code, item_name, amount, qty}], next_event:{name, subject, starts_on}|None, open_todos:[{name, description, date, allocated_to, priority}]}`
- `crm_customer_orders(name, kind="Sales Order", status=None, start=0, page_len=25) -> {rows:[{name, date, status, grand_total, outstanding}], total, statuses:[...], summary:{per_month:[{label,count}], outstanding}}`. `kind` must be in `("Sales Order","Delivery Note","Sales Invoice")`, else throw. `page_len` is clamped to 1–100.
- `crm_customer_pricing(name, search=None, start=0, page_len=50) -> {price_list, source:"customer"|"customer_group"|None, rows:[{item_code, item_name, uom, rate, currency, last_rate, last_date}], total}`
- `crm_customer_contracts(name) -> {rows:[{name, status, start_date, end_date, is_signed, contract_template}], available: bool}`

Money: submitted (`docstatus=1`) Sales Invoice `base_grand_total`, currency from `_company_currency()`. Order count = submitted Sales Orders. Open quotations: `quotation_to='Customer' AND party_name=name AND docstatus=1 AND status IN ('Open','Replied')`. Last invoiced rate per item: `SELECT sii.item_code, sii.rate, si.posting_date FROM tabSales Invoice Item sii JOIN tabSales Invoice si … WHERE si.customer=%s AND si.docstatus=1 AND sii.item_code IN %s ORDER BY si.posting_date DESC`, reduced in Python to the first row per item (item codes for the current page only).

- [ ] **Step 1: Failing tests** — use a fixture customer created in `setUpClass` (`frappe.get_doc({"doctype":"Customer","customer_name":"_CP Test / O'Brien & Co","customer_group": <first leaf group>,"territory": <first leaf territory>}).insert(ignore_permissions=True)`), plus a real customer with invoices chosen by SQL (`SELECT customer FROM tabSales Invoice WHERE docstatus=1 GROUP BY customer ORDER BY count(*) DESC LIMIT 1`).

```python
class TestCustomerPage(FrappeTestCase):
    def test_empty_customer_returns_empty_structures(self):
        h = C.crm_customer_header(self.empty)
        self.assertEqual(h["figures"]["order_count"], 0)
        self.assertIsNone(h["figures"]["last_order_date"])
        self.assertEqual(C.crm_customer_orders(self.empty)["rows"], [])
        self.assertEqual(C.crm_customer_orders(self.empty)["total"], 0)
        p = C.crm_customer_pricing(self.empty)
        self.assertEqual(p["rows"], []) if p["price_list"] is None else None
        self.assertEqual(C.crm_customer_contracts(self.empty)["rows"], [])
        self.assertEqual(C.crm_customer_overview(self.empty)["top_items"], [])

    def test_awkward_names_resolve(self):
        self.assertEqual(C.crm_customer_header(self.empty)["customer"]["name"], self.empty)

    def test_header_matches_direct_sql(self):
        h = C.crm_customer_header(self.busy)
        total = frappe.db.sql("select coalesce(sum(base_grand_total),0) from `tabSales Invoice` where customer=%s and docstatus=1", self.busy)[0][0]
        self.assertAlmostEqual(h["figures"]["lifetime_revenue"], float(total), places=2)
        n = frappe.db.count("Sales Order", {"customer": self.busy, "docstatus": 1})
        self.assertEqual(h["figures"]["order_count"], n)

    def test_orders_page_and_total(self):
        r = C.crm_customer_orders(self.busy, kind="Sales Invoice", page_len=5)
        self.assertLessEqual(len(r["rows"]), 5)
        self.assertEqual(r["total"], frappe.db.count("Sales Invoice", {"customer": self.busy, "docstatus": ["<", 2]}))

    def test_orders_page_len_is_clamped(self):
        self.assertLessEqual(len(C.crm_customer_orders(self.busy, kind="Sales Invoice", page_len=10_000)["rows"]), 100)

    def test_orders_rejects_unknown_kind(self):
        with self.assertRaises(frappe.ValidationError):
            C.crm_customer_orders(self.busy, kind="User")

    def test_unknown_customer_raises(self):
        with self.assertRaises(frappe.DoesNotExistError):
            C.crm_customer_header("__no_such_customer__")

    def test_customer_endpoints_require_customer_read(self):
        # Patch the permission check: building a real user who passes _guard but
        # lacks Customer read depends on site DocPerms this test should not own.
        from unittest.mock import patch
        with patch("upande_crm.api.customer.frappe.has_permission", side_effect=frappe.PermissionError):
            for fn in (C.crm_customer_header, C.crm_customer_overview, C.crm_customer_orders,
                       C.crm_customer_pricing, C.crm_customer_contracts):
                with self.assertRaises(frappe.PermissionError):
                    fn(self.busy)

    def test_module_off_refuses(self):
        _save(module_customer_page=0)
        with self.assertRaises(frappe.PermissionError):
            C.crm_customer_header(self.busy)
```

Also add every new endpoint under `"customer_page"` in `test_modules_gated.GATED`.

- [ ] **Step 2: Run** → FAIL (no module).
- [ ] **Step 3: Implement** `api/customer.py`, reusing `_guard`, `_has`, `_company_currency` from `api/crm.py`. Month trend: `DATE_FORMAT(posting_date,'%%Y-%%m')` grouping over the last 12 months, zero-filled in Python. Pricing: if `Customer.default_price_list` is set use it (`source="customer"`), else `Customer Group.default_price_list` (`source="customer_group"`), else None. Item Price query filtered by `price_list` and optional `search` (`item_code LIKE %s OR item_name LIKE %s`, escaping `_`/`%` with `frappe.db.escape`-safe `LIKE` params (memory: unescaped `_` wildcard)). Contracts: `available = _has("Contract")`. `tabs` / `default_tab` come from settings `custpage_tabs` (via `parse_lines`) and `custpage_default_tab`.
- [ ] **Step 4: Run** `test_customer_page`, `test_modules` → PASS.
- [ ] **Step 5: Commit** `feat(crm): a customer page API — header, orders, pricing, contracts`.

---

### Task 5: Customer timeline and notes

**Files:**
- Modify: `upande_crm/api/customer.py`
- Test: `upande_crm/tests/test_customer_page.py`

**Interfaces — Produces:**
- `crm_customer_timeline(name, kinds=None, before=None, limit=50) -> {items:[{kind, when, title, snippet, who, ref_doctype, ref_name}], next_before: str|None}`. `kinds` is a JSON list or comma string ⊆ `("email","call","whatsapp","event","task","note")`; `before` is an ISO datetime for keyset paging; `limit` is clamped to 1–100.
- `crm_customer_add_note(name, content) -> {item}`. Requires non-blank content (after stripping HTML) and Customer **write** or comment permission (`frappe.has_permission("Customer","read",name)` is sufficient because Comment adds need read; follow `frappe.desk.form.utils.add_comment` semantics). Inserts `Comment` with `comment_type="Comment"`, `reference_doctype="Customer"`, `reference_name=name`, `content`.

Sources (each at most `limit` rows with `when < before`, merged, sorted desc, cut to `limit`):
- **email**: `Communication` where `communication_medium='Email'` and (`reference_doctype='Customer' AND reference_name=%s` OR `timeline_links` (`tabCommunication Link` `link_doctype='Customer' AND link_name=%s`) OR the reference is one of the scope's Lead/Opportunity/Quotation names from `scope.customer_scope`). when=`communication_date`, title=`subject`, who=`sender`, snippet = first 160 chars of stripped `content`.
- **call**: `Call Log` where `customer=%s` or Dynamic Link to the Customer. when=`creation`, title=f"{type} call", who=`owner`, snippet=`summary`.
- **whatsapp**: only if `is_enabled("wa")` and the doctype exists. `WhatsApp Message` where `reference_doctype='Customer' AND reference_name=%s`. when=`creation`, title=`type`, snippet=`message`.
- **event**: `Event` names from `scope.event_names(scope)` plus Event Participants `reference_doctype='Customer'`. when=`starts_on`.
- **task**: `ToDo` names from `scope.todo_names(scope)` plus `reference_type='Customer' AND reference_name=%s`. when=`creation`, title = stripped description (80 chars).
- **note**: `Comment` `comment_type='Comment' AND reference_doctype='Customer' AND reference_name=%s`. when=`creation`, who=`comment_email`.

`next_before` = the `when` of the last item when `len(items) == limit`, else None.

- [ ] **Step 1: Failing tests**

```python
    def test_note_round_trips_into_the_timeline(self):
        C.crm_customer_add_note(self.empty, "<p>Met at IFTF, wants samples</p>")
        t = C.crm_customer_timeline(self.empty)
        self.assertEqual(t["items"][0]["kind"], "note")
        self.assertIn("samples", t["items"][0]["snippet"])

    def test_blank_note_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            C.crm_customer_add_note(self.empty, "<p> </p>")

    def test_timeline_filters_by_kind(self):
        C.crm_customer_add_note(self.empty, "a note")
        self.assertEqual(C.crm_customer_timeline(self.empty, kinds="email")["items"], [])

    def test_timeline_pages_by_keyset(self):
        t1 = C.crm_customer_timeline(self.busy, limit=5)
        if t1["next_before"]:
            t2 = C.crm_customer_timeline(self.busy, limit=5, before=t1["next_before"])
            self.assertTrue(all(i["when"] < t1["next_before"] for i in t2["items"]))

    def test_timeline_is_newest_first(self):
        whens = [i["when"] for i in C.crm_customer_timeline(self.busy, limit=30)["items"]]
        self.assertEqual(whens, sorted(whens, reverse=True))

    def test_unknown_kind_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            C.crm_customer_timeline(self.busy, kinds="sms")
```

`when` values are normalised to `str(datetime)` so they compare lexically. Add both endpoints to `GATED["customer_page"]`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `test_customer_page`, `test_modules` → PASS.
- [ ] **Step 5: Commit** `feat(crm): one timeline per customer, and notes that land on it`.

---

### Task 6: Customer page UI and hash routing

**Files:**
- Create: `frontend/src/sections/CustomerPage/index.jsx`, `Header.jsx`, `Overview.jsx`, `Timeline.jsx`, `Orders.jsx`, `Pricing.jsx`, `Contracts.jsx`
- Create: `frontend/src/lib/customer.js` (API wrappers, using the same `call` helper as `api.js`)
- Modify: `frontend/src/store.js` (hash sync; `openCustomer(name)`; `SECTION_META.custpage = { title: 'Customer', sub: '' }`)
- Modify: `frontend/src/App.jsx` (`custpage: CustomerPage` lazy)
- Modify: `frontend/src/components/DataTable.jsx` (new optional `onRowClick(row)` prop, which takes precedence over the desk link)
- Modify: `frontend/src/sections/Customers.jsx` (All/My/Top rows → `openCustomer`), `components/TopBar.jsx` search hits of type Customer, `sections/Territories/PinnedDetail.jsx` customer rows, and `Opportunities.jsx`/`Prospects.jsx` party links where the party is a Customer. Each goes through a `customerLink(name)` helper in `lib/crm.js`: `moduleOn('customer_page') ? openCustomer(name) : openFrappe('Customer', name)`.

**Interfaces — Consumes:** Task 4/5 endpoints; `moduleOn`. **Produces:** `openCustomer(name)`; hash format `#<section>[/<table>]`, where `table` is `encodeURIComponent`-encoded.

- [ ] **Step 1: Hash sync.** In `store.select`, after `set`, write `location.hash = '#' + section + (table ? '/' + encodeURIComponent(table) : '')` when it differs. Add `initHash()`, called from App's boot effect after `loadOrg`: it parses the hash (split on the first `/`, `decodeURIComponent` the rest) and calls `select` if the section is in `SECTIONS`. A `hashchange` listener does the same, guarded against re-entry by comparing with the current state. `openCustomer = (name) => get().select('custpage', name)`.
- [ ] **Step 2: Page.** `index.jsx` reads `table` as the customer name, fetches the header (`crm_customer_header` with the store's date range), renders `Header` and a tab strip from `header.tabs`, and starts on `default_tab`. The active tab is kept in local state and each tab component fetches its own data on mount. Loading and error states use `crm-empty`. A PermissionError shows "You don't have access to this customer" or "The customer page is switched off".
  - `Header.jsx`: name, a group/territory/price-list line, account manager, Active/Disabled badge, `KpiRow` for the six figures (money via `fmtMoney(v, currency)`), and quick actions: Log call (`openCall` with the Customer ref), Email (`openCompose({ to: '', ref: {doctype:'Customer', name} })` — match ComposeDialog's existing props), WhatsApp (`select('wa')` filtered — only if `moduleOn('wa')`), New event (`openEvent` with ref), Add note (switches to the Timeline tab with the note box focused), and Open in desk (`openFrappe`). Each is hidden when its module is off.
  - `Overview.jsx`: `AreaTrendChart` for trend, `HBarsChart` for top items, a next-event card and an open-tasks list.
  - `Timeline.jsx`: kind chips (multi-toggle), a note textarea with a Save button (`crm_customer_add_note`, then prepend), and the list of items with an icon per kind, when (`fmtDate`), title, snippet and who. Clicking an item opens `openFrappe(ref_doctype, ref_name)`. "Load older" uses `next_before`.
  - `Orders.jsx`: a segmented control for kind, a status select, a `DataTable` with `doctype={kind}`, a pager (Prev/Next with `start`, showing "x–y of total"), and the summary strip.
  - `Pricing.jsx`: a banner saying "Prices from price list **X** (the customer's own list / inherited from customer group)", a search box, and a table of item, UOM, list rate, last invoiced rate + date (flagged `bdg-warn` when they differ by >0.5%), with a pager.
  - `Contracts.jsx`: a table, or the empty state "No contracts recorded — contracts entered in ERPNext appear here."
- [ ] **Step 3: Wire links** per the Files list.
- [ ] **Step 4: Build** `yarn build`. Manual on kaitet.local via `http://kaitet.local:8002`, or whichever host serves kaitet.local (memory: :8002 serves webstore.localhost by default, so use `bench --site kaitet.local serve --port 8010` in the background if needed). Open Customers → click the busiest customer and check the header figures against the desk, flip through each tab, add a note, reload with the hash intact, and press Back to return to the list. Also check a customer whose name contains `&`.
- [ ] **Step 5: Commit** `feat(crm): the customer page — one place for a customer's whole story`.

---

### Task 7: Theme backend — drop presets, add colour, font, shape and CSS seeds, add a preview endpoint

**Files:**
- Delete: `upande_crm/theme/transfer.py`, `upande_crm/theme/presets/`
- Create: `upande_crm/theme/fonts.py` (port of webstore's, CRM field names)
- Modify: `upande_crm/theme/tokens.py`, `upande_crm/theme/__init__.py` (add `get_font_link(settings=None)`)
- Modify: doctype JSON (remove `theme_preset`; add fields below), controller validation
- Modify: `upande_crm/api/settings.py` (`DEFAULTS`, `OPTIONS`, `_theme_payload`, `_write_seeds`, remove `crm_theme_apply_preset`, rewrite `crm_theme_reset`, add `crm_theme_preview`)
- Modify: `upande_crm/www/customer_relationship_management.py` (`context.theme_font_link`) and the www html template (a `<link>` when set)
- Test: `upande_crm/tests/test_theme.py`

**Interfaces — Produces:**
- `tokens.SEED_FIELDS` = colour seeds only (existing 8 + `theme_accent_dark, theme_accent_soft, theme_wash, theme_border, theme_border_strong`); `tokens.THEME_FIELDS` = SEED_FIELDS + `theme_accent_primary, theme_font_sans, theme_font_sans_name, theme_font_display, theme_font_display_name, theme_font_mono, theme_font_mono_name, theme_google_fonts_url, theme_radius, theme_radius_card, theme_radius_panel, theme_custom_css`
- `tokens.get_tokens(settings)` also emits: `f`, `display`, `mono` (font stacks), `radius`, `r-sm`, `r-card`, `r-panel`
- `tokens.get_theme_css(settings)` appends `theme_custom_css` inside `:root` last
- `tokens.contrast_report(tokens: dict) -> [{key, label, fg, bg, ratio, level: "ok"|"warn"|"bad"}]` for pairs: text/bg ("Main text on page"), text-3/bg ("Muted text on page"), on-accent/gold ("Button text on brand colour", only if accent_primary), gold-text/gold-soft ("Brand text on pale tint"), and good/good-soft, warn/warn-soft, bad/bad-soft, info/info-soft ("Success badge" …). Unresolved tokens fall back to shipped values parsed from a `SHIPPED` dict in tokens.py.
- `crm_theme()` / `_theme_payload` → `{seeds: {field: value for THEME_FIELDS}, tokens, derived: tokens for the same settings with no pins (for "worked out for you" swatches), contrast, fonts: {sans:[...], display:[...], mono:[...]}, can_edit, installed}`
- `crm_theme_save(seeds)` accepts THEME_FIELDS; `crm_theme_preview(seeds)` → same payload shape computed on `dict(get_settings(), **known)` with no write; `crm_theme_reset()` blanks every THEME_FIELD (Check → 0).
- Bundled families: sans `Poppins, Inter, IBM Plex Sans, Space Grotesk`; display `Fraunces`; mono `IBM Plex Mono`; plus `Custom`. Select options start with a blank.

Pins in `get_tokens` (applied after derivation, so a set seed overrides the derived value):
- `theme_accent_dark` → `gold-2`, `gold-text`, and `grad-gold` deep stop (rebuild the gradient string)
- `theme_accent_soft` → `gold-soft`, `selected`
- `theme_accent_primary` (truthy and accent set) → `primary` = hsl(accent), `primary-foreground` = hsl(on-accent), `ring` = hsl(accent); `nav-active` = accent hex, `nav-active-fg` = on-accent (new tokens; the default CSS defines `--nav-active: var(--ink)` and `--nav-active-fg: #fff`, or whatever the Sidebar uses today — audit it in Task 8)
- `theme_wash` → `surface-3`, `secondary`, `muted` (hsl)
- `theme_border` → `line`, `border`, `input`, `accent` (hsl channels as `_shadcn_channels` does), and `hairline` = rgba of the border at 0.6 alpha
- `theme_border_strong` → `line-2`
- radius: `theme_radius` → `radius` and `r-sm`; `theme_radius_card` → `r-card`; `theme_radius_panel` → `r-panel`

Validation (controller `_validate_theme_extras`): radius values match `^(0|\d+(\.\d+)?(px|rem|em))$`, otherwise throw "Corner sizes need a unit, e.g. 8px or 0.5rem". Custom font choice requires its `_name`, and requires `theme_google_fonts_url` to be set. The URL must pass `fonts.is_allowed_url`. `theme_custom_css` must not contain `</style` or `<` at all. Font names must match `^[A-Za-z0-9 \-]+$`.

- [ ] **Step 1: Update tests.** Remove the preset tests (`test_both_shipped_presets_are_listed`, `test_presets_carry_a_label_and_seeds`, `test_upande_preset_is_the_shipped_palette`, `test_karen_roses_preset_is_maroon`, `test_traversal_and_junk_names_are_refused`, `test_unknown_preset_throws`, `test_apply_preset_*`, `test_hand_edited_seeds_clear_the_preset_marker`), the `transfer` import, and any `payload_shape` references to presets. Add:

```python
class TestThemeExtras(FrappeTestCase):
    def test_blank_new_seeds_change_nothing(self):
        base = T.get_tokens(SHIPPED_SEEDS)
        blank = dict(SHIPPED_SEEDS, **{f: "" for f in T.THEME_FIELDS if f not in SHIPPED_SEEDS})
        self.assertEqual(T.get_tokens(blank), base)

    def test_accent_dark_pins_its_tokens(self):
        t = T.get_tokens(dict(SHIPPED_SEEDS, theme_accent_dark="#553300"))
        self.assertEqual(t["gold-2"], "#553300"); self.assertEqual(t["gold-text"], "#553300")
        self.assertIn("#553300", t["grad-gold"])

    def test_accent_soft_pins_selected(self):
        t = T.get_tokens(dict(SHIPPED_SEEDS, theme_accent_soft="#fff1d6"))
        self.assertEqual(t["gold-soft"], "#fff1d6"); self.assertEqual(t["selected"], "#fff1d6")

    def test_wash_and_borders_pin(self):
        t = T.get_tokens(dict(SHIPPED_SEEDS, theme_wash="#eeeeee", theme_border="#dddddd", theme_border_strong="#bbbbbb"))
        self.assertEqual(t["surface-3"], "#eeeeee"); self.assertEqual(t["line"], "#dddddd"); self.assertEqual(t["line-2"], "#bbbbbb")
        self.assertEqual(t["border"], color.to_hsl_channels(color.parse("#dddddd")))

    def test_accent_primary_repaints_primary(self):
        t = T.get_tokens(dict(MAROON_SEEDS, theme_accent_primary=1))
        self.assertEqual(t["primary"], color.to_hsl_channels(color.parse("#8c1d2e")))
        self.assertEqual(t["nav-active"], "#8c1d2e")

    def test_accent_primary_without_accent_does_nothing(self):
        self.assertEqual(T.get_tokens({"theme_accent_primary": 1}), {})

    def test_bundled_font_sets_the_stack(self):
        t = T.get_tokens({"theme_font_sans": "Inter"})
        self.assertTrue(t["f"].startswith('"Inter"'))

    def test_custom_font_needs_a_name(self):
        self.assertNotIn("f", T.get_tokens({"theme_font_sans": "Custom"}))

    def test_radius_seeds_emit_tokens(self):
        t = T.get_tokens({"theme_radius": "4px", "theme_radius_card": "0", "theme_radius_panel": "1rem"})
        self.assertEqual((t["r-sm"], t["radius"], t["r-card"], t["r-panel"]), ("4px", "4px", "0", "1rem"))

    def test_custom_css_is_appended_last(self):
        css = T.get_theme_css({"theme_accent": "#d9a514", "theme_custom_css": "--ink-4: #54586b;"})
        lines = css.strip().splitlines()
        self.assertEqual(lines[-1], "}")
        self.assertEqual(lines[-2].strip(), "--ink-4: #54586b;")

    def test_contrast_report_flags_unreadable_text(self):
        t = T.get_tokens(dict(SHIPPED_SEEDS, theme_ink="#f0f0f0"))
        rep = {r["key"]: r for r in T.contrast_report(t)}
        self.assertEqual(rep["text_on_bg"]["level"], "bad")

    def test_contrast_report_passes_the_shipped_palette(self):
        rep = T.contrast_report(T.get_tokens(SHIPPED_SEEDS))
        self.assertEqual(next(r for r in rep if r["key"] == "text_on_bg")["level"], "ok")

class TestThemeValidation(FrappeTestCase):
    def tearDown(self): frappe.db.rollback(); _clear()
    def _save(self, **kw):
        doc = frappe.get_single(S.SETTINGS_DOCTYPE); doc.update(kw); doc.save(ignore_permissions=True)

    def test_radius_requires_a_css_length(self):
        for bad in ("12", "1e3px", "10 px", "calc(1px)"):
            with self.assertRaises(frappe.ValidationError, msg=bad):
                self._save(theme_radius=bad)

    def test_font_url_host_is_enforced(self):
        with self.assertRaises(frappe.ValidationError):
            self._save(theme_font_sans="Custom", theme_font_sans_name="Lato", theme_google_fonts_url="https://evil.example/x.css")

    def test_custom_css_cannot_close_the_style_tag(self):
        with self.assertRaises(frappe.ValidationError):
            self._save(theme_custom_css="</style><script>alert(1)</script>")

    def test_reset_clears_every_theme_field(self):
        frappe.set_user("Administrator")
        S.crm_theme_save(json.dumps({"theme_accent": "#8c1d2e", "theme_radius": "4px", "theme_accent_primary": 1}))
        S.crm_theme_reset(); _clear()
        s = S.get_settings()
        self.assertTrue(all(not s.get(f) for f in T.THEME_FIELDS))
        self.assertEqual(get_theme_css(), "")

    def test_preview_does_not_write(self):
        frappe.set_user("Administrator")
        out = S.crm_theme_preview(json.dumps({"theme_accent": "#123456"}))
        self.assertEqual(out["tokens"]["gold"], "#123456")
        _clear(); self.assertNotEqual(S.get_settings()["theme_accent"], "#123456")

    def test_theme_preset_field_is_gone(self):
        self.assertFalse(frappe.get_meta(S.SETTINGS_DOCTYPE).has_field("theme_preset"))
```

Adjust `test_reset_returns_to_upande_gold` → covered by `test_reset_clears_every_theme_field`, so delete it. Keep `test_seed_fields_are_all_known_settings_keys`, extended to cover THEME_FIELDS.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** per the Interfaces above. Remove `theme_preset` from DEFAULTS and the JSON. Add the new fields to the JSON's Theme section in this order: Brand (accent, accent_dark, accent_soft, accent_primary), Neutral (ink, ink_muted, canvas, wash, border, border_strong), Status (4), Fonts, Shape, Advanced (`theme_custom_css` Code/CSS). Put the plain-English help in each field's `description` too, so the desk form explains itself. Add font select options to `OPTIONS`.
- [ ] **Step 4:** `bench --site kaitet.local migrate`; run `test_theme`, `test_settings` → PASS.
- [ ] **Step 5: Commit** `feat(crm): a theme without presets — brand, neutral, status, fonts and shape`.

---

### Task 8: Theme frontend — bundled fonts, radius variables, the new Theme tab

**Files:**
- Create: `upande_crm/public/fonts/*.woff2` (copy from `apps/upande_webstore/upande_webstore/public/fonts/`: poppins 400–700, inter 400–700, ibm-plex-sans 400–600, space-grotesk 500/700, fraunces 500/600/600-italic/700, ibm-plex-mono 400/600)
- Create: `upande_crm/public/css/fonts.css` (`@font-face` rules pointing at `/assets/upande_crm/fonts/...`, `font-display: swap`)
- Modify: `frontend/index.html` and the build-html script / www template: link `/assets/upande_crm/css/fonts.css`; remove the Poppins/Fraunces Google `<link>` + preconnects (keep Material Symbols)
- Modify: `frontend/src/index.css` (add `--r-sm: 9px; --r-card: 14px; --r-panel: 18px; --nav-active; --nav-active-fg` with today's values; replace hard-coded radii)
- Modify: `frontend/tailwind.config.js` if card/dialog radii come from Tailwind classes (map `rounded-card` → `var(--r-card)`, `rounded-panel` → `var(--r-panel)`)
- Modify: `frontend/src/components/Sidebar.jsx` (active item uses `--nav-active`/`--nav-active-fg`)
- Rewrite: `frontend/src/sections/Settings/Theme.jsx`; create `frontend/src/sections/Settings/ThemePreview.jsx`
- Modify: `frontend/src/api.js` (`themePreviewApi`), and remove `themeApplyPresetApi`

**Interfaces — Consumes:** Task 7 payload. **Produces:** none downstream.

- [ ] **Step 1: Radius audit.** `grep -n "border-radius" frontend/src/index.css` and `grep -rn "rounded-\(lg\|xl\|2xl\|\[" frontend/src/components frontend/src/sections | head -80`. Classify each as control (≤10px) → `var(--r-sm)`, card/table (11–16px) → `var(--r-card)`, dialog/panel (≥17px) → `var(--r-panel)`. `999px` and `50%` stay. Record the default for each variable as the most common current value in its class, so the default look is unchanged.
- [ ] **Step 2: Fonts.** Copy the files and write `fonts.css`. Confirm that `--f`, `--display` and `--mono` in `index.css` still name Poppins/Fraunces and resolve to the local files. In `build-html.mjs` / `index.html`, swap the links. Put the `theme_font_link` `<link>` in the www template via Jinja (`{% if theme_font_link %}`).
- [ ] **Step 3: Theme.jsx.** Two columns (`grid lg:grid-cols-[minmax(0,1fr)_380px]`), preview `sticky top-4`, stacked on narrow screens.
  - Sections are `Panel`s: **Brand colours**, **Neutral colours**, **Status colours**, **Fonts**, **Shape**, **Advanced** (collapsed `<details>`, "For developers").
  - Each colour row: label; plain-English line (`text-[12.5px] text-ink-3`); "Technically: …" line (`text-[11px] text-ink-mute`); picker + hex input (the existing `ColorRow`, extended). When blank, the swatch shows `derived[token]` at 50% opacity with "worked out for you", and a "Clear" link appears when set.
  - `theme_accent_primary` is a switch row. Fonts: a select per role (options from payload `fonts`), a name input shown when Custom, and a single Google Fonts URL input shown when any role is Custom. Shape: per field, `<input type=range min=0 max=28>` + numeric input in px + a "Square corners" checkbox (sets `0`); the stored value is `${n}px`.
  - Contrast list below the preview: one row per report item with a swatch pair, ratio to 1 dp, and ✓ Readable / ⚠ Hard to read for small text / ⚠ Hard to read.
  - Draft changes are debounced 250ms and trigger `themePreviewApi(draft)`. The response's `tokens` feed the preview, and `contrast` feeds the list. Save calls `crm_theme_save`, then `location.reload()` is offered ("Saved — reload to see it everywhere"). "Reset to default" asks for confirmation, then calls `crm_theme_reset`.
  - Copy (exact text): see the Plain-English table below.
- [ ] **Step 4: ThemePreview.jsx.** A `div` whose `style` sets each token as `--name: value`. Shadcn channel tokens are set bare, as the server returns them. Inside it: a mini sidebar (3 items, one active), a KPI tile, a Primary button and an Outline button (the real `Button`), the four `.bdg` status badges, a two-row `.tbl` with one row in hover style, a `.bdg`-style accent chip, an `Input`, and a 4-bar chart made from divs using `--gold`, `--info`, `--good`, `--ink-4`. Headings use `var(--display)`, numbers `var(--mono)`.
- [ ] **Step 5: Build and verify** — `yarn build`. Manual: change Accent → preview updates before save; save → reload → app repainted; Inter body font applied; card radius 0 → square cards; Reset → shipped look, and the page `<head>` has no theme `<style>`. Check DevTools Network: no request to fonts.googleapis.com except Material Symbols.
- [ ] **Step 6: Commit** `feat(crm): a theme editor that explains itself, with a live preview`.

Plain-English copy (label — plain line — technically):

| Field | Plain | Technically |
|---|---|---|
| Accent | Your brand colour. Used for highlights, badges, charts and the focus ring. | --gold family, chart series, focus ring |
| Accent dark | A deeper version of your brand colour, for brand-coloured text on white and the dark end of buttons. | --gold-2, --gold-text, gradient deep stop |
| Accent soft | A very pale version, used behind highlighted badges and selected rows. | --gold-soft, --selected |
| Use accent for main buttons | Off: main buttons are near-black and your brand colour is just trim. On: buttons and the active menu item use your brand colour. | --primary, --ring, active nav |
| Ink | The main text colour. It also tints every grey and every shadow, so this one choice changes the feel of the whole app. | text, 7-step grey scale, shadows |
| Muted text | Secondary text like dates, labels and hints. Pick a warm or cool grey to set the mood. | --ink-mute, --text-3 |
| Page canvas | The background behind all the cards. | --bg, lighter surfaces derive from it |
| Muted fill | Slightly darker patches: row hover, quiet panels, the search box. | --surface-3, secondary/muted fills |
| Border | Thin lines around cards, inputs and between table rows. | --line, --border, --input, hairlines |
| Border strong | Heavier dividers and the edge of outlined buttons. | --line-2 |
| Success | Good news: won deals, paid invoices, completed tasks. | --good + pale badge fill |
| Warning | Needs attention: overdue tasks, pending quotations. | --warn + pale badge fill |
| Danger | Problems: lost deals, failed messages, errors. | --bad, destructive buttons |
| Info | Neutral notes and secondary chart lines. | --info + pale badge fill |
| Body font | The font for almost everything — text, buttons, tables. | --f |
| Headings font | Big page titles and panel headings. | --display |
| Numbers font | Figures in KPI tiles and codes like invoice numbers. | --mono |
| Small corners | How rounded buttons, inputs and badges are. | --radius, --r-sm |
| Card corners | How rounded cards, KPI tiles and tables are. | --r-card |
| Panel corners | How rounded dialogs and large panels are. | --r-panel |
| Custom CSS | For developers: exact overrides, applied last. | appended inside :root |

---

### Task 9: Docs and final verification

**Files:**
- Modify: `docs/wiki/wiki.json` and add `docs/wiki/sections/customer-page.md`, `docs/wiki/admin/modules.md`; update `docs/wiki/admin/*theme*` if present (grep for "preset" under `docs/wiki` and rewrite those passages)
- Modify: spec — record the preview-endpoint deviation

- [ ] **Step 1:** Write the wiki pages in the house style (read two existing pages first): what each module switch does, how to reach the customer page, what each tab shows, and where the data comes from (including the "price list, not per-customer pricing" and "no contracts yet" notes).
- [ ] **Step 2:** Full suite: `bench --site kaitet.local run-tests --app upande_crm` → all PASS. `yarn build` clean.
- [ ] **Step 3:** Request a code review of the whole change set (superpowers:requesting-code-review) and address findings.
- [ ] **Step 4: Commit** `docs(crm): modules, the customer page, and the new theme editor`.
