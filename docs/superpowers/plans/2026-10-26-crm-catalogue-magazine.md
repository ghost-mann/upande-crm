# CRM Catalogue Magazine Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the buyer's catalogue page into a template-driven "colour
almanac" magazine. Every look and wording setting lives in named templates
in CRM Settings, and the starter templates cover flowers, avocado and
coffee.

**Architecture:**
- **Data:** a new `CRM Catalogue Template` doctype, with four child tables,
  holds look, wording, grouping, spec columns, badges, frequencies and
  section switches.
- **Server-side rendering model:** a pure module, `api/catalogue_display.py`,
  turns a catalogue + template into one display payload. That covers
  groups with repeated cards, resolved text, theme and mixes, plus the
  estimate rule.
- **Who uses the payload:** the guest page renders it with vanilla JS and
  bundled fonts; Settings previews it in an iframe via postMessage.

**Tech Stack:** Frappe/ERPNext v16, Python, vanilla JS/CSS (buyer page), React 18 + Vite (CRM SPA), WOFF2 fonts (SIL OFL) from Fontsource.

**Spec:** `docs/superpowers/specs/2026-10-26-crm-catalogue-magazine-design.md` (builds on `2026-10-25-crm-catalogues-design.md`).

**Test site / commands:** from `/home/austin/frappe-v16-bench`, run
`bench --site webstore.localhost run-tests --app upande_crm --module upande_crm.tests.<module>`.
Migrate with `bench --site webstore.localhost migrate`. Build the SPA with
`cd apps/upande_crm/frontend && npm run build`, and commit the rebuilt
`upande_crm/public/frontend` and `www/customer-relationship-management.html`.

## Global Constraints

- **Escaping:** Jinja on this site doesn't autoescape. Every template
  string reaches the page as text: escaped in JS, never as innerHTML. The
  catalogue's `terms` is the only HTML, as today.
- **Colours:** validated server-side as `#RRGGBB` before they reach the page,
  and applied as CSS custom properties.
- **No third-party requests from the buyer page:** fonts are bundled under
  `public/catalogue/fonts/`, and the page loads only the selected pair.
- **Unchanged:** submission, party matching, interests and links. The only
  submit change: the frequency must be one of the template's labels.
- **Writes:** a GET request's writes aren't committed, so keep guest
  endpoints that write as POST. Tests must not create Custom Fields (DDL
  commits). A null Float reads as 0, so store presence explicitly.
- **Seed data:** starter templates come from `after_install` and
  `after_migrate`, not patches.txt (install-app skips patches, and
  `before_migrate` runs before model sync).
- **Permissions:** templates are written by System Manager, Sales Manager
  or CRM Manager (`api/settings.WRITE_ROLES`) and read by CRM roles. Guests
  get the resolved payload only.
- **Buyer page:** framework-free; JS + CSS under ~60 KB gzipped excluding
  fonts; usable at 360px; visible focus; respects
  `prefers-reduced-motion`.
- **Vite:** keep the existing chunking. New SPA screens are `lazy()`.
- **Commits:** authored by ghost-mann, with no Claude co-author line.

## Review Focus

1. **A template edited badly while a catalogue is live:**
   - a missing label falls back to the starter's default text;
   - a low-contrast colour pair still renders (the editor warns, it doesn't
     block).

   Test in Task 2: `test_payload_text_falls_back_to_defaults`.
2. **A line colour word no group matches ("All", blank, "Burgundy Red"):**
   "All" and blank land in the fallback group; "Burgundy Red" matches the
   "red" keyword as a whole word.
   Test in Task 2: `test_colour_group_resolution`.
3. **Deleting a template that catalogues still use:** refused with a
   message naming how many catalogues use it.
   Test in Task 4: `test_delete_template_in_use_refused`.
4. **A mix that points at a line that was removed:** the mix still renders
   with the remaining lines, and is dropped when none remain.
   Test in Task 2: `test_mix_with_removed_line`.
