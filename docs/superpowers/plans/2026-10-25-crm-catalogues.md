# CRM Catalogues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shareable price catalogues in Upande CRM. Buyers open a public or
personal link, tick lines with box quantities, and land in the CRM as a Lead (or
against their existing Lead/Customer) with a Catalogue Interest record.

**Architecture:** Five new doctypes in module Upande CRM (opens are counted on the link/catalogue rather than a visit table: the spec's Builder's call). Three Python API
modules: `api/catalogues.py` (CRM side, role-gated, behind module `cat`),
`api/catalogue_import.py` (xlsx → preview lines) and `api/catalogue_public.py`
(guest, token-scoped, rate-limited). A server-rendered guest page at
`/catalogue/<token>` with vanilla JS. A new SPA section `cat` (catalogue list,
editor, share dialog, interests).

**Tech Stack:** Frappe/ERPNext v16, Python (openpyxl, already in the bench env),
React 18 + Vite SPA (`frontend/`), vanilla JS/CSS for the guest page.

**Spec:** `docs/superpowers/specs/2026-10-25-crm-catalogues-design.md`

**Test site:** `webstore.localhost`. Run
`bench --site webstore.localhost run-tests --app upande_crm --module upande_crm.tests.<module>`
from `/home/austin/frappe-v16-bench`. The SPA builds with
`cd apps/upande_crm/frontend && npm run build`.

## Global Constraints

