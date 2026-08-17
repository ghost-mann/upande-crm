# CRM Overview as a Command Center

## Why

The Overview reads as a report, not a command center. It leads with Revenue — a
number the Sales Analytics section already owns — and reduces the day's work to a
single "Open Tasks" count with nothing to act on. Nothing on the page answers the
question a sales manager actually walks in with: *what moved, and why?*

A high-selling variety that stops selling is the most expensive event on this
farm, and today the dashboard cannot show it happening.

## What changes

### KPI row

Revenue and Open Tasks are removed. The row becomes:

| Tile | Value | Sub | Chip |
|---|---|---|---|
| New Leads | count in range | in selected range | ±% vs prior period |
| To Opportunity | conversions | converted from leads | conversion rate |
| Prospects | count | engaged accounts | territories |
| Customers | active | active accounts | companies |
| Upcoming | tasks + events next 7 days | to action this week | overdue count |
| Follow-ups | calls due + emails awaiting reply | needing a response | oldest waiting |

"Conversions to opportunity" counts Leads whose status is `Opportunity` **or**
`Converted`, plus Opportunities whose `opportunity_from` is a Lead in range —
deduplicated by lead name, because a lead that converted and a lead that was
opened as an opportunity are the same event counted two ways in ERPNext.

### Upcoming Tasks & Events table

Replaces the open-tasks metric. One table, tasks and events interleaved in true
chronological order, grouped `Overdue → Today → Tomorrow → This week → Later`.
Columns: when, kind badge, title, who, priority/category, linked record.

- Tasks: open `ToDo` scoped to CRM work (the existing `_crm_todos` rule).
- Events: `Event` with `starts_on >= today`, status Open.
- Overdue tasks (`date < today`) sort first and render in the bad tone.
- Deliberately **not** date-range scoped: "upcoming" means from now forward, and
  a header pill reading "Last 30 days" must not hide tomorrow's meeting. Same
  reasoning as `_aging` and `_targets` in `api/analytics.py`.

### Track record

The centrepiece. Multi-series line chart with two toggles:

- **By flower** / **By salesperson**
- **Revenue** / **Stems**

Top 6 series by revenue in range; buckets adapt to span (daily ≤ 92 days, weekly
≤ 366, monthly beyond) so a 12-month view is readable. Clicking a legend entry
opens the mover drill for that series.

### Movers, and the "why"

A band listing the biggest decliners and gainers against the immediately
preceding window of equal length. Each decliner carries a generated one-line
cause, and opens a drill that decomposes the change exactly:

```
Δrevenue = (Q₁ − Q₀)·r₀  +  (r₁ − r₀)·Q₁
           volume effect     price effect
```

where `Q` is stems and `r` the average realised rate. The two effects sum to the
total change by construction, so the split is arithmetic rather than inference.

The drill also ranks per-customer contributions (`R₁c − R₀c`), labelling an
account with `R₁c = 0` as *stopped buying* rather than *down 100%*, and ranks
per-rep contributions the same way. Where invoices reach back far enough it
reports the same window one year earlier, so a seasonal dip is not mistaken for a
lost account.

The same drill serves a salesperson: which varieties and which accounts moved
under them.

### Top 5 sellers — three views

Tabbed, all against the top 5 varieties by revenue in range:

1. **Matrix** — rows = top customers, columns = the 5 varieties, cells = spend
   with ± vs prior period. An empty cell renders `—`: an account *not* buying a
   house-top variety is itself the signal.
2. **Per customer** — each account's own top 5, since a small account's mix
   differs from the house mix.
3. **By rep** — top 5 salespeople, each expanding to the customers behind the
   number.

### Salesperson performance

Scorecard table: revenue and ±% vs prior, orders, AOV, distinct customers,
varieties sold, and an activity column (calls logged, emails sent, open tasks,
upcoming events) so effort sits beside result. Row click opens the rep drill.

### Follow-ups

Calls needing a callback and sent emails with no reply, side by side, each
actionable through the existing `CallDialog` / `ComposeDialog`.

### Removed as now-duplicated

- *Sales & Orders Trend* card — Booked vs Billed already draws this.
- *Top Customers* card — subsumed by Top Sellers.
- SalesBand's *Top products* and *Sales reps* lists — both are first-class
  sections now.

Retained: SalesBand (Booked vs Billed, target attainment, receivables aging),
the funnel, lead status, and the lead-trend / territories / stages row.

## Architecture

### Backend — `upande_crm/api/command.py`

A read layer, so it follows `api/crm.py` house style: every query individually
guarded, degrading to zero or empty. Three endpoints rather than one, so the
KPI row is not held behind the heaviest query:

| Endpoint | Returns |
|---|---|
| `crm_command_center` | `kpis`, `upcoming`, `follow_ups` |
| `crm_sales_track_record` | `track_record`, `movers`, `top_sellers`, `rep_performance` |
| `crm_mover_detail(kind, key)` | the decomposition, fetched only when a drill opens |

Money is summed from `base_*` columns throughout — transaction currencies on this
site are mixed, so only the company-currency fields are summable. `_company_currency`
is reused from `api/analytics.py` rather than reimplemented.

**Salesperson = Sales Order `owner`.** `Sales Team.sales_person` holds 28 rows
with a single distinct person and attaches to Customer, not to orders; `owner`
has a genuine spread across eight sales staff. This is the choice
`_rep_performance` already made, kept for consistency.

**Flower = the Item.** Varieties are items (Giselle, Fireworks, Dinara…) within
the Spray/Standard Roses groups — 144 distinct items sold. `item_name` falls back
to `item_code`.

### Frontend — `frontend/src/sections/Overview/`

One file per concern, each independently readable:

| File | Purpose |
|---|---|
| `index.jsx` | layout and section order only |
| `Kpis.jsx` | the six tiles |
| `Upcoming.jsx` | merged tasks + events table |
| `TrackRecord.jsx` | multi-series chart + toggles |
| `Movers.jsx` | decliners / gainers band |
| `MoverDrill.jsx` | the decomposition dialog |
| `TopSellers.jsx` | three tabbed views |
| `RepScorecard.jsx` | salesperson performance table |
| `FollowUps.jsx` | calls due + emails awaiting reply |

`MultiLineChart` is added to `charts/Charts.jsx`, drawing series from the existing
`PAL` so the new chart reads as part of the same system.

Store: `command` and `track` join `SECTION_LOADERS`; the drill is fetched on
demand into `moverDetail` and is not part of `loadAll`.

## Testing

`upande_crm/tests/test_command.py`, following `test_analytics.py`:

- every endpoint returns its documented keys on the live site
- the volume/price decomposition sums to the total change (the arithmetic
  identity that makes the "why" trustworthy)
- an account absent from the current window is reported as *stopped*, not −100%
- `upcoming` ignores the date range and never returns a past event
- conversions are not double-counted when a lead is both `Converted` and the
  source of an Opportunity
- an unknown `kind` passed to `crm_mover_detail` is rejected, not queried
