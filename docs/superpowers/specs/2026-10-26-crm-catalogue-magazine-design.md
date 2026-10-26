# CRM Catalogue Magazine Templates — Design

**Date:** 2026-10-26
**Status:** Agreed with the user in conversation (choices made with mockups in
the visual companion). Choices the user did not make are marked **Builder's call**.
**Builds on:** `2026-10-25-crm-catalogues-design.md` (catalogues, links, interests,
import), already merged to master. Submission, matching, interests and
Make Opportunity do not change.
**Test site:** `webstore.localhost` (the :8002 default site).

## Why

The buyer page today is a plain list. The user wants it to read like a
**flower magazine**, keeping every detail, and wants the whole look and
wording **configurable in CRM Settings**. It must work for any of Upande's
farms — flowers, avocado, coffee (and later sugarcane and others) — not
only flowers.

The chosen direction is the **colour almanac** (mockup "C"): a trade colour
book with a magazine cover, read as one long scroll. Avocado and coffee use
the same engine with a different grouping, vocabulary and look.

## Goals

- Named **magazine templates** in CRM Settings. Each catalogue picks one.
  One site can serve several farms or crops.
- A template sets:
  - the **look**: a preset, colours, font pair and cover;
  - the **grouping**: colour, Item Group or grade;
  - the **wording**: units, labels, cover text, buttons;
  - the crop's **spec columns** and their display;
  - a **badge list**;
  - **section switches**.
- The buyer page renders from the template, and keeps every detail the page
  shows today.
- A **live preview** of the template in Settings, using a real catalogue.
- Three starter templates ship with the app: **Flowers almanac**, **Avocado
  export** and **Coffee lots**. Existing catalogues move to Flowers almanac,
  and the plain page is retired.

## Non-goals

- No custom CSS box, no page-flip or spread reading, and no per-company
  settings (templates cover multiple farms).
- No change to submissions, party matching, interests, links or Opportunity
  creation.
- No fonts loaded from Google or any third party on the buyer page.

## Anti-goals

- A template change that silently breaks a live catalogue (an unreadable
  colour pair, a missing label). The editor validates, and the page falls
  back to the template defaults.
- Template text or colours that can inject markup or script into the
  guest page. All template values are data; nothing is rendered as HTML
  except the terms, which already are.
- Losing any detail the current page shows: grade, box type, pack, bunch,
  weight, both prices, tier threshold, boxes, frequency, "More info" link,
  currency switch, closed notice, personal-link prefill, thank-you page.

## The buyer page (the almanac, top to bottom)

One long scroll, mobile first. Each part can be switched off per template,
except the products and the bar.

1. **Cover.** The template's brand colour fills it. It shows:
   - the logo: the template's, else the Company logo, else the company name
     as a wordmark;
   - the issue title (e.g. "The colour almanac · Autumn issue 2026");
   - the headline (e.g. "Colour, by the box.") and the dek (one sentence);
   - the validity line, generated from the catalogue's dates and currencies;
   - the cover image. **User's decision:** the template chooses the mode,
     either an uploaded image or an automatic collage of the first item
     photos. A catalogue can override with its own image.
2. **"From the farm" letter.** The catalogue's `terms`, typeset as a short
   letter. The heading and sign-off come from the template.
3. **Group tabs.** Sticky at the top while scrolling, one per group, with
   counts. Colour grouping shows swatches; the other groupings use brand tints.
4. **Mixes.** Per-catalogue combinations ("Cool whites", "Purple & blush"),
   each with a stripe of its colours, a one-line summary, and "Add this mix".
   Adding fills those lines' boxes, adding to anything already entered.
