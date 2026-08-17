# Overview: demand, conversion, a funnel that is a funnel, and leads you can create

## Why

Six requests, all landing on the Overview:

1. Prospect should read before "to opportunity" in the KPI row.
2. You cannot tell whether a client opened an email — ERPNext can, this app cannot.
3. Salesperson performance shows what a rep *sold*, never what a rep *converts*.
4. Nothing anywhere shows what flowers clients are *asking for*, only what they bought.
5. The Sales Funnel card is five bars that do not describe a funnel.
6. A lead cannot be created — let alone converted — without leaving for the desk.

(5) is the one worth stating plainly, because the codebase already knew about it.
`api/pipeline.py` documents, in its module docstring, that counting each stage
independently "produces nonsense when the stages are not linked: it reports 4
leads and 1,429 orders in the same funnel, as though orders were 300x the leads
that produced them." That module then built a correct cohort funnel for the
Analytics section — and left the broken one on the Overview. This design deletes
the broken one and gives both sections the same walk.

## What is already true, and must not be rebuilt

Measured on `kaitet.local` before anything here was designed:

| Fact | Consequence |
|---|---|
| 9,202 of 21,299 sent Communications carry `read_by_recipient=1` | Open tracking is **already live**. This is a display job, not a plumbing job. |
| 47 Email Accounts have `track_email_status=1` | The tracking pixel is being injected; `crm_send_email` already passes `communication=` to `sendmail`. |
| Frappe stores `read_by_recipient` (bool) + `read_by_recipient_on` (first open only) | **There is no open counter.** `update_communication_as_read` returns early once the flag is set. "Opened ×3" is not obtainable and will not be shown. |
| 45 Opportunities have `opportunity_from='Lead'`, 8 have `'Prospect'` | The cohort walk unions both routes. See the correction below — the second route recovers nothing today. |
| 30 rows in `Prospect Lead`, against 45 lead→opportunity links | Prospect **cannot be a funnel stage**: Leads 112 → Prospects 30 → Opportunities 45 widens. |
| 6 Opportunity Item rows, 48 Quotation Item rows, 43,714 Sales Order Item rows | The demand card starts nearly empty. It must say so rather than look broken. |
| `Lead.lead_owner` has 14 distinct values; `Lead.owner` is 46 Guest / 31 Administrator | Conversion must key on `lead_owner`, not `owner`. |
| Only 6 users appear in both `Lead.lead_owner` and `Sales Order.owner` | Conversion cannot be a column on the existing rep scorecard; it needs its own card. |
| `Guest` owns 63 of 112 leads and 26 of 59 opportunities | "Unassigned" is a real row with a real finding in it, not a rounding error. |

Per `upande-crm-surfaces-not-reimplementations`: the write layer delegates to
ERPNext's own mappers (`lead.make_opportunity`, `prospect.make_opportunity`,
`lead.add_lead_to_prospect`) rather than reproducing their field mapping.

## Corrections found during implementation

Three claims in the original draft of this document were wrong. They are recorded
rather than quietly edited out, because each one changed the build.

**The prospect route recovers nothing.** The draft said the shared walk would fix
an undercount of 8 opportunities in the Analytics funnel. It does not. Those 8
sit on five prospects — Asia Pacific Florals, Deutsche Blumen AG, Gulf
Horticulture Holdings, MSD, Nippon Flower Trading — that have **zero** rows in
`Prospect Lead`, while the 30 prospects that do carry lead links have no
opportunities. The two populations do not intersect, so `via_prospect` is 0 and
the sub-band never draws. The route is still walked: it is the correct traversal,
it costs one indexed query, and it starts counting the moment somebody converts a
lead through a prospect from the new dialog. It is simply not a bug fix.

**A fixed field allowlist could not create a lead on this site.** Lead here has
sixteen mandatory fields, two of them custom (`custom_business_unit`,
`custom_business_registration_number`), plus `country`, `city`, `whatsapp_no` and
others the draft's allowlist never mentioned. Every create failed on
`MandatoryError` with no way for the dialog to even ask for the values. The
allowlist is therefore computed: a fixed base, widened by the site's own
mandatory fields read from the meta, minus a `PROTECTED_FIELDS` denylist that
`owner`, `docstatus`, timestamps and assignment internals can never leave. The
form renders one input per discovered field, so a customised Lead is fillable
from the CRM instead of only from the desk.