- Frappe/ERPNext **v16**. No SQL functions in `get_list` `fields=` (use `frappe.qb`), escape `_` in LIKE, and new Single fields need the existing backfill (`patches/backfill_module_switches.py` already reads JSON defaults, so add each field to the settings JSON with a default).
- CRM endpoints: `@frappe.whitelist()` then `@requires_module("cat")`, then `_guard()` first thing. Reads degrade to empty; writes throw.
- Guest endpoints: `@frappe.whitelist(allow_guest=True)`, never `_guard()`. Every call re-resolves the token and re-checks status and validity.
- A public submission creates at most a **Lead**. Never a User, Customer or Contact-with-portal-access.
- Existing Leads/Customers are never modified by buyer input. Only comments are added.
- The WhatsApp channel must not break sites without `frappe_whatsapp`. Use `api.whatsapp._available()`.
- Sends throw. A failed email or WhatsApp send never reports success.
- Vite: keep the existing chunking (only the react-core leaf chunk). New sections are `lazy()` like the others.
- Commits are authored by ghost-mann, with no Claude co-author line (user's instruction).

## Review Focus

1. **Lead insert on sites with custom mandatory Lead fields** (the Kaitet sites have nine). A guest submission must still create the Lead. Insert with `flags.ignore_mandatory = True` → test in Task 4.
2. **Same email typed in a different case or with spaces**, or a phone number in another format. It must still match the existing party → test in Task 4.
3. **A price missing for one currency.** The page shows "—" and a submission in that currency snapshots `None`, not 0 → test in Task 2 (validation) and Task 4 (snapshot).
4. **Re-submitting the same personal link twice.** That creates two interests, not an error and not a second Lead → test in Task 4.
5. **Offer sheet with merged header cells and summary rows** (`Aster (5 varieties)`, colour `All`). The import must not crash, and lists them as unmatched → test in Task 3.

---

### Task 1: Module switch, settings fields and doctypes

**Files:**
- Modify: `upande_crm/modules.py`: add `Module("cat", "module_catalogues", "Catalogues", ("cat",), "Pipeline", "Share price catalogues by link and collect buyers' interest as leads.", True)`
- Modify: `upande_crm/upande_crm/doctype/upande_crm_settings/upande_crm_settings.json`: add a Check `module_catalogues` (default 1), Data `catalogue_whatsapp_template`, Data `catalogue_email_subject` (default `"{catalogue}: our current offer"`), Text `catalogue_email_body` (default `"Hello {name},\n\nOur current offer is here: {link}\n\nTick what you'd like and send it back; we'll be in touch."`)
- Modify: `upande_crm/api/settings.py` `DEFAULTS`: mirror the three text fields
- Create doctypes (module Upande CRM, under `upande_crm/upande_crm/doctype/`):
  - `crm_catalogue` (naming `CAT-.YYYY.-.####`). Fields: title (reqd), company (Link Company, reqd), status (Draft/Live/Closed, default Draft), valid_from, valid_to (Date), currencies (Data, reqd, comma list, e.g. `USD, EUR`), volume_tier_qty (Int), terms (Text Editor), public_token (Data, unique, read_only), views (Int, read_only), lines (Table → CRM Catalogue Line)
  - `crm_catalogue_line` (istable). Fields: item (Link Item, reqd), item_name (fetch), grade, box_type (default `Standard`), color, info_url, vbn (Data), pack_qty (Float), bunch (Data), weight (Float), prices (JSON)
  - `crm_catalogue_link` (naming hash). Fields: catalogue (Link, reqd), party_type (Select Lead/Customer), party (Dynamic Link), contact_email, contact_phone, token (Data, unique), sent_via (Email/WhatsApp/Copied), sent_by (Link User), sent_on (Datetime), first_opened_on, last_opened_on (Datetime), open_count (Int)
  - `crm_catalogue_interest` (naming `CEI-.YYYY.-.#####`). Fields: catalogue, via_link (Link CRM Catalogue Link), party_type, party, contact_name, company_name, email, phone, country, message, currency, status (New/Contacted/Converted/Dropped, default New), opportunity (Link Opportunity), items (Table → CRM Catalogue Interest Item)
  - `crm_catalogue_interest_item` (istable). Fields: line_ref (Data, the catalogue line's `name`), item, item_name, grade, box_type, pack_qty, qty (Float, boxes), frequency (Select One-off/Weekly), price, tier_price (Float, no default, nullable)
  - DocPerms on all four parents: Sales User and Sales Manager read/write/create (`if_owner` write for Sales User on CRM Catalogue), System Manager full.
- Test: `upande_crm/tests/test_catalogue_model.py`

**Interfaces:**
- Produces: `CRMCatalogue.price_for(line, currency) -> tuple[float|None, float|None]`, `CRMCatalogue.currency_list() -> list[str]`, `CRMCatalogue.is_open(today=None) -> bool` (Live, and today within the optional dates). `public_token` is set on insert with `frappe.generate_hash(length=24)`.

- [ ] **Step 1: Write failing tests** in `test_catalogue_model.py`:
  - `test_token_is_set_and_unique`: two catalogues get different 24-char tokens.
  - `test_currencies_validated`: `"USD, XXX"` raises `ValidationError`, and `"usd, eur"` is stored as `"USD, EUR"`.
  - `test_line_prices_only_for_catalogue_currencies`: prices `{"GBP": {...}}` on a USD catalogue raise.
  - `test_missing_currency_price_is_none`: `price_for(line, "EUR") == (None, None)` when only USD is set.
  - `test_is_open`: Draft → False. Live → True. Live with `valid_to` yesterday → False. Closed → False.
  - `test_module_registered`: `"cat" in enabled_map()`.
- [ ] **Step 2: Run, expect FAIL** (doctype missing). `bench --site webstore.localhost run-tests --app upande_crm --module upande_crm.tests.test_catalogue_model`
- [ ] **Step 3: Create the JSONs and controllers.** Then `bench --site webstore.localhost migrate`.
- [ ] **Step 4: Run, expect PASS.** Also re-run `test_modules`, `test_settings` and `test_modules_gated`.
- [ ] **Step 5: Commit** `feat(catalogues): doctypes and the module switch`

### Task 2: CRM-side catalogue API

**Files:**
- Create: `upande_crm/api/catalogues.py`
- Test: `upande_crm/tests/test_catalogues.py`

**Interfaces:**
- Consumes: Task 1 doctypes and controller methods.
- Produces (all `@frappe.whitelist()` + `@requires_module("cat")`):
  - `crm_catalogues() -> {"rows": [...], "available": bool}`. Each row: name, title, company, status, valid_from, valid_to, currencies, owner, views, links, opened, interests, lines.
  - `crm_catalogue_get(name) -> {"catalogue": {..., "lines": [...]}, "public_url": str}`
  - `crm_catalogue_save(catalogue: json) -> {"catalogue": ...}` (POST). Creates or updates, replaces lines wholesale. Editable fields only.
  - `crm_catalogue_status(name, status)` (POST)
  - `crm_catalogue_duplicate(name) -> {"name": new}` (POST). Copies everything, status Draft, new token.
  - helper `catalogue_url(token) -> str` = `frappe.utils.get_url(f"/catalogue/{token}")`

- [ ] **Step 1: Failing tests:**
  - `test_save_and_get_roundtrip`: lines with prices for USD+EUR come back identical.
  - `test_sales_user_cannot_edit_others_catalogue`: as a test Sales User, saving a catalogue owned by Administrator raises `PermissionError`.
  - `test_duplicate_gets_new_token_and_draft`
  - `test_list_counts`: after inserting one link and one interest, row `links == 1`, `interests == 1`.
  - `test_module_off_refuses`: with `module_catalogues = 0`, `crm_catalogues()` raises `PermissionError`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Counts come from `frappe.qb` group-by queries, not `get_list` fields.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `feat(catalogues): build, list and duplicate catalogues`

### Task 3: Offer-sheet import

**Files:**
- Create: `upande_crm/api/catalogue_import.py`
- Test: `upande_crm/tests/test_catalogue_import.py`, plus a fixture `upande_crm/tests/fixtures/offer_sheet_sample.xlsx` (a 4-row trimmed copy of the real sheet with the same two header rows: the Standard Box and 1/8th-box blocks, and one "Aster (5 varieties)" row)

**Interfaces:**
- Produces:
  - `parse_offer_sheet(content: bytes, currencies: list[str]) -> list[dict]`. Each dict holds product, vbn, grade, color, info_url, box_type, pack_qty, bunch, weight, and `prices` `{cur: {"price", "tier"}}`. Pure function, no DB.
  - `match_items(rows) -> list[dict]`, which adds `item` (or None) and `match` (`"vbn" | "name" | "normalised" | None`)
  - Endpoint `crm_catalogue_import(file_url, currencies) -> {"lines": [...matched], "unmatched": [...]}` (POST, `cat` module). `file_url` is a private File uploaded through the standard upload.

Sheet rules (from the real file): tab names map to currencies as `USD→USD` and `Euro|EUR→EUR`. The header row is the first row containing `Product`, `VBN`, `Grade`. The row below it holds the sub-headers (`Packrate`, `Bunch`, `Price`, `Price >4 boxes`, `Weight`). The first `Packrate` starts the Standard block, and the next `Packrate` group, under the `1/8th box` header, is the 1/8 block. Rows with an empty Product are skipped. Hyperlink cells: use `cell.hyperlink.target` when set, else the text. Rows are joined across tabs by (product, grade, box_type).

- [ ] **Step 1: Failing tests:**
  - `test_parses_standard_and_eighth_box_lines`: the Gletsjer 60 cm row gives two lines. Standard has pack 300, bunch `x10` and USD price 0.232 (to 3 places).
  - `test_joins_usd_and_eur_tabs`: the same line carries both currencies.
  - `test_summary_row_parsed_but_unmatched`: "Aster (5 varieties)" is in the output with `item` None after `match_items`.
  - `test_name_normalisation_matches`: an Item named `Aster (Novi Belgii Grp) Dark Milka` matches the sheet's `Aster (Novi Belgii Grp) Dark Milka`. An Item `Agapanthus Gletsjer` matches `Agapanthus 'Gletsjer'` (quotes stripped).
  - `test_real_sheet_smoke`: skipped unless `/home/austin/Downloads/Marginpar FOB Combined pricelist Oct-Dec 2026 final.xlsx` exists. Parses without error into more than 100 lines.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** with `openpyxl.load_workbook(BytesIO, data_only=True)`. Normalise with lowercase, strip `'"()`, and collapse whitespace.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `feat(catalogues): import a seasonal offer sheet`

### Task 4: Guest endpoints, party matching and the interest record

**Files:**
- Create: `upande_crm/api/catalogue_public.py`
- Test: `upande_crm/tests/test_catalogue_public.py`

**Interfaces:**
- Consumes: Task 1 (`is_open`, `price_for`), `api.whatsapp._suffix`.
- Produces:
  - `resolve_token(token) -> (catalogue_doc, link_doc|None)`. Raises `DoesNotExistError` for an unknown token.
  - `catalogue_view(token) -> dict` (guest). Returns company name and logo, title, terms, currencies, tier qty, open flag, and groups `[{item, item_name, image, description, lines:[...]}]` in line order. With a personal link it also returns `prefill` (name, company, email, phone). It records the open: link `open_count += 1`, sets first/last opened, or catalogue `views += 1` for public. Writes use `frappe.db.set_value` / `frappe.db.sql` update with `update_modified=False`.
  - `catalogue_submit(token, contact: json, lines: json, currency, website="") -> {"ok": True}` (guest, POST, `@rate_limit(limit=10, seconds=3600)`). `website` is the honeypot: when non-empty it returns ok and saves nothing.
  - `find_party(email, phone) -> (party_type, party)|(None, None)`. A Customer via Contact (email or phone suffix) wins over a Lead. Email is compared lowercased and stripped.
  - Lead creation: `lead_name`, `company_name`, `email_id`, `mobile_no`, `country`, `utm_source="Catalogue"` (create the UTM Source if missing; spec: source "Catalogue"), a note naming the catalogue title, `lead_owner=catalogue.owner`, `flags.ignore_mandatory=True`, `ignore_permissions=True`.
  - Interest: snapshot each line (`line_ref`, item, item_name, grade, box_type, pack_qty, qty, frequency, price/tier via `price_for` in the chosen currency). Lines with qty ≤ 0 are dropped. Zero lines raises `ValidationError("Pick at least one line")`.
  - After insert: `frappe.sendmail` to the catalogue owner (subject `New interest from {name} — {catalogue}`), a Notification Log for the owner, and `add_comment("Info", …)` on the party.

- [ ] **Step 1: Failing tests** (run the guest calls under `frappe.set_user("Guest")`):
  - `test_view_counts_public_and_personal_opens`
  - `test_closed_catalogue_refuses_submit`: Closed, and Live with `valid_to` in the past, both raise.
  - `test_new_email_creates_lead_and_interest`: the Lead has `lead_owner == catalogue.owner`, and the interest party is that Lead.
  - `test_known_customer_email_case_insensitive`: a Contact with email `buyer@x.com` linked to a Customer. Submitting `"  Buyer@X.com "` creates an interest on the Customer and no new Lead (Lead count unchanged).
  - `test_phone_suffix_match`: `+254 712 345 678` matches a Lead with `0712345678`.
  - `test_personal_link_same_email_uses_party` and `test_forwarded_link_other_email_rematches`: a different email creates a new Lead and records `via_link`.
  - `test_resubmit_creates_second_interest_not_second_lead`
  - `test_missing_currency_price_snapshots_none`
  - `test_honeypot_saves_nothing`
  - `test_lead_with_custom_mandatory_field_still_inserts`: add a temporary reqd Custom Field on Lead in the test, then remove it in tearDown.
  - `test_owner_notified`: one Email Queue row to the owner (`frappe.flags.testing_email` / check `Email Queue`).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `feat(catalogues): buyers submit interest from a link`

### Task 5: Personal links and sending (email / WhatsApp / copy)

**Files:**
- Modify: `upande_crm/api/catalogues.py`: add sharing endpoints
- Modify: `upande_crm/api/whatsapp.py`: `crm_whatsapp_send_template(..., body_params=None)`. `body_params` is a JSON list, stored as `body_param` = `json.dumps({str(i+1): v})` on the WhatsApp Message.
- Test: `upande_crm/tests/test_catalogue_share.py`

**Interfaces:**
- Produces:
  - `crm_catalogue_share_options(name, party_type, party) -> {"email": str|None, "phone": str|None, "channels": {"email": bool, "whatsapp": bool, "whatsapp_mode": "text"|"template"|None, "copy": True}, "reason": {...}}`. Email needs module `mail` and an email address. WhatsApp needs module `wa`, `_available()` and a phone. The mode is `text` when `_window_open(last inbound)`, else `template` if `catalogue_whatsapp_template` is set, else WhatsApp is false with a reason.
  - `crm_catalogue_share(name, party_type, party, channel, subject=None, body=None) -> {"link": name, "url": str, "sent": bool}` (POST). Creates a CRM Catalogue Link (reusing an existing one for the same catalogue+party+channel), then:
    - email: calls `crm_send_email(recipients, subject, content, reference_doctype=party_type, reference_name=party)` with `{link}`, `{name}` and `{catalogue}` filled.
    - whatsapp: `crm_whatsapp_send` (text) or `crm_whatsapp_send_template(..., body_params=[url])`.
    - copy: no send.
  - `crm_catalogue_links(name) -> {"rows": [...]}`: links with party, sent_via, opens and last opened. Filtered with `readable_parties`.

- [ ] **Step 1: Failing tests** (WhatsApp sends are never actually inserted: patch `frappe_whatsapp`'s insert by mocking `upande_crm.api.whatsapp.crm_whatsapp_send` / `_send_template` with `unittest.mock.patch`):
  - `test_copy_creates_link_with_token_url`
  - `test_email_send_creates_communication_with_link`: a Communication exists with reference = party and the URL in its content.
  - `test_email_hidden_when_mail_module_off`
  - `test_whatsapp_template_used_outside_window`: the mock receives `body_params=[url]`.
  - `test_whatsapp_disabled_without_template_outside_window`: `channels.whatsapp is False` with a reason.
  - `test_send_template_body_params_stored`: the existing endpoint called with `body_params` builds `body_param == '{"1": "<url>"}'`. Patch `WhatsApp Message.insert` to capture the doc.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect PASS.** Also re-run `test_whatsapp`.
- [ ] **Step 5: Commit** `feat(catalogues): send personal catalogue links by email, WhatsApp or copy`

### Task 6: Interests list, detail and Make Opportunity

**Files:**
- Modify: `upande_crm/api/catalogues.py`
- Test: `upande_crm/tests/test_catalogue_interests.py`

**Interfaces:**
- Produces:
  - `crm_catalogue_interests(catalogue=None, status=None, party_type=None, party=None) -> {"rows": [...]}`. Each row has name, catalogue title, party, contact, status, creation, `lines` and `boxes` (sum of qty), `weekly` (bool any). Filtered by `readable_parties`, but the catalogue owner and CRM managers see all interests on their catalogues.
  - `crm_catalogue_interest_get(name)`: full doc with items. Same visibility rule.
  - `crm_catalogue_interest_status(name, status)` (POST)
  - `crm_catalogue_make_opportunity(name) -> {"opportunity": name}` (POST). Creates `Opportunity` with `opportunity_from=party_type`, `party_name=party`, `currency` = the interest's currency, and items: `item_code`, `qty = boxes × pack_qty` (stems/units in the Item's UOM; with no pack_qty, use qty = boxes), `rate` = the tier price when the box count is above `volume_tier_qty` and a tier exists, else price, and `description` = `"{grade} · {box_type} · {qty} boxes {frequency}"`. Sets the interest's opportunity and status Converted. Calling it twice returns the existing one.

- [ ] **Step 1: Failing tests:**
  - `test_restricted_user_sees_only_readable_parties`: a Sales User with a User Permission on one Customer sees that Customer's interest only.
  - `test_owner_sees_all_on_own_catalogue`
  - `test_make_opportunity_weekly_line`: 5 boxes weekly × pack 300, with tier qty 4 → qty 1500, rate = tier price, description contains `Weekly`.
  - `test_make_opportunity_below_tier_uses_price`
  - `test_make_opportunity_idempotent`
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `feat(catalogues): interests list and Make Opportunity`

### Task 7: The buyer page `/catalogue/<token>`

**Files:**
- Modify: `upande_crm/hooks.py`: `website_route_rules = [{"from_route": "/catalogue/<token>", "to_route": "catalogue"}]` (merge if one exists)
- Create: `upande_crm/www/catalogue.html`, `upande_crm/www/catalogue.py` (`no_cache = 1`. `get_context` sets the title and company only, with `context.token = frappe.form_dict.token`. A missing or unknown token renders "This offer isn't available").
- Create: `upande_crm/public/catalogue/catalogue.js`, `upande_crm/public/catalogue/catalogue.css`

**Interfaces:**
- Consumes: `catalogue_view`, `catalogue_submit` (Task 4).

Page behaviour: the layout C groups from `catalogue_view`. The header carries the company logo and name, the title, validity and a currency switch (when there's more than one). The terms are collapsible. Each Item card shows its image (or a neutral placeholder), name, colour pills (distinct colours of its lines), description (clamped to 3 lines) and a "More info" link (the first line's `info_url`). Then the rows: grade, box type, `pack_qty · bunch · weight kg`, the price per unit in the selected currency (or "—"), "above N boxes" tier, a boxes input and a One-off/Weekly select. A sticky bottom bar shows `N lines · M boxes` and **Send interest**, which opens the contact form (prefilled for personal links). A hidden `website` field is the honeypot. Submit leads to a thank-you view. A closed offer shows a notice and no inputs. Mobile first: cards stack, rows wrap, and inputs are at least 40px. No framework.

- [ ] **Step 1:** Build the page. Then, on webstore.localhost with a seeded catalogue (Task 9 seed), drive it with Playwright as Guest at 390px and 1280px widths. Screenshot both. Submit once and check the interest exists.
- [ ] **Step 2:** Verify the closed-offer notice (set status Closed, reload).
- [ ] **Step 3: Commit** `feat(catalogues): the buyer's catalogue page`

### Task 8: SPA section "Catalogues"

**Files:**
- Modify: `frontend/src/nav.js`: in the Pipeline group, add `{ type: 'group', section: 'cat', icon: 'menu_book', label: 'Catalogues', subs: [{ table: '', label: 'Catalogues' }, { table: 'interests', label: 'Interests' }] }`
- Modify: `frontend/src/App.jsx` (`const Catalogues = lazy(() => import('./sections/Catalogues/index.jsx'))`, plus `cat: Catalogues` in `SECTIONS`), `frontend/src/store.js` (`SECTION_META.cat`), `frontend/src/api.js` (wrappers for every endpoint in Tasks 2, 3, 5 and 6 under `const CT = 'upande_crm.api.catalogues.'`)
- Create: `frontend/src/sections/Catalogues/index.jsx` (list + interests tabs), `CatalogueEditor.jsx`, `ShareDialog.jsx`, `InterestDetail.jsx`
- Modify: `frontend/src/sections/CustomerPage/…`: add an "interests" tab (`CUSTPAGE_TABS` + `CUSTPAGE_TAB_MODULE["interests"] = "cat"` in `modules.py`) listing `crm_catalogue_interests(party_type="Customer", party=name)`
- Modify: `frontend/src/components/LeadDialog.jsx`: when editing an existing lead, show a small "Catalogue interests" list (same endpoint, `party_type="Lead"`)

Behaviour:
- **List:** a DataTable of catalogues (title, status badge, validity, currencies, lines, views, links opened/sent, interests, owner) with actions New, Open, Duplicate, Close/Go live, Copy public link.
- **Editor:** header fields, then the line grid grouped by Item. Columns: grade, box type, colour, pack, bunch, weight, one price/tier pair per currency, and info URL. Add a line with LinkSearch on Item. **Import offer sheet** uploads to `/api/method/upload_file` (private), calls `crm_catalogue_import`, shows the matched lines plus an "Unmatched" list where each row gets a LinkSearch (map to Item) or is skipped, then merges into the grid. Save calls `crm_catalogue_save`.
- **Share dialog:** pick a party (LinkSearch over Lead and Customer), then `crm_catalogue_share_options`, then three buttons (Email / WhatsApp / Copy link), each disabled with its reason. Email shows the editable subject and body prefilled from settings. A table of links already sent (`crm_catalogue_links`) shows opens.
- **Interests:** a table with a status filter. The detail drawer shows the contact, lines (grade, box type, boxes, frequency, price) and status select, plus **Make Opportunity**, which then links to the opportunity.
- Settings → Modules picks up `cat` automatically. Add `catalogue_whatsapp_template` (a select of approved templates via `waTemplatesApi`) and the email subject/body to the Settings section's Catalogues block.

- [ ] **Step 1:** Implement, then run `npm run build`. The build must not add a new manual chunk.
- [ ] **Step 2:** Use Playwright as a Sales User on webstore.localhost: create a catalogue, import the real sheet, map one unmatched row, go Live, copy the public link, share by email to a Lead, open the Interests tab after a guest submission, and Make Opportunity. Screenshot each.
- [ ] **Step 3: Commit** `feat(catalogues): catalogue builder, sharing and interests in the CRM`

### Task 9: Seed and end-to-end on webstore.localhost

**Files:**
- Create: `upande_crm/demo/catalogue_seed.py` with `seed(path=None)`. It creates (if missing) Items for about 8 Marginpar varieties from the real sheet (item_group "Products" or the first existing group, stock_uom Nos), attaches a generated placeholder image to two of them, and builds a Live USD+EUR catalogue owned by a Sales User from the import functions in Task 3.

- [ ] **Step 1:** Run `bench --site webstore.localhost execute upande_crm.demo.catalogue_seed.seed`.
- [ ] **Step 2:** Run the full app suite: `bench --site webstore.localhost run-tests --app upande_crm`. All pass. Note any failures that were already failing before this work, with evidence (`git stash` run).
- [ ] **Step 3:** Run the end-to-end flows in Tasks 7 and 8 together, as the real Sales User and as Guest.
- [ ] **Step 4: Commit** `chore(catalogues): demo seed for the catalogue flow`