5. **Submitting a frequency the template doesn't list** (an old page, or a
   tampered request): refused with ValidationError, and nothing is saved.
   Test in Task 3: `test_submit_rejects_unknown_frequency`.

---

### Task 1: Template doctypes, catalogue fields, starter seed

**Files:**
- Create doctypes (module Upande CRM) under `upande_crm/upande_crm/doctype/`:
  - `crm_catalogue_template`:
    - naming: `field:template_name`;
    - fields: all the spec's "CRM Catalogue Template" fields;
    - Selects:
      - `preset`: Almanac / Field guide / Market sheet;
      - `group_by`: Colour / Item Group / Grade;
      - `cover_mode`: Image / Collage;
      - `font_pair`: options from `FONT_PAIRS` keys, below.
  - child `crm_catalogue_template_colour_group`: `label`, `swatch`,
    `swatch_ink`, `keywords`.
  - child `crm_catalogue_template_spec`:
    - fields: `key`, `label`, `display` (Column / Badge / Subtitle),
      `import_headers`;
    - table field on the template: `spec_columns`.
  - child `crm_catalogue_template_badge`: `label`, `background`, `ink`.
  - child `crm_catalogue_template_frequency`:
    - fields: `label`, `period_text`, `recurring` (Check);
    - table field on the template: `frequencies`.
  - child `crm_catalogue_product`: `item` (Link Item, reqd), `badges`
    (Small Text), `note` (Small Text), `specs` (JSON).
  - child `crm_catalogue_mix`: `title` (reqd), `items` (JSON), `summary`
    (Small Text).
- Modify existing doctypes:
  - `crm_catalogue.json`: add `template` (Link CRM Catalogue Template),
    `cover_image` (Attach Image), `products` (Table → CRM Catalogue
    Product), `mixes` (Table → CRM Catalogue Mix).
  - `crm_catalogue_line.json`: add `specs` (JSON) and `colour_group` (Data).
  - `crm_catalogue_interest_item.json`: `frequency` changes from Select to
    Data.
- Create `upande_crm/catalogue_templates.py`:
  - `FONT_PAIRS`: dict of key → `{"head": family, "text": family, "note":
    family, "files": [...]}`. At least 6 pairs, including `almanac`
    (Archivo + Archivo Narrow + Newsreader), `orchard` (Fraunces +
    Instrument Sans + Spectral) and `roastery` (Spectral + Instrument Sans +
    Spectral).
  - `STARTERS`: the three starter templates, with the exact values in the
    spec table.
  - `ensure_starters()`: creates any missing starter.
  - `assign_default_template()`: sets "Flowers almanac" on catalogues with
    no template.
- Modify `upande_crm/hooks.py`: `after_migrate = ["upande_crm.catalogue_templates.after_migrate"]`
  (merge if one already exists). `after_migrate()` calls both functions.
  Also call them at the end of `setup.setup` when the doctype exists (that
  covers after_install).
- Modify `setup.py` `CRM_ROLE_PERMS`: CRM User reads CRM Catalogue
  Template; CRM Manager writes it.
- Controller `crm_catalogue_template.py` (`validate`):
  - colours must match `^#[0-9A-Fa-f]{6}$`;
  - spec `key` must be a unique slug (`^[a-z][a-z0-9_]{0,30}$`);
  - at least one frequency, with unique labels;
  - colour-group labels unique;
  - `on_trash` refuses while any CRM Catalogue uses it.
- Controller `crm_catalogue.py` `validate`:
  - **products:** sync the `products` rows to the distinct line items
    (add missing, drop unused, keep existing values);
  - **template:** default it to "Flowers almanac" when blank and the
    starter exists;
  - **badges:** drop labels not in the template's badge list;
  - **specs:** drop line/product spec keys not in the template, or of the
    wrong display kind (Column → line, Badge/Subtitle → product).
