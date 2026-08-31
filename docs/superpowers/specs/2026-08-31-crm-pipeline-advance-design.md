# Advancing a record through the pipeline, from the dashboard

*2026-08-31*

## The problem

The CRM dashboard can capture a lead and convert it two ways: to a Prospect, or to
an Opportunity. Everything after that — quoting, and becoming a customer — means
opening the desk. That is the whole of the gap this design closes.

Two facts, both measured on `kaitet.local`, decide most of what follows.

**A quotation can be addressed to a Lead.** ERPNext supports
`Quotation.quotation_to = "Lead"` natively, and turns that lead into a customer
when the quote becomes a Sales Order. Quoting before the customer exists is a
supported path, not something this app has to invent.

**Conversion to Customer currently throws data away.** `Customer.email_id` and
`Customer.mobile_no` are Read Only with `fetch_from = customer_primary_contact.*`,
and Customer has no `phone` field at all. ERPNext's `lead._make_customer` sets the
primary contact only from a Contact that already exists, and a lead captured
through this app has none. The result is visible in the data: **9 of the 10
lead-derived customers on this site have no primary contact and no primary
address**, so the email, mobile and phone collected on those leads are gone.

Worse, two *required* Customer fields have 100%-populated Lead sources under
different names that no mapper maps:

| Customer field | required | Lead source | populated |
|---|---|---|---|
| `default_currency` | yes | `custom_billing_currency` | 100% |
| `default_price_list` | yes | `custom_price_list` | 100% |

So a conversion today either fails on MandatoryError or silently takes a global
default that contradicts what the salesperson recorded.

## What gets built

Every hop in the pipeline, available from the dashboard, with the data that exists
on the source landing somewhere real on the target.

```
Lead ─┬─► Opportunity ─┬─► Quotation ─► Customer
      │                └─► Customer
      ├─► Prospect ──────► Customer
      ├─► Quotation ─────► Customer
      └─► Customer  (skips the quote; allowed, and labelled as such)
```

Quotations land as **drafts**. Submitting, printing and emailing stay in the desk.
A consequence worth stating: `Lead.status` does not flip to `Quotation`, because
ERPNext only counts submitted quotes (`Lead.has_quotation` filters `docstatus: 1`).
Setting it by hand would make the funnel count a quote nobody sent.

## Architecture

### Module split

`api/leads.py` has been the write module for capture *and* conversion. It splits:

* **`api/leads.py`** keeps capture — `crm_lead_save`, `crm_lead_form_options`,
  `crm_flower_search`, and the allowlist machinery (`PROTECTED_FIELDS`,
  `_lead_fields`, `_required_lead_fields`) plus the shared `_payload`, `_pick`
  and `_require` helpers.
* **`api/advance.py`** owns every hop, including the three that live in
  `leads.py` today. It imports the three helpers from `leads.py` — one
  directional dependency, no third module for three functions.
* **`api/carry_across.py`** owns what lands where when the target is a Customer.

This changes three whitelisted method paths. `frontend/src/api.js` builds them
from a module-name prefix and is updated with it; nothing outside this app calls
them.

### The route table

One closed `HOPS` dict, keyed `(source_doctype, target_doctype)`. Each entry
carries the dotted path to the ERPNext mapper, the allowlisted header fields,
whether the hop takes item lines, whether items are mandatory, an optional
precondition, and whether the mapper inserts the document itself.

| Hop | Mapper | Notes |
|---|---|---|
| Lead → Prospect | `lead.create_prospect` | controller method, special-cased |
| Lead → Opportunity | `lead.make_opportunity` | header + items |
| Lead → Quotation | `lead.make_quotation` | header + items, items required |
| Lead → Customer | `lead.make_customer` | precondition: no customer yet |
| Prospect → Opportunity | `prospect.make_opportunity` | header + items |
| Prospect → Customer | `prospect.make_customer` | precondition: no customer yet |
| Opportunity → Quotation | `opportunity.make_quotation` | header |
| Opportunity → Customer | `opportunity.make_customer` | precondition: no customer yet |
| Quotation → Customer | `advance._resolve_quotation_customer` | resolver: re-enters `_advance` |

The mapper is resolved **from this table only**, never from anything the client
sends. The dispatcher is shared; the endpoints are not — each hop is a three-line
`@frappe.whitelist()` wrapper (`crm_lead_to_quotation`, `crm_lead_to_customer`,
`crm_opportunity_to_quotation`, …) so every route stays greppable and
individually gated.

### One code path

`_advance(source_doctype, source, target_doctype, payload)`:

1. `_guard()` — the CRM role gate.
2. Source exists, else throw.
3. `_require(source_doctype, "read", source)`.
4. `_require(target_doctype, "create")`.
5. The hop's precondition.
6. Resolve the mapper from `HOPS`.
7. Apply the allowlisted header; append validated item lines.
8. `insert()` — **the last step**, so a bad item line leaves the source untouched.
9. For a Customer target, run the carry-across in the same transaction.

Return envelope, uniform across hops:
`{doctype, name, title, items, amount, currency, existing}`. `existing: true` is
how Quotation → Customer reports "this lead was already a customer, here it is"
rather than returning a name the user believes is new.

### The duplicate guard

`lead.make_customer`, `prospect.make_customer` and `opportunity.make_customer`
have no existing-customer check; ERPNext's own Lead form avoids a second customer
only by hiding the button via `has_customer()`. Exposing a button means owning
that check, so every hop to Customer first looks for
`Customer.lead_name` / `Customer.prospect_name` and refuses with
"{source} is already customer {name}". This is the one piece of logic here that
ERPNext's mappers do not have.

### Carry-across

Driven by a declared per-source mapping table in `api/carry_across.py`, with three
destinations.

**→ Customer**, direct field map. From Lead: `territory` 100%, `market_segment`
100%, `language` 100%, `custom_business_unit` 100%,
`custom_business_registration_number` 100%, `custom_mode_of_payment` 100%,
`website` 18%, `custom_instagram` 19%, `custom_facebook` 11%, `gender` 6%, plus
the two required fields renamed: `custom_billing_currency` → `default_currency`
and `custom_price_list` → `default_price_list`. Prospect and Opportunity get their
own, thinner lists.

**→ a new Contact**, linked by Dynamic Link and set as
`customer_primary_contact`: `first_name`, `last_name`, `salutation`, `email_id`,
`mobile_no`, `phone` (all 100% on Lead), `job_title` 68% → `Contact.designation`,
`gender`. `whatsapp_no` 100% has no Contact field, so it becomes an extra
`Contact Phone` row. **This step is what makes `Customer.email_id` and
`Customer.mobile_no` show anything at all.**

**→ a new Address**, linked and set as `customer_primary_address`:
`custom_billing_street_address` 60% → `address_line1`, `custom_billing_city` 60%
falling back to `city` 100%, `custom_billing_country` 60% falling back to
`country` 100%, `custom_billing_postal_code` 35%, `custom_billing_state_` 27%.
`address_line1` is required and has no 100% fallback, so **when there is no street
line, no Address is created** — a placeholder would pollute 2,913 real addresses
to no benefit.

**→ `customer_details`**, a provenance block for the fields that have data and no
home on Customer: `no_of_employees` 100%, `annual_revenue` 100%,
`qualification_status` 100%, `lead_owner` 100%, `custom_message` 62%. Written as
text rather than as new custom fields on Customer — this app surfaces core
doctypes, it does not reshape them.

The carry-across runs inside the same transaction as the Customer insert. If the
Contact fails, the hop fails: a customer whose email has been lost is the exact
outcome this exists to prevent.

Existing customers are **not** backfilled. The 9 already missing their contact
details stay as they are; writing to live customer records is a separate decision
from building this feature.

## The dashboard

`ConvertDialog.jsx` becomes `AdvanceDialog.jsx` (store key `convertDialog` →
`advanceDialog`), its mode strip driven by a table keyed on the source doctype so
it offers exactly the hops that exist:

```
Lead        → [Opportunity] [Quotation] [Prospect] [Customer]
Prospect    → [Opportunity] [Customer]
Opportunity → [Quotation]   [Customer]
Quotation   → [Customer]
```

Opportunity mode keeps today's fields. Quotation mode adds valid-till, order type,
required varieties, and — on a lead source — an "also raise an opportunity" tick,
implemented as `_advance` twice (Lead → Opportunity, then Opportunity →
Quotation) rather than a tenth route. Prospect mode is unchanged. Customer mode
offers customer group and territory, prefilled from the source.

Customer mode also shows a **carry-across preview**, the one genuinely new piece
of UI:

```
Will carry across
  Contact   Jane Muthoni · jane@acme.co.ke · +254 700 111 222 · WhatsApp +254 …
  Address   12 Rose Road, Naivasha, Kenya · Billing
  Customer  Territory Kenya · Price list Export · Currency EUR · 6 more
  Notes     5 fields with no home on Customer → customer_details
```

It is backed by `crm_advance_preview(source_doctype, source, target_doctype)`,
which runs the same mapping table without inserting. A read, so it degrades to an
empty preview rather than blocking the dialog. Without it the mapping is invisible
and unverifiable; with it, a salesperson sees the email is coming across before
committing.

