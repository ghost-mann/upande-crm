# CRM Catalogues and Expressions of Interest — Design

**Date:** 2026-10-25
**Status:** Agreed with the user in conversation. Choices the user did not make
are marked **Builder's call**.
**Scope:** a new switchable module in upande_crm. Built and tested first on
`webstore.localhost` (the :8002 default site, which has upande_crm).

## Why

Sales teams send buyers a seasonal offer sheet as an Excel file (the reference is
`Marginpar FOB Combined pricelist Oct–Dec 2026 final.xlsx`). Interest then
comes back by email or WhatsApp in whatever form the buyer likes. Sales re-types
it, and new buyers who get hold of the sheet never enter the CRM at all.

The goal: share a catalogue of selected items from inside the CRM as a link.
Whoever opens it, known customer or stranger, ticks what they want with
quantities. That lands in the CRM as a Lead (or against the existing
Lead/Customer) plus a structured record of the interest, ready for sales to
follow up and later turn into an Opportunity.

**The module must be generic** (any Upande client, not only flowers), proven first
with Marginpar-shaped data.

## Goals

- Any CRM user can build a catalogue, fill it from an Excel offer sheet, edit it,
  and share it.
- Each catalogue has one **public link**, and the user can generate **personal
  links** for specific Leads/Customers. The salesperson picks how to send each
  personal link: **email**, **WhatsApp** or **copy link**. All three are built
  into the CRM.
- Buyers see a branded page (layout C, below) with prices, can switch between
  the catalogue's currencies, enter quantities, and submit.
- A submission creates or matches a Lead/Customer and creates a **Catalogue
  Interest** record. The catalogue's owner is notified.
- The CRM shows who **opened** a personal link and when, view counts for the
  public link, and every submission.

## Non-goals

- No order-taking, payment, stock or availability checks. This is interest, not
  a Sales Order.
- No buyer accounts or login, and no buyer-side editing after submit.
- No confirmation email to the buyer. They see a thank-you page only.
- Event and Christmas/Saints price columns are not carried on a line. A separate
  catalogue covers an events offer.
- The Item master is not restructured. No Item Variants are created per length.

## Anti-goals (would be a failure even if it "works")

- Strangers' submissions creating Website Users, desk users or Customers. A
  public submission creates a **Lead** at most.
- A known buyer's submission creating a duplicate Lead.
- The public page leaking anything beyond the catalogue: no other prices, items
  or customer data, and no guessable link to other catalogues.
- A WhatsApp send that reports success but was never delivered (the CRM's
  existing rule: sends throw).

## Data facts (Marginpar live, checked 2026-10-25)

- Flower Items are **one Item per variety** (e.g. "Aster (Novi Belgii Grp) Dark
  Milka", group "Summer Flowers", UOM Nos), with **no variants** and **no image**.
  Lengths (50/60/70 cm) exist only in the offer sheet.
- Selling Item Prices are effectively absent (one KES row).
- The offer sheet has three tabs: a combined FOB sheet, `USD` and `Euro`. They
  share these columns: Product, VBN, Grade (length), Color, Packrate, Bunch, Price
  (per stem), Price >4 boxes, Weight, event and Christmas prices, and a photo link.
  At the top is a block of ordering terms (lead time, order adjustments, branded
  boxes and sleeves, pack rates fixed, bunching, standing-order priority) and a
  version date.

## Data model

All new doctypes live in module **Upande CRM**.

### CRM Catalogue

| Field | Type | Notes |
|---|---|---|
| title | Data, reqd | e.g. "FOB Offer Oct–Dec 2026" |
| company | Link Company, reqd | branding (name and logo) on the public page |
| status | Select | Draft / Live / Closed. Only Live pages accept views and submissions |
| valid_from, valid_to | Date | optional. Outside the range the page shows "this offer has closed" |
| currencies | Table MultiSelect or child table | 1+ currencies. The first is the page's default |
| volume_tier_qty | Int | the "above N boxes" threshold (4 on the Marginpar sheet). Blank means no tier column |
| terms | Text Editor | the ordering-terms block, shown on the page |
| public_token | Data, unique, read-only | random, unguessable, set on insert |
| lines | Table → CRM Catalogue Line | |
| owner | (standard) | the user notified on submissions |

**Interest visibility (user's decision):** whoever can read the interest's party
(the Lead or Customer) can read the interest. That reuses the CRM's existing
`readable_parties` scoping (commit d598313), since User Permissions skip Dynamic
Links. Catalogue Links follow the same rule. The catalogue owner and CRM managers
see all interests on their catalogues.

Permissions: any CRM role can create. A user edits their own catalogues; CRM
managers edit all. Follow the existing record-level rules the CRM uses
(commit d598313).

### CRM Catalogue Line (child)

| Field | Type | Notes |
|---|---|---|
| item | Link Item, reqd | name, image, description and attributes come from the Item |
| grade | Data | e.g. "60 cm". Free text, so it stays generic |
| box_type | Data | e.g. "Standard", "1/8 box". The offer sheet's 1/8th-box block becomes its own line, with its own pack_qty and price (**user's decision**) |
| color | Data | shown as a pill; imported from the sheet's Color column (**user's decision**: Marginpar Items carry no colour) |
| info_url | Data (URL) | "More info" link on the page; imported from the sheet's Photos (Website) column, which links to product web pages, not images |
| pack_qty | Float | units per box ("Packrate") |
| bunch | Data | e.g. "x10" |
| weight | Float | optional, per box |
| vbn | Data | optional external code. Shown only if set |
| price_<n>, tier_price_<n> | Currency, one pair per catalogue currency | see **Builder's call** below |
| sort_order | (idx) | |