- Test: `upande_crm/tests/test_catalogue_templates.py`

**Interfaces:**
- Produces:
  - `catalogue_templates.FONT_PAIRS: dict[str, dict]`
  - `catalogue_templates.STARTERS: list[dict]`
  - `catalogue_templates.ensure_starters() -> list[str]` (names created)
  - `catalogue_templates.assign_default_template() -> int`
  - `CRMCatalogueTemplate.frequency_labels() -> list[str]`
  - doctype names as listed above.

- [ ] **Step 1: Write failing tests** in `test_catalogue_templates.py`:
  - `test_starters_created_once`: run `ensure_starters()` twice. The names
    `{"Flowers almanac", "Avocado export", "Coffee lots"}` exist, and the
    second call returns `[]`.
  - `test_starter_edits_survive`: edit Flowers almanac's `headline`, call
    `ensure_starters()`, and the headline is unchanged.
  - `test_bad_hex_refused`: `brand="green"` raises ValidationError.
  - `test_spec_keys_unique_slugs`: two specs with key `cup` raise; key
    `Cup Score` raises.
  - `test_needs_a_frequency`: an empty frequencies table raises.
  - `test_delete_template_in_use_refused` (Review Focus 3): a catalogue uses
    the template, so deleting it raises LinkExistsError or ValidationError,
    with the count in the message.
  - `test_catalogue_products_follow_lines`: a catalogue with lines for items
    A, A, B has two product rows. Remove B's line, save, and one product row
    is left; A's badges/note survive the save.
  - `test_unknown_badges_and_specs_dropped`: product badges `"Bestseller\nBogus"`
    on Flowers almanac are saved as `"Bestseller"`. A line spec key that the
    template doesn't define is dropped.
  - `test_existing_catalogues_get_flowers_almanac`: a catalogue whose template
    was cleared with `db.set_value` gets "Flowers almanac" after
    `assign_default_template()`.
- [ ] **Step 2: Run, expect FAIL** (module/doctype missing).
- [ ] **Step 3: Implement** the JSONs, controllers and `catalogue_templates.py`,
  then migrate. Existing catalogue tests that build catalogues through
  `make_catalogue` must still pass. The default template is set in
  `validate`, so the fixtures need no change.
- [ ] **Step 4: Run, expect PASS.** Also run `test_catalogue_model`,
  `test_catalogues`, `test_catalogue_public`, `test_settings` and
  `test_modules`.
- [ ] **Step 5: Commit** `feat(catalogues): magazine templates, product and mix records, starter templates`

### Task 2: The display model (`api/catalogue_display.py`)

**Files:**
- Create: `upande_crm/api/catalogue_display.py`
- Test: `upande_crm/tests/test_catalogue_display.py`