**"Opened ×3" was never obtainable**, as noted in the table above — confirmed
against `update_communication_as_read`, which returns early once the flag is set.
The indicator shows whether and when, and nothing else.

## Module layout

```
api/funnel.py    NEW   cohort(frm, to, scope) -> stages + drop-offs + samples
                       imported by pipeline.py AND command.py
api/leads.py     NEW   write layer: lead save, two converts, form options, item search
api/demand.py    NEW   read layer: flowers asked for, by variety and by client
api/command.py   +70   _rep_conversion(), returned by crm_sales_track_record
api/crm.py       ~15   read-receipt columns in crm_mail_data; old funnel removed
api/pipeline.py  -60   own walk deleted; imports funnel.cohort
```

`funnel.py` and `demand.py` follow `crm.py`'s **read** contract: every query
individually guarded, degrading to zero or empty. `leads.py` follows
`activity.py`'s **write** contract, which is the inverse — every failure must
surface, no bare `except`, an explicit field allowlist, and real
`frappe.has_permission` checks.

That last point is deliberate. Per `crm-broad-visibility-intended`, the CRM
dashboards bypass record-level permissions by design so a manager sees the whole
pipeline. Writes do **not** inherit that. A user who can read every lead on the
dashboard must still hold create permission on Lead to make one.

---

## 1. KPI tile order

`Kpis.jsx`: swap tiles 2 and 3. The row becomes

    New leads · Prospects · To opportunity · Customers · Upcoming · Follow-ups

Six tiles, grid unchanged. The comment above the array is updated to record why
the order is what it is — an account becomes a prospect before it becomes an
opportunity, so the row should read in that direction.

## 2. Email open indicator

### Backend

`crm_mail_data` (`api/crm.py`) adds `read_by_recipient`, `read_by_recipient_on`
and `delivery_status` to its `select`. Per row, after the existing `unread`
computation:

```python
r["opened"] = 1 if (direction == "Sent" and r.get("read_by_recipient")) else 0
r["opened_on"] = r.get("read_by_recipient_on") if r["opened"] else None
```

Guarded on column existence, because `read_by_recipient` is a core field but this
module never assumes a column exists.

`crm_send_email` is **not** changed. Tracking already works; and the
`read_receipt` field is the RFC `Disposition-Notification-To` header, a different
mechanism that prompts the recipient's mail client for consent. Turning that on
is a behaviour change nobody asked for.

### Frontend

A shared `<OpenIndicator />` used by both views, rendering only for sent mail:

- opened → filled dot, `opened · <relative time>`
- not opened → hollow dot, `no open recorded`

The wording is deliberate. Pixel tracking undercounts: a recipient whose client
blocks images reads the mail and never registers. `no open recorded` is true;
`not opened` would not be. The tooltip carries the full caveat, including that
tracking requires *Track Email Status* on the outgoing account.

`MailList.jsx` renders it under the subject; `ThreadView.jsx` renders it in the
message header beside the existing `delivery_status` badge.

## 3. Conversion by salesperson

`_rep_conversion(frm, to, scope)` in `api/command.py`, returned as
`rep_conversion` from `crm_sales_track_record` — no extra round trip, and it
lands beside `rep_performance`, which feeds the card directly above it.

Keyed on `Lead.lead_owner`. Per owner:

| Field | Meaning |
|---|---|
| `leads` | leads created in range with this `lead_owner` |
| `to_opp` | of those, how many reached an Opportunity **by linkage** |
| `won` | of those opportunities, how many are `status='Converted'` |
| `rate` | `won / leads` |
| `opp_rate` | `to_opp / leads` |

`to_opp` uses the same union as the funnel — `opportunity_from='Lead'` plus the
prospect route — so the two cards cannot disagree. Status strings are not used:
`Lead.status='Opportunity'` is set by a workflow that does not always fire.

`Guest`, `Administrator` and blank collapse into one **Unassigned** row, pinned
last regardless of sort, and excluded from the ranking bar's maximum.