**Builder's call:** how the per-currency prices are stored. Either a nested price
table (line × currency → price, tier_price) or fixed columns for up to N
currencies. Requirement: the page can switch currency, and a line priced in USD
but not EUR shows "—" for EUR rather than 0.

Lines group on the page **by Item**, and within an Item by line order. Photos come
only from the Item's `image`. Until someone uploads one, the card is text-only (a
neutral placeholder). The import does not fetch images and does not touch the
Item master (**user's decision**).

### CRM Catalogue Link (personal links)

| Field | Type | Notes |
|---|---|---|
| catalogue | Link CRM Catalogue | |
| party_type | Select | Lead / Customer |
| party | Dynamic Link | |
| contact_email, contact_phone | Data | where it was sent |
| token | Data, unique | |
| sent_via | Select | Email / WhatsApp / Copied |
| sent_by, sent_on | | |
| first_opened_on, last_opened_on, open_count | | opens are tracked |

### CRM Catalogue Visit (tracking)

One row per page open: catalogue, link (blank for the public link), timestamp,
and a hashed IP/user-agent only if needed for de-duplication. **Builder's call:**
roll up public views as a counter on the catalogue rather than one row per view,
if row volume is a concern.

### CRM Catalogue Interest (the expression of interest)

| Field | Type | Notes |
|---|---|---|
| catalogue | Link | |
| via_link | Link CRM Catalogue Link | blank if from the public link |
| party_type / party | Lead or Customer | set by matching (below) |
| contact_name, company_name, email, phone, country, message | | as entered, or prefilled from the party |
| currency | | the currency shown when submitted |
| items | Table → CRM Catalogue Interest Item | |
| status | Select | New / Contacted / Converted / Dropped |
| opportunity | Link Opportunity | set by "Make Opportunity" |

**CRM Catalogue Interest Item:** item, grade, qty (boxes), frequency (One-off /
Weekly), plus a copy of the unit price, tier price and pack_qty as shown. That
copy is a snapshot, so later catalogue edits don't change what the buyer saw.

## Buyer page (public)

- Route: a `www` page under the site, e.g. `/catalogue/<token>`. The token is
  either a catalogue's `public_token` or a personal link's `token`.
- **Layout C (chosen):** one card per Item with its photo, name, attribute pills
  (e.g. colour) and description. Inside each card, one row per catalogue line:
  grade, box type, pack info (pack_qty, bunch, weight), price per unit, tier price
  ("above N boxes"), and a quantity box plus a **One-off / Weekly** selector.
  The terms block sits at the top. A sticky bar shows the line count and
  "Send interest".
- A **currency switch** sits at the top when the catalogue has more than one
  currency.
- **Public link:** the contact form asks for name, company, email (required),
  phone, country and message.
- **Personal link:** already known, so the form is prefilled with the party's
  details and can be edited.
- After submit: a thank-you page. Nothing is emailed to the buyer.
- Must work well on a phone.
- Runs as Guest. Endpoints are `allow_guest` and token-scoped. Each request
  re-checks status and validity. Spam protection is a **Builder's call**: at
  minimum a honeypot field plus a per-IP rate limit.
- Branding: company name and logo from the catalogue's Company.

## What a submission does

1. Resolve the party:
   - A personal link uses its party **when the email typed matches the party's
     email** (or is left as prefilled). A different email falls through to
     public matching, and the interest still records `via_link` (**user's
     decision**: forwarded links must not file a stranger under the original
     party).
   - A public link matches on **email**, then **phone** (the WhatsApp module's
     last-9-digits suffix rule), against Contacts linked to a Lead or Customer,
     and against Lead.email_id. A Customer match wins over a Lead match.
   - No match creates a **Lead** (source / UTM: "Catalogue", campaign = the
     catalogue title), owned by the catalogue's owner.
2. Create a **CRM Catalogue Interest** linked to that party. The items are
   snapshotted.
3. Notify the catalogue's **owner**: an email plus a Frappe notification, with
   a link to the interest in the CRM.
4. Add a timeline comment on the Lead/Customer.

Existing Leads and Customers are never overwritten by what a buyer typed. A
differing phone number or company name goes on the interest only.

## CRM side (SPA)

A new switchable module **Catalogues** in `modules.py` (group: Pipeline or
Marketing, **Builder's call**), with nav entries:

- **Catalogues:** list of catalogues with status, validity, views, submissions
  and owner. Create, duplicate and close.
- **Catalogue editor:** title, company, currencies, validity, tier threshold and
  terms, plus a line grid with an add-Item picker. **Import offer sheet** and
  **share**.
- **Share dialog:** copy the public link, or pick Leads/Customers and a channel
  per send:
  - **Email:** a template (subject/body with `{{ link }}`, editable before
    sending), sent through the existing `crm_send_email`, filed against the party.
  - **WhatsApp:** through the existing `crm_whatsapp_send`. Inside the 24-hour
    window it sends free text with the link. Outside it, it sends the approved
    template chosen in **CRM Settings** with the link as a parameter, via
    `crm_whatsapp_send_template`. If no template is configured, the WhatsApp
    option says so and is disabled for that recipient. **Builder's call:** a new
    CRM Settings field `catalogue_whatsapp_template`, with the link filling the
    template's first body variable (`{{1}}`).
    `crm_whatsapp_send_template` takes no parameters today, so extend it to
    pass body parameters through to `frappe_whatsapp`.
  - **Builder's call:** each channel follows its own module. With the Mail module
    off, the email option hides. With the WhatsApp module off or `frappe_whatsapp`
    missing, the WhatsApp option hides. Copy link always works.
  - **Copy link:** creates the personal link and copies it.

  Every option creates a CRM Catalogue Link row, so opens are tracked.
- **Interests:** a list of submissions with status, party, catalogue and
  line/box totals, and a detail view. **Make Opportunity** creates an Opportunity
  for the party, copying the items (qty = boxes × pack_qty in the Item's UOM, or
  boxes. **Builder's call**, keep it consistent with how Opportunities are
  quoted). It links back and sets status Converted. **User's decision:** a
  Weekly line goes across **as per-week quantity, unchanged**, with "Weekly" in
  the Opportunity Item's description, and sales adjusts. The rate is the tier
  price when that line's boxes exceed `volume_tier_qty` (judged **per line**),
  otherwise the standard price, in the interest's currency.
- On the Lead and Customer pages: their catalogue interests and links sent.

## Offer-sheet import

- Upload an `.xlsx` in the catalogue editor. Read the tabs whose name matches a
  catalogue currency (`USD`, `Euro`/`EUR`). Find the header row by its labels
  (`Product`, `VBN`, `Grade`, `Color`) rather than by a fixed row number.
- Matching each row to an Item: VBN against an Item field if one exists, then
  exact `item_name`, then a normalised name (quotes, brackets and case
  stripped). Unmatched rows are listed for the user to map by hand or skip.
  Nothing is created in the Item master automatically.
- Columns map to grade, colour, info_url, pack_qty, bunch, price, tier price and
  weight. The **Standard Box** block and the **1/8th box** block each become a
  line, with box_type "Standard" and "1/8 box". A block with no price is skipped.
  Event and Christmas columns are ignored.
- Rows that aren't a single variety (e.g. "Aster (5 varieties)", colour "All",
  no VBN) usually won't match an Item. They are listed as unmatched like any
  other row, and the user maps them to an Item or skips them. There is no
  free-text line type (**Builder's call**, since `item` is required).
- Import fills the line grid for review. The user saves. Re-importing replaces
  the lines, after a confirmation.
- The terms block above the header row may be imported into `terms`
  (**Builder's call**).

## Constraints

- Frappe/ERPNext **v16**. Respect the v16 traps in memory: no SQL functions in
  `get_list` fields (use `frappe.qb`), escape `_` in LIKE, and don't trust a
  Single's new Check field without a backfill.
- The SPA build: keep the existing Vite chunking (only a react-core leaf chunk).
- The CRM must keep working without `frappe_whatsapp`. The WhatsApp channel then
  hides itself, like the existing module.
- Doctypes need `after_install`/migrate-safe setup for any seed data (patches
  don't run on install-app).
- Test as a real Sales User, not as Administrator, and test the public page as
  Guest.

## Test plan (webstore.localhost)

- Seed a handful of Marginpar-like Items (a few varieties, with images) and
  import the real offer sheet into a catalogue with USD + EUR.
- Public link as Guest: a new email creates a Lead and an interest. A known
  customer's email attaches to the Customer and creates no Lead.
- Personal link: the page opens prefilled, and the open is recorded. Submitting
  attaches to the right party.
- Share by email, by WhatsApp (in and outside the window, or the disabled state
  where WhatsApp isn't set up), and by copy.
- Closed / out-of-dates catalogue: the page refuses to submit.
- Make Opportunity copies the lines correctly.
- Module switched off: the nav disappears and endpoints refuse.

## Left to the builder

The items marked **Builder's call** above. The exact doctype naming series.
Visual styling within the CRM's existing navy theme. The empty, error and
loading states. The thank-you copy.