**Interfaces:**
- Consumes: Task 1 doctypes, `CRMCatalogue.price_for`, `currency_list`, `is_open`.
- Produces:
  - `resolve_colour_group(line, template) -> str`: the line's
    `colour_group`, else the first group whose keywords contain the colour
    word, else `template.fallback_group_label or "Mixed"`. Keywords match
    whole words, case-insensitively, against the colour text; "Burgundy Red"
    matches keyword "red".
  - `group_key(line, item_group, template) -> str`, per `group_by`.
  - `template_text(template) -> dict[str, str]`: every label resolved, with
    `{unit}`, `{pack}`, `{packs}`, `{Packs}` and `{n}` substituted
    (`{n}` = the catalogue's tier qty, filled by `build_display`). A blank
    field falls back to the starter "Flowers almanac" value for that field.
  - `build_display(doc, template, preview=False) -> dict` with keys:
    - `theme`: `{brand, brand_ink, paper, ink, accent, accent_ink,
      font_pair, fonts: {head, text, note, css}, cover_mode, cover_image,
      logo}`;
    - `text`;
    - `sections`: the switches as bools;
    - `frequencies`: `[{label, period_text, recurring}]`;
    - `specs`: `[{key, label, display}]`;
    - `groups`: `[{key, label, swatch, swatch_ink, products: [{item,
      item_name, image, note, badges: [{label, background, ink}],
      subtitle: [{label, value}], product_badge_specs: [{label, value}],
      lines: [...]}]}]`;
    - `mixes`: `[{title, summary, colours: [hex], items: [{line, boxes}]}]`;
    - the top-level fields `catalogue_view` returns today (title, company,
      currencies, tier_qty, open, valid_to, valid_from, terms).
  - Each line dict is today's line dict, plus `specs` (Column specs only)
    and `group`.
  - `estimate(lines, picks, currency, tier_qty, frequencies) -> list[dict]`:
    - one entry per frequency in use: `{frequency, period_text, amount}`;
    - `picks` is `[{line, qty, frequency}]`;
    - per pick: `qty × pack_qty × (tier if tier_qty and qty > tier_qty and tier is not None else price)`;
    - picks with no price or no pack qty are skipped;
    - entries are in the template's frequency order; zero amounts are
      dropped.

- [ ] **Step 1: Write failing tests:**
  - `test_colour_group_resolution` (Review Focus 2): "White" → "Whites";
    "Burgundy Red" → "Oranges & reds"; "All" → "Mixed"; "" → "Mixed"; a
    line with `colour_group="Pinks"` → "Pinks".
  - `test_product_repeats_across_groups`: one item with lines "White" and
    "Pink", in Flowers almanac. Groups "Whites" and "Pinks" each hold a
    product for that item, each with only its own line.
  - `test_group_by_grade_and_item_group`: Coffee lots splits by `grade`;
    Avocado export groups by the Item's `item_group`.
  - `test_group_order_follows_template`: the Whites group comes before
    Purples whatever the line order.
  - `test_product_fields_once_per_product`: badges, note and the
    Subtitle/Badge specs from the product row appear on every repeated copy
    of the card. A blank note falls back to the Item description.
  - `test_payload_text_falls_back_to_defaults` (Review Focus 1): blank
    `cta_label` and `pack_label_plural` on a copied template still give
    "Send my interest" and "boxes". `tier_label` with tier 4 gives
    "Above 4 boxes".
  - `test_mix_with_removed_line` (Review Focus 4): a mix with one valid and
    one stale line keeps one item; a mix with only stale lines is dropped.
  - `test_estimate_split_by_frequency`: picks 2 boxes Weekly (pack 300,
    price 0.232) and 1 box One-off (pack 320, price 0.186) give
    `[{"frequency": "One-off", "period_text": "once", "amount": 59.52},
    {"frequency": "Weekly", "period_text": "a week", "amount": 139.2}]`
    (amounts rounded to 2 places).
  - `test_estimate_uses_tier_above_threshold_and_skips_unpriced`: 5 boxes
    with tier qty 4 uses tier 0.2204; a line with no price is skipped.
  - `test_hidden_sections_not_sent`: with `show_codes=0`, line `vbn` is
    `None` in the payload; with `show_weight=0`, `weight` is `None`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Pure functions, apart from reading Items, the
  Company and File URLs.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `feat(catalogues): the magazine display model`

### Task 3: Guest API on the display model, plus preview

**Files:**
- Modify: `upande_crm/api/catalogue_public.py`
- Modify: `upande_crm/api/catalogues.py` (add `crm_catalogue_preview`)
- Test: `upande_crm/tests/test_catalogue_public.py` (extend), `upande_crm/tests/test_catalogue_display.py`

**Interfaces:**
- Consumes: `build_display`, `CRMCatalogueTemplate.frequency_labels()`.
- Produces:
  - `catalogue_view(token)`: returns `build_display(doc, template)` plus
    `personal` and `prefill`, as today. Draft rule as today (no groups);
    open recording as today.
  - `catalogue_submit(...)`: unchanged signature. Each pick's `frequency`
    must be in the template's `frequency_labels()`; missing means the first
    label; unknown raises ValidationError("Unknown frequency").
  - `crm_catalogue_preview(name, template=None) -> dict` (`cat` module,
    `_guard`, read permission on the catalogue):
    - `template` is optional JSON of an unsaved template doc, used instead
      of the saved one; it is validated (hex etc.) without saving.
    - Returns `build_display(..., preview=True)` for any status and dates.
    - Records nothing.
  - `crm_catalogue_make_opportunity`: a line is recurring when its
    frequency row has `recurring`. The description still names the
    frequency label.

- [ ] **Step 1: Failing tests:**
  - `test_view_returns_theme_text_groups`: the keys `theme`, `text`,
    `sections` and `groups` are present for a live catalogue.
  - `test_submit_accepts_template_frequency`: on Avocado export,
    "Per shipment" is accepted and stored on the interest item.
  - `test_submit_rejects_unknown_frequency` (Review Focus 5): "Weekly" on
    Avocado export raises, and no interest is saved.
  - `test_preview_ignores_status_and_records_nothing`: a Draft catalogue
    previews with groups, and `views` stays 0.
  - `test_preview_uses_unsaved_template`: passing a template JSON with
    `headline="Draft headline"` returns that headline; the saved template
    is unchanged.
  - `test_preview_requires_crm_user`: as Guest, it raises PermissionError.
  - `test_make_opportunity_recurring_from_template`: a "Monthly" pick
    (recurring) on Avocado export puts "Monthly" in the description.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect PASS.** Run all `test_catalogue*` modules.
- [ ] **Step 5: Commit** `feat(catalogues): serve the magazine payload, template frequencies, preview`

### Task 4: Template and catalogue editing API, and spec-aware import

**Files:**
- Modify: `upande_crm/api/catalogues.py`, `upande_crm/api/catalogue_import.py`
- Test: `upande_crm/tests/test_catalogue_templates.py` (extend), `upande_crm/tests/test_catalogue_import.py` (extend)

**Interfaces:**
- Produces:
  - **Template endpoints** (all `@requires_module("cat")`):
    - `crm_catalogue_templates() -> {"rows": [...], "font_pairs": FONT_PAIRS-without-files, "can_edit": bool}`.
      A row has name, preset, group_by, brand, catalogues_using.
    - `crm_catalogue_template_get(name) -> {"template": dict}`, the doc and
      its child tables.
    - `crm_catalogue_template_save(template: json) -> {"template": dict,
      "warnings": [str]}`. Writers only. Warnings are WCAG contrast below
      4.5 for ink/paper, brand_ink/brand, accent_ink/accent and each badge.
    - `crm_catalogue_template_copy(name, new_name) -> {"name"}`.
    - `crm_catalogue_template_delete(name)`, refused while in use
      (Task 1's `on_trash`).
  - `contrast_ratio(hex_a, hex_b) -> float`: the WCAG relative-luminance
    formula.
  - **`crm_catalogue_save`** also accepts:
    - `template`, `cover_image`;
    - `products` (`[{item, badges: [str], note, specs: {}}]`, merged by
      item);
    - `mixes` (`[{title, items: [{line, boxes}], summary}]`);
    - line `specs` and `colour_group`.
  - **`crm_catalogue_get`** also returns `products`, `mixes`, and each
    line's resolved `group`, so the editor can show the derived group as a
    placeholder.
  - **`crm_catalogue_import(file_url, currencies, catalogue=None)`:** when a
    catalogue is given, its template's `import_headers` map sheet columns:
    Column specs onto line `specs`, Badge/Subtitle specs onto a returned
    `products` list. Without one, the behaviour is unchanged.
  - **`parse_offer_sheet(content, currencies, spec_headers=None)`:**
    `spec_headers` is `{key: [header, ...]}`, matched against the
    group-header row, case-insensitively.

- [ ] **Step 1: Failing tests:**
  - `test_template_save_warns_low_contrast`: ink #777777 on paper #888888
    returns a warning naming "text on paper".
  - `test_template_save_needs_writer_role`: a plain Sales User raises
    PermissionError.
  - `test_copy_template`: the copy has the same spec columns, and
    `is_standard` is 0.
  - `test_catalogue_save_products_and_mixes`: products and mixes round-trip
    through `crm_catalogue_get`.
  - `test_contrast_ratio_known_values`: black on white gives 21.0;
    #777777 on white gives about 4.48.
  - `test_import_fills_spec_columns`: a workbook with an extra header
    "Vase life" and a Flowers-almanac copy that has spec `vase_life`
    (Column, import_headers "Vase life") puts the value in the line's
    `specs`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect PASS.** Also run `test_modules`, after adding the
  new endpoints to `test_modules_gated.GATED["cat"]`.
- [ ] **Step 5: Commit** `feat(catalogues): template editing, product and mix editing, spec-aware import`

### Task 5: Bundled fonts and the almanac buyer page

**Files:**
- Create: `upande_crm/public/catalogue/fonts/<pair>/*.woff2` (latin subset,
  the weights used only). Source them from Fontsource on jsDelivr
  (`https://cdn.jsdelivr.net/fontsource/fonts/<family>@latest/latin-<weight>-<style>.woff2`),
  downloaded once and committed. Add `fonts/LICENSES.md` naming each family
  and OFL-1.1.
- Rewrite: `upande_crm/public/catalogue/catalogue.js`, `catalogue.css`
- Modify: `upande_crm/www/catalogue.html`: add `data-preview` when
  `?preview=1` and the session user is a CRM user (from `catalogue.py`).

**Interfaces:**
- Consumes:
  - the `catalogue_view` payload (Task 3);
  - `crm_catalogue_preview` (Task 3), used in preview mode via a
    `{type: "catalogue-preview", name, template}` postMessage from the same
    origin.
- Produces the page described in the spec's "buyer page" section:
  - cover, letter, sticky group tabs, mixes, group sections with repeated
    product cards, the spec table with template labels, the bar with the
    split estimate, form, thank-you page, closed notice and currency switch.
  - **Fonts:** an `@font-face` CSS file per pair,
    `fonts/<pair>/fonts.css`, linked by the JS from `theme.fonts.css`.
  - **Theme:** colours via `--brand`, `--brand-ink`, `--paper`, `--ink`,
    `--accent` and `--accent-ink` on the root element.
  - The estimate logic is a JS port of `estimate()`. Keep it a single pure
    function `estimate(lines, picks, currency, tierQty, frequencies)` with
    the same rounding.
  - "Add this mix" adds each mix item's boxes to the current pick, using
    the default frequency when none is set.
  - Preview mode: no form submit (the button is disabled with "Preview"),
    and nothing is posted.

- [ ] **Step 1:** Fetch the fonts and write `fonts.css` per pair. Check that
  each file is a WOFF2 (`file` says "Web Open Font Format (Version 2)") and
  that the total size is under 1.5 MB.
- [ ] **Step 2:** Implement the page. Seed a Flowers almanac catalogue
  (Task 7's seed covers the Marginpar one).
- [ ] **Step 3:** Drive it with Playwright as Guest at 390px and 1280px:
  - screenshot the cover, letter, tabs, a mix and a group;
  - tap a tab and check it scrolls to its group;
  - "Add this mix" fills the boxes, and the bar shows the split estimate;
  - submit, and the interest exists;
  - no request leaves 127.0.0.1;
  - no page errors.
- [ ] **Step 4:** Check the closed notice and preview mode (postMessage
  changes the headline live, and submit is disabled).
- [ ] **Step 5: Commit** `feat(catalogues): the almanac buyer page with bundled fonts`

### Task 6: CRM screens: template editor with live preview; catalogue editor additions

**Files:**
- Create: `frontend/src/sections/Settings/CatalogueTemplates.jsx` (list +
  editor + preview iframe), and register it as Settings tab `templates`
  ("Catalogue templates"). The existing Settings → Catalogues tab
  (email/WhatsApp) stays.
- Modify: `frontend/src/lib/catalogues.js` (wrappers for the Task 3/4
  endpoints), `frontend/src/nav.js` (the Settings sub),
  `frontend/src/sections/Settings/index.jsx`.
- Modify: `frontend/src/sections/Catalogues/CatalogueEditor.jsx`:
  - a template picker, and a cover image override (upload);
  - a **Products** panel per item: badges multi-select from the template
    list, a note (placeholder: the Item description), and inputs for the
    Badge/Subtitle specs;
  - line grid: inputs for the Column specs and a colour group select
    (placeholder: the derived group);
  - a **Mixes** panel: add or remove a mix, title, a line picker with boxes;
  - a "Preview" button that opens the buyer page in preview mode in a new
    tab.

Editor behaviour:
- The preset picker fills colours and fonts from the preset values (Field
  guide and Market sheet values are the builder's call).
- Colour inputs are `<input type=color>` plus a hex text box.
- Font pair is a select showing each pair's names in their own faces.
- Colour groups, specs, badges and frequencies are small editable tables.
- Section switches use the Settings `Toggle`.
- Contrast warnings from save are shown inline.
- **Preview:** a catalogue picker and an iframe of
  `/catalogue/<public_token>?preview=1`. The editor posts the draft on each
  change (debounced 300 ms).

- [ ] **Step 1:** Implement, then `npm run build` (no new manual chunk).
- [ ] **Step 2:** Use Playwright as a Sales Manager (Administrator), on
  Settings → Catalogue templates:
  - open Flowers almanac and change the brand colour and headline; the
    iframe preview updates without saving;
  - save, and the warning shows for a low-contrast ink;
  - copy to "Flowers almanac (copy)";
  - delete the copy;
  - try deleting Flowers almanac, and it is refused because catalogues use
    it.
- [ ] **Step 3:** Use Playwright as `crm.sales@webstore.test` in the
  catalogue editor:
  - pick a template;
  - set a product badge and note;
  - set a line's colour group;
  - add a mix of two lines;
  - save, reload, and all of it persists;
  - Preview opens the magazine.
- [ ] **Step 4: Commit** `feat(catalogues): template editor with live preview; products, specs and mixes in the catalogue editor`

### Task 7: Demo data for the three templates, end to end, suite

**Files:**
- Modify: `upande_crm/demo_catalogue.py`:
  - `seed()`: the Marginpar catalogue gets Flowers almanac, product badges
    on 3 items, notes on 3, and two mixes.
  - New `seed_avocado()`: Items "Hass" and "Fuerte" under item groups
    "Hass" and "Fuerte" (created if missing), Count lines 12–24, carton
    prices, Dry matter and Certification specs.
  - New `seed_coffee()`: two lots, grades AA/AB, Screen lines, cup score
    and process specs.
  - All three are Live and owned by `crm.sales@webstore.test`.

- [ ] **Step 1:** Run the three seeds on webstore.localhost.
- [ ] **Step 2:** Use Playwright as Guest on all three catalogues at 390px and
  1280px: screenshots, one submission each, no errors, no third-party
  requests. Check that the avocado page says "cartons" and "Per shipment"
  and that the coffee page shows the cup-score badge.
- [ ] **Step 3:** Run the full app suite. Compare the failing set with
  `master`'s, as in the previous plan: nothing may fail only on this
  branch.
- [ ] **Step 4: Commit** `chore(catalogues): demo catalogues for flowers, avocado and coffee`