Sorted by `leads` descending, not by `rate`. One lead converted is not a 100%
closer, and rate-sorting would put that row on top. The rate renders as a bar, so
the eye still ranks it without the order lying.

New `Overview/RepConversion.jsx`, placed immediately after `RepScorecard`.

## 4. Flowers in demand

`api/demand.py` → `crm_demand(date_from, date_to, customer)`.

Sources, unioned:

- **Opportunity Item** joined to Opportunity where `docstatus < 2` and
  `status not in ('Lost', 'Closed')`
- **Quotation Item** joined to Quotation where `docstatus = 1` and
  `status not in ('Lost', 'Expired', 'Cancelled')`

Both are demand that has not become an order. Grouped by `item_code`: stems from
`qty`, value from `base_amount`, and a distinct client count. Client identity
comes from `party_name` / `customer_name` on the parent.

Money is summed from `base_*` columns only, matching `command.py`'s stated rule —
transaction currencies on this site are mixed and only company-currency fields
are summable.

Payload also carries `sources: {opportunity_lines, quotation_lines}`.

### The empty state is a feature

Six opportunity lines and 48 quotation lines exist today. The card will look
nearly empty, and it should say why rather than render a blank panel:

> Demand is read from the flower lines on open opportunities and quotations.
> 6 opportunity lines and 48 quotation lines in this range. Adding varieties when
> you convert a lead fills this in.

That sentence points directly at section 7, which is where the data comes from.
This is the one feature whose value is mostly forward-looking, and the UI admits
it instead of implying the query is broken.

New `Overview/Demand.jsx`, placed beside `TopSellers` in the "Who buys what"
band — *asked for* next to *sold*, which is the contrast that makes either
number mean something.

## 5. The funnel

### `api/funnel.py::cohort(frm, to, scope)`

One lead cohort, walked forward down both routes:

1. Leads created in range (scoped).
2. Opportunities reached by either
   `opportunity_from='Lead' and party_name in cohort`, **or**
   `Prospect Lead.lead in cohort` → `Prospect` → `opportunity_from='Prospect' and party_name in those prospects`.
   Deduplicated on opportunity name.
3. Won: those opportunities with `status='Converted'`.

Returns three **monotonic** stages. Each carries `count`, `of_previous`,
`of_first`, `dropped` (count lost before the next stage) and `sample` — up to 20
records with name and label, so the drill needs no second endpoint.

The Opportunities stage additionally carries `direct` and `via_prospect`.

Prospect is **not** a stage. 30 leads link to a prospect while 45 reach an
opportunity, so drawing Prospect as a stage makes the shape bulge back out at
Opportunities. This is the identical failure `pipeline.py` refused to ship when
it excluded Quotations: "inserting it would draw a funnel that narrows to 3 and
then widens back to 20 — visibly wrong, and wrong about the process."

### Consumers

- `pipeline.py::crm_analytics_funnel` imports `cohort` and deletes its own walk.
  It gains the prospect route — which finds nothing today, see the corrections
  above — and reports both route counts under `linkage`. Its velocity, linkage
  and order-book sections are otherwise untouched.
- `crm_command_center` returns `funnel`.
- The independently-counted `funnel` key is **removed** from
  `crm_dashboard_overview`. Only `Overview/index.jsx` consumes it. This is the
  only breaking payload change in this design.

### `Overview/Funnel.jsx`

Inline SVG. One tapered polygon per stage, width proportional to count, narrowing
downward. Between each pair, the drop-off peels off to the right as a ribbon
carrying its count and its reason ("never progressed", "lost or still open").
Prospect appears as a shaded inner band on the Opportunity segment, labelled
`via prospect`.

Clicking a stage opens a popover listing that stage's `sample` records, each
routing to the desk through the existing `openFrappe`. Theme tokens only — the
ink→gold ramp already used by `FUNNEL_RAMP`, not hardcoded hex.

## 6. Lead creation and conversion

### `api/leads.py`

