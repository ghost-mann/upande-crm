# CRM Claims, Quotations, Visits, Pipeline Stages — Design

**Date:** 2026-09-28
**Status:** Decided by the implementer on the user's instruction ("I'm AFK, finish
everything"). Every choice below that the user did not make is marked **Decision**.
**Scope:** Sub-projects 2–5 from the client list. Follows
`2026-09-28-crm-modules-customer-page-theme-design.md` (modules, customer page, theme).

## Data facts (kaitet.local)

- `Issue` is 1,837 **maintenance** tickets (issue_type "Maintenance"), not customer
  claims; no `Customer Feedback` doctype. → Claims need their own doctype.
- Quotation: 27 (23 Draft). **0** Sales Order Items point back at a quotation, so
  quote→order conversion is 0 today; the reporting is honest about that.
- Opportunity.sales_stage uses the stock `Sales Stage` list (Prospecting 43, …).
- Lead: `qualification_status` (Unqualified 69 / In Process 18 / Qualified 28),
  `qualified_by`, `qualified_on` exist. The channel is `utm_source` → `UTM Source`
  (v16); a legacy v15 `source` column still holds 79% of the history. The lead
  dialog currently offers "Lead Source", which does not exist in v16 — its source
  list is always empty. **Bug, fixed here.**
- Event.event_category already has custom "Visit" and "Claim" values (3 and 1 rows).

## 1. Claims (objective: Complaints & Claims Tracking)

**Decision:** new doctype **CRM Claim** (`CLM-.YYYY.-.#####`), module Upande CRM.

| Field | Type | Notes |
|---|---|---|
| customer | Link Customer, reqd | |
| claim_type | Data, reqd | validated against Settings → `claim_types` |
| status | Select | Open / Under Review / Resolved / Rejected |
| raised_on | Date, default Today | |
| reference_doctype | Select | Sales Invoice / Delivery Note / Sales Order, optional |
| reference_name | Dynamic Link | must belong to the same customer |
| item_code | Link Item | optional |
| qty_affected | Float | stems / units |
| amount_claimed, amount_credited | Currency | company currency |
| description | Text Editor, reqd | |
| root_cause | Small Text | |
| resolution | Text | required when Resolved or Rejected |
| resolved_on | Date, read only | set when status becomes Resolved/Rejected, cleared on reopen |
| assigned_to | Link User | |

Settings: `claim_types` (default Quality rejection, Short shipment, Damaged goods,
Late delivery, Wrong variety, Other), `claim_sla_days` (default 7; an open claim older
than this is **overdue**).

API `api/claims.py` (module `claims`): `crm_dashboard_claims(date_from, date_to)` —
KPIs (open, under review, overdue, resolved in range, median days to resolve, claimed
and credited value), by type, by status, rows; `crm_claim_save(claim)`;
`crm_claim_references(customer, kind)` for the order picker;
`crm_customer_claims(name)` for the customer page.

UI: a **Claims** section (Service group) with dashboard, table, "Log a claim" dialog;
a **Claims** tab on the customer page; claims on the customer timeline; an "Open
claims" figure in the customer header.

## 2. Quotations (objectives: Quotation Management; quotation conversion reporting)

**Decision:** read ERPNext `Quotation` — no new doctype. Conversion = a submitted
quotation with at least one Sales Order Item whose `prevdoc_docname` is it.

API `api/quotations.py` (module `quotations`): `crm_dashboard_quotations(range)` —
KPIs (issued, open, converted, lost, expired, conversion rate, average value, median
days quote→order), monthly trend, status mix, rows (party, date, valid till, total,
status, linked orders), top quoted items; `crm_customer_quotations(name)` — the
customer's quotations plus **pricing history**: every quoted rate per item over time.
Settings: `quote_followup_days` (default 7): an open quotation older than this is
flagged "follow up".

UI: a **Quotations** section (Pipeline group); a **Quotations** tab on the customer
page. Creating the order stays in the desk ("Open in desk → Create → Sales Order"),
which is ERPNext's own mapping; the row links there.

## 3. Visits (objective: Event Logging)

**Decision:** new doctype **CRM Visit** (`VIS-.YYYY.-.#####`) with a child table
**CRM Visit Action** — rather than overloading Event, which has no outcome or
follow-up structure.

| Field | Type | Notes |
|---|---|---|
| visit_type | Select, reqd | "Customer visit to farm" / "Sales visit to customer" |
| party_type | Select | Customer / Lead / Prospect |
| party | Dynamic Link, reqd | |
| visit_date | Datetime, reqd | |
| status | Select | Planned / Completed / Cancelled |
| purpose | Data, reqd | validated against Settings → `visit_purposes` |
| location | Data | |
| staff | Small Text | who went / hosted (comma-separated users or names) |
| customer_attendees | Small Text | |
| outcome | Text Editor | required when Completed |
| actions | Table CRM Visit Action | action, assigned_to, due_date, todo (read only) |

On save, every action row without a ToDo gets one (reference = the visit, allocated
to `assigned_to`, due `due_date`), so follow-ups land in Events & Tasks.

Settings: `visit_purposes` (default Farm tour, Variety showcase, Relationship
check-in, Complaint follow-up, Price negotiation, Other).

API `api/visits.py` (module `visits`): `crm_dashboard_visits(range)`,
`crm_visit_save(visit)`, `crm_customer_visits(name)`. UI: a **Visits** section
(Activity group) with dashboard, table and "Log a visit" dialog; a **Visits** tab and
timeline entries on the customer page.

## 4. Pipeline stages & lead qualification (objectives: Lead Capture & Qualification; Sales Pipeline Tracking)

Settings: `opportunity_stages` — ordered list, default Prospecting, Sample Dispatch,
Quotation, Negotiation. Saving settings creates any missing `Sales Stage` record.
`lead_channels` — default Email, Phone Call, Trade Event, Referral, Website; saving
creates any missing `UTM Source`.

**Pipeline board** (new sub-view of Opportunities, module `opps`):
columns = *Leads* (open leads, with qualification chip) → each configured stage
(open opportunities) → *Confirmed customers* (customers created in the range). Cards
move by a stage select: `crm_opportunity_set_stage(name, stage)` (write permission on
that Opportunity). `crm_lead_qualify(name, status)` sets `qualification_status`,
`qualified_by`, `qualified_on`.

Lead capture: the dialog gets **Channel** (`utm_source`, configured channels first)
and **Qualification** fields. Analytics read `coalesce(utm_source, source)` so old and
new leads both count.

## Cross-cutting

- Modules `claims`, `quotations`, `visits` become **available**. Their sections:
  claims → `claims`, quotations → `quotes`, visits → `visits`; the board is a table of
  `opps`. A one-off patch switches them on for sites where the placeholder backfill
  stored 0; fresh installs get 1 from the backfill.
- Customer page tabs gain `quotations`, `claims`, `visits`; each shows only if its
  module is on.
- New doctypes get DocPerms for System Manager, Sales Manager, Sales User, CRM
  Manager, CRM User (read/write/create/report; delete for managers only).
- Every endpoint: `@requires_module`, `_guard()`, per-doctype read/write checks,
  parameterised SQL, empty states rather than errors.