A shared capture bar is wired into the Leads, Opportunities, Prospects and
Customers sections; the Overview keeps its existing two buttons. The dead
`newDoctype` keys in `nav.js` — declared and never read by anything — come out,
superseded by the capture bars.

## Testing

`tests/test_advance.py` walks Lead → Opportunity → Quotation → Customer in one
test, asserting each link (`party_name`, `quotation.opportunity`,
`customer.lead_name`), then each hop alone, then every rejection path: a quotation
with no items, an unknown item code, a second customer for the same lead, a
missing permission, and the allowlist still dropping `owner` and `docstatus`.

`tests/test_carry_across.py` asserts a converted Customer carries
`default_currency` and `default_price_list` from the lead's custom fields, has a
primary Contact holding the email and both phone numbers, has a primary Address,
and has the provenance block — and that a lead with no street line produces no
Address at all.

`tests/test_leads.py` has its imports updated for the moved functions.

Finally the chain is run once against `kaitet.local` and the created document
names reported, so the result is records that can be opened rather than a green
terminal.

## Deliberately not built

* **No Sales Order hop.** The chain stops at Customer, which is what was asked
  for. `pipeline.py` measures 0 quotation → order links on this site anyway.
* **No free-standing "New customer" form.** A customer with no origin is desk
  data entry, and building one means rebuilding the Customer form inside the CRM.
* **No submit-on-create for quotations.** A mistake on a submitted quote can only
  be fixed by cancel-and-amend.
* **No backfill of the 9 existing contactless customers.**
* **No new custom fields on Customer** for the homeless lead fields.


## What the build changed

Four things the design did not anticipate, each found by running it.

**The quotation hop could not use ERPNext's resolver.** `quotation._make_customer`
inserts the Customer itself, which skips the carry-across — and measured, that
fails outright: this site makes `default_currency` and `default_price_list`
mandatory on Customer, and nothing else fills them. The hop now resolves the
party and re-enters `_advance` through the Lead or Prospect route, so a
quotation-raised customer gets exactly the same treatment as any other.

**Mandatory Customer fields needed a fallback.** A Lead carries answers for both
required fields; a Prospect carries neither, so the prospect and opportunity
routes failed on ERPNext's "Could not auto create Customer" every time.
`carry_across.fill_required` fills any still-empty mandatory field from the
site's own settings — `Selling Settings.selling_price_list`, the company's
default currency — and **never** from an arbitrary row of the link target. What
it cannot answer is left empty, so the insert raises ERPNext's own message
naming the field rather than this module inventing a value nobody chose.

**Contacts and addresses had to be reused, not created.** Two things already
build them on this site: ERPNext's `Lead.after_insert` calls `link_to_contact()`,
and a site Server Script, "Shipping and Billing Address Creation", makes a
billing and a shipping Address. Creating fresh ones gave every converted customer
a duplicate. `ensure_contact` and `ensure_address` now link what exists, fill
only its blank fields, and create only what is missing.

**A numeric zero is not data.** The live walk wrote "Annual revenue: 0.0" into a
customer's details, because `annual_revenue` is present on every lead here and
zero on nearly all of them — the same trap `api/pipeline.py` documents for
`opportunity_amount`. `notes_block` now skips numeric zeros.

## Verified

57 tests across `test_leads`, `test_advance` and `test_carry_across`, and one
live walk on `kaitet.local`:

    Lead CRM-LEAD-2026-00278 (Bloomgate Exports Ltd)
      -> Opportunity CRM-OPP-2026-00048        1 variety line
      -> Quotation   SAL-QTN-2026-00025        to Lead, opportunity linked,
                                               draft, KES 184,800.00
      -> Customer    Bloomgate Exports Ltd     contact Amina Wanjiru linked,
                                               email and mobile fetched through it,
                                               currency USD, price list USD Price List

    Lead CRM-LEAD-2026-00279 (Rift Valley Blooms Ltd)
      -> Quotation   SAL-QTN-2026-00026        direct, no customer created,
                                               lead status still "Lead"

The second walk is the thing that was asked for: a quotation raised against a
lead that is not a customer, with no customer created as a side effect.

One pre-existing site issue surfaced and was **not** fixed, because it is outside
this work: the Server Script "Shipping and Billing Address Creation" inserts an
Address whenever any of street, city or country is set, so a lead with a city but
no street line fails on a mandatory `address_line1` — and its own error handler
then raises `AttributeError: module has no attribute 'get_traceback'`, hiding the
cause. The test fixtures avoid tripping it rather than working around it.