| Endpoint | Delegates to | Notes |
|---|---|---|
| `crm_lead_save(lead)` | Lead controller | Explicit field allowlist |
| `crm_lead_to_prospect(lead, prospect=None)` | `lead.add_lead_to_prospect`, else creates + links | |
| `crm_lead_to_opportunity(lead, payload)` | `lead.make_opportunity` | then stage, closing date, items |
| `crm_prospect_to_opportunity(prospect, payload)` | `prospect.make_opportunity` | then stage, closing date, items |
| `crm_lead_form_options()` | — | Lead Source, Territory, Industry, statuses, assignable users, sales stages |
| `crm_flower_search(q)` | Item | `is_sales_item=1`, not disabled |

The lead allowlist is a fixed base (`lead_name`, `first_name`, `last_name`,
`company_name`, `email_id`, `mobile_no`, `phone`, `source`, `territory`,
`industry`, `market_segment`, `lead_owner`, `status`, `no_of_employees`,
`website`, …) **unioned with whatever this site has made mandatory**, read from
the Lead meta at call time. Anything outside that union is dropped rather than
written, and `PROTECTED_FIELDS` — `owner`, `docstatus`, `name`, timestamps,
`_assign`, `_user_tags`, `naming_series` — is subtracted last, so no schema
change can make an internal field writable. See the corrections above for why
this is computed rather than frozen.

Item lines accept `item_code`, `qty`, `rate` only. `item_code` is validated
against Item before the child row is built.

Conversion is transactional in the sense that matters: if building the
Opportunity throws, the Lead is left exactly as it was. No partial state, and no
swallowed exception — the dialog shows the real reason.

### Frontend

- `LeadDialog.jsx` — create a lead. On save, offers **Convert now**.
- `ConvertDialog.jsx` — to Prospect, or to Opportunity with variety / stems /
  rate lines, using `LinkSearch` for the item picker.

Both follow `CallDialog`'s structure: `useStore` slice for open/closed state,
throwing save so the dialog keeps what was typed, error line in the footer. Both
lazy-loaded and mounted in `App.jsx` beside the existing dialogs.

Entry point is a **New lead** button on the Overview beside the KPI row.
Converting an existing lead goes through a lead search in the same dialog.

Scoped to the Overview, because that is what was asked for ("from here"). Wiring
the same actions into the Leads section's rows would be cheap but is not in
scope.

## Testing

New `test_funnel.py`, `test_leads.py`, `test_demand.py`; `test_command.py`
extended. Following `test_calls.py`'s stated principle for the write module —
every rejection path asserted, because a lead that appears to save and does not
is the worst outcome here.

Specifically:

- The funnel never widens: `count[i+1] <= count[i]` for every cohort, including
  an empty one.
- A lead that reaches an opportunity by both routes is counted exactly once.
- `direct + via_prospect == opportunities` always.
- A failed opportunity conversion leaves the Lead unchanged.
- The field allowlist drops `owner` and `docstatus`.
- `crm_lead_save` without Lead create permission raises `PermissionError`.
- `crm_demand` on a site with no Opportunity Item returns empty, not an error.
- Read-receipt fields surface on sent mail and are absent on received mail.

## Risks

**The demand card will look empty on day one.** That is honest, and the empty
state says so, but it is the one deliverable here whose value is entirely
forward-looking. If an immediately-populated card was wanted, the revealed-demand
reading (varieties each client repeatedly orders, from the 43,714 Sales Order
Item rows) is the version with data behind it today — at the cost of overlapping
`TopSellers`.

**Removing `funnel` from `crm_dashboard_overview`** is the only breaking change
to an existing payload. Only `Overview/index.jsx` reads it in this repo; an
external caller of that endpoint would notice. `test_scope.py` followed the
funnel to `crm_command_center` and now asserts the old key is gone.

**A latent Tailwind bug exists elsewhere in the app.** The theme defines its
semantic colours as bare `var(--bad)` rather than channel triples, so Tailwind's
slash-opacity modifier (`bg-bad/55`) compiles to an invalid colour and renders
nothing. This bit the funnel's drop-off wedge, which was fixed with an explicit
`style` opacity. Three pre-existing instances remain and are **not** touched
here: `sections/WhatsApp/Thread.jsx:89` (`border-gold/30`, `border-bad/40`) and
`sections/WhatsApp/Dashboard.jsx:33` (`border-bad/40`). Those borders are
currently invisible.