5. **Group sections.** A big group heading, then the products:
   - **Grouping:** by colour group, Item Group, or line grade, as the
     template says. Order: the template's group order for colour, then
     first appearance; products and lines in catalogue line order.
   - **A product whose lines fall in different groups (user's decision):**
     its card repeats in each group it has lines in, and each copy shows
     only that group's lines. Tab and section counts count a product once
     per group it appears in.
   - **Product card:** photo (Item image, else a neutral placeholder), swatch
     strip (colour grouping only; shows the code when codes are on), name,
     badges, note. **Badges, note, and Badge/Subtitle specs are set once
     per product (user's decision)**; only Column specs are per line.
   - **Spec table:** grade, box type, pack (pack qty · bunch · weight),
     price per unit, tier price above N, boxes input + frequency select.
     Spec columns the template marks "column" are added to the table.
   - Spec columns marked "badge" render as badges; those marked "subtitle"
     render under the name.
   - A "More info" link (http/https only, as today).
6. **Bar.** Sticky: the line and box count, and **the estimate if the
   template switches it on**.
   - **Per line:** boxes × pack qty × price, using the tier price when the
     line's boxes exceed the tier threshold. Lines without a price or pack
     qty are left out.
   - **Split by frequency (user's decision):** one amount per frequency in
     use, each with that frequency's period wording, e.g. "$420 once +
     about $139 a week". Shown in the selected currency.
   - The button text comes from the template.
7. Contact form, thank-you page, closed notice and currency switch: as
   today, with wording from the template.

## Data model

### CRM Catalogue Template (new, regular doctype; managed from CRM Settings)

| Group | Fields |
|---|---|
| Identity | `template_name` (unique), `preset` (Almanac / Field guide / Market sheet), `is_standard` (shipped starters; can be copied, edits allowed) |
| Colours | `brand`, `brand_ink`, `paper`, `ink`, `accent`, `accent_ink`. Hex `#RRGGBB`, validated |
| Type | `font_pair`: Select from the bundled list (below) |
| Cover | `cover_mode` (Image / Collage), `cover_image` (Attach Image), `logo` (Attach Image, optional), `issue_title`, `headline`, `dek` |
| Letter | `letter_heading` (default "From the farm"), `letter_signoff` |
| Grouping | `group_by` (Colour / Item Group / Grade), `colour_groups` (table, below), `fallback_group_label` (default "Mixed") |
| Wording | `unit_label` (stem / kg / fruit / tonne), `pack_label` and `pack_label_plural` (box / boxes, carton / cartons, bag / bags), `grade_label` (Length / Count / Screen), `bunch_label` (Bunch / Fruits per carton; blank hides it), `weight_label`, `price_label` (default "Per {unit}"), `tier_label` (default "Above {n} {packs}"), `qty_label` (default "{Packs}"), `frequencies` (table, below), `cta_label` (default "Send my interest"), `thank_you_text`, `closed_text` |
| Specs | `spec_columns` (table, below) |
| Badges | `badges` (table, below) |
| Sections | Check each: `show_cover`, `show_letter`, `show_tabs`, `show_mixes`, `show_badges`, `show_notes`, `show_estimate`, `show_codes`, `show_weight`, `show_more_info` |

Child tables:

- **CRM Catalogue Template Colour Group:** `label` (e.g. "Whites"),
  `swatch` (hex), `swatch_ink` (hex), `keywords` (comma list, e.g.
  "white, cream, ivory"). Row order is tab order.
- **CRM Catalogue Template Spec:**
  - `key` (slug, unique per template), `label` (e.g. "Cup score");
  - `display` (Column / Badge / Subtitle);
  - `import_headers` (comma list of sheet header names to read it from).
- **CRM Catalogue Template Badge:** `label`, `background`, `ink`.
- **CRM Catalogue Template Frequency:**
  - `label` (e.g. "Weekly", "Per shipment");
  - `period_text` (estimate wording, e.g. "a week", "per shipment"; blank =
    "once");
  - `recurring` (Check; drives the Make Opportunity description).

  The first row is the default. There must be at least one row.

### Changes to existing doctypes

- **CRM Catalogue:**
  - `template` (Link, reqd; default from the starter "Flowers almanac");
  - `cover_image` (override);
  - `mixes` (Table → CRM Catalogue Mix).
- **CRM Catalogue Line:**
  - `specs` (JSON `{key: value}`, for the template's Column specs only);
  - `colour_group` (Data; blank = derived from `color` by keyword).
- **CRM Catalogue Product (new child of CRM Catalogue, one row per Item
  used by its lines):**
  - `item`;
  - `badges` (Small Text, newline list of template badge labels);
  - `note` (Small Text; blank = the Item description);
  - `specs` (JSON, for the template's Badge and Subtitle specs).

  The editor creates and removes these rows as lines are added and removed.
- **CRM Catalogue Mix (new child):**
  - `title`;
  - `items` (JSON `[{"line": <line name>, "boxes": n}]`);
  - `summary` (Small Text; blank = generated from the variety names).

Line names are stable across saves (already true since the review fix), so
mixes can point at them.

### Colour group resolution

1. A line's `colour_group` if set.
2. Otherwise, the first template colour group whose keywords contain the
   line's `color` word (case-insensitive, whole word).
3. Otherwise, the fallback group (`"Mixed"`). That is what "All" or a blank
   colour lands in.

For grouping by Item Group, the Item's `item_group` is used. For grouping by
grade, the line's `grade` is used.

## Fonts (user's decision: bundled, curated)

The fonts ship inside upande_crm as WOFF2 under `public/catalogue/fonts/`. All
are SIL OFL fonts. There are at least 6 pairs (headline + text + note). The
starter templates use:

- **Flowers almanac:** Archivo (condensed, heavy) + Archivo Narrow + Newsreader italic.
- **Avocado export:** Fraunces + Instrument Sans + Spectral italic.
- **Coffee lots:** Spectral + Instrument Sans + Spectral italic.

The rest of the list is the builder's call (distinct characters: a grotesk, a
didone, an old-style). Only Latin subsets, so the payload stays small. The page
loads only the selected pair. The buyer page makes no third-party requests.

## Starter templates (shipped, created by setup if missing)

| | Flowers almanac | Avocado export | Coffee lots |
|---|---|---|---|
| Group by | Colour (Whites, Pinks, Purples, Blues, Yellows, Greens, Oranges & reds, Mixed) | Item Group | Grade |
| Labels | stem · box · Length · Bunch | carton · carton · Count · Fruits per carton | kg · bag · Screen · (bunch hidden) |
| Frequencies | One-off, Weekly | Per shipment, Monthly | One-off |
| Specs | — | Dry matter (Subtitle), Certification (Badge) | Cup score (Badge), Process (Column), Variety (Subtitle) |
| Badges | Bestseller, New this season, Limited | GlobalG.A.P., Organic | Microlot, Top lot |
| Estimate | on | off | on |
| Colours | brand #1E4D3A, paper #F6F6F1, ink #18181A | brand #2E4A23, accent #C9A227 | brand #3B2418, accent #B5532E |

The mockups in `.superpowers/brainstorm/233157-1793000081/content/`
(`almanac-v1.html`, `templates-v1.html`) are the visual reference for
spacing, hierarchy and tone. They are not pixel specs.

Setup creates the starters through `after_install` / migrate, not
patches.txt (install-app skips patches). It never overwrites a starter a site
has edited. A one-time step sets `template = "Flowers almanac"` on catalogues
that have none.

## CRM side

- **Settings → Catalogue templates** (new tab):
  - a list of templates with New, Copy and Delete (blocked while catalogues
    use the template);
  - an editor with sections: Preset · Colours · Type · Cover · Wording ·
    Grouping & colour groups · Spec columns · Badges · Sections;
  - a **live preview** on the right.
- **Live preview (user's decision):**
  - An iframe of the real buyer page for a catalogue picked in the editor.
  - The editor posts the unsaved template to it (`postMessage`), and the page
    re-renders with it.
  - In preview mode, nothing is recorded (no views) and the form can't submit.
  - Preview mode needs a logged-in CRM user, and takes postMessage only from
    the same origin.
  - **My call:** preview shows any catalogue the user can read, whatever its
    status or dates. It uses its own logged-in endpoint
    (`crm_catalogue_preview`), returning the same payload as
    `catalogue_view` without the status checks.
- **Validation:**
  - Colours must be hex.
  - Warn (don't block) when a text/background pair falls below WCAG 4.5:1:
    ink on paper, brand_ink on brand, accent_ink on accent, badge ink on
    background.
  - Spec keys must be unique slugs.
  - Frequencies must be non-empty.
- **Catalogue editor:**
  - a template picker;
  - a cover image override;
  - per line: spec inputs (one per template spec column), a badges
    multi-select from the template list, a note, a colour group override
    (showing the derived group as a placeholder);
  - a **Mixes** panel: add a mix, name it, pick lines and boxes.
- **Import (user's decision: flowers sheet only for now):** the parser
  stays the Marginpar-style one.
  - It takes the catalogue's template, and fills template spec columns from
    the sheet columns named in `import_headers`: Column specs go onto
    lines, Badge/Subtitle specs onto the product row.
  - The colour word goes to `color`; the group is derived.
  - Avocado and coffee lines are typed in the editor. A mappable import
    for other crops waits until real sheets exist.
- **Permissions:** templates are written by Settings write roles (System
  Manager, Sales Manager, CRM Manager) and read by CRM roles. Guests never
  read a template directly: `catalogue_view` returns the resolved display
  config with the catalogue.

## Guest API change

`catalogue_view` additionally returns:
- `theme`: colours, font pair, cover mode and image, logo;
- `text`: every label after `{unit}`, `{pack}` and `{n}` substitution;
- `sections`: the switches;
- `groups` in display order, with group label/swatch, and per product/line
  the specs, badges (with colours), note and mixes.

The page JS renders from that. `catalogue_submit` is unchanged, apart from
accepting any frequency in the template's list. The submit's frequency
validation moves from the fixed One-off/Weekly to the template's list.
Interest Item `frequency` becomes Data. Make Opportunity marks a line as
recurring when its frequency row has `recurring` set.

## Constraints

- Frappe/ERPNext v16. The existing traps in memory apply:
  - Jinja doesn't autoescape;
  - a GET request's writes aren't committed;
  - a Custom Field insert in a test is DDL;
  - a null Float reads back as 0;
  - new fields on a saved Single need a backfill (templates are a regular
    doctype, so this applies only to new Settings fields).
- All template strings are inserted as text (escaped). Colours are applied
  through CSS custom properties, validated as hex server-side before they
  reach the page.
- The buyer page stays framework-free, under ~60 KB JS+CSS gzipped excluding
  fonts. Respect `prefers-reduced-motion`. Visible keyboard focus. Usable at
  360px wide.
- The SPA keeps its Vite chunking; the editor is lazy-loaded.
- Tests for: template validation, colour-group resolution, the starter seed
  (idempotent), the catalogue_view payload, the import spec mapping, the
  estimate rule (a pure function tested in Python, then ported to JS), and the
  frequency list on submit.

## Left to the builder

The items marked Builder's call; the extra font pairs; exact spacing and
type scale within the mockups' direction; the Field guide and Market sheet
preset values; empty, loading and error states; and the copy of the starter
templates beyond what is listed.
