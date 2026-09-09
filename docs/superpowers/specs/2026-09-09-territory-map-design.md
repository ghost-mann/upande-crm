# Territory Map — design

A fullscreen interactive world map as a CRM section. Hover a country for an
intel readout; click to zoom and pin a deeper one.

## Why this shape

Every design choice below follows from four facts measured on `kaitet.local`,
not from assumption:

1. **Territories are countries.** 206 records: 8 continent groups holding ~196
   countries. A choropleth is the natural projection of that tree, and needs no
   new taxonomy.
2. **There is no point geometry.** `Address` has no `latitude`/`longitude`
   column, so pins are impossible. Polygons are the only option.
3. **`Address.country` disagrees with `Territory`** (`Russian Federation` vs
   `Russia`), so the `territory` field is the only reliable join. Country
   strings are not used anywhere in this feature.
4. **35% of invoices are tagged to a group, not a country** — see *The regional
   ledger* below. This is the fact that most shapes the design.

## Data reality

| Doctype | Tagged | Total |
|---|---|---|
| Lead | 115 | 115 |
| Opportunity | 60 | 61 |
| Prospect | 43 | 44 |
| Customer | 380 | 888 |
| Sales Invoice | 9,849 | 13,780 |
| Sales Order | 10,138 | 11,323 |

Only **48 territories carry any data at all**. The map will be mostly empty, and
that is the correct picture — the design leans into it rather than inventing
density.

## The regional ledger

Records are tagged against **group** territories as often as leaf ones:

| Territory | Kind | Invoices | Customers |
|---|---|---|---|
| Middle East | group | 2,816 | 94 |
| Europe | group | 425 | 14 |
| Africa | group | 235 | 41 |
| Asia | group | 0 | 4 |
| All Territories | root | 1 | 66 |

3,477 of 9,849 invoices — **35%** — sit on a territory that is not a country.
There is no honest way to paint them: distributing Middle East's 2,816 invoices
across its member countries would be fabrication.

So the map shows what is country-attributable, and a **regional ledger** docked
below the intel panel accounts for the rest, explicitly labelled as
un-attributable. The two figures together always reconcile to the totals. A map
that quietly dropped a third of the revenue would be worse than no map.

## Geometry join

`world-atlas` `countries-110m.json` (108KB) — 177 features keyed by ISO 3166-1
numeric id, carrying only a Natural Earth `name` ("W. Sahara", "Dem. Rep.
Congo"). Territory names are joined to **ISO numeric**, never to those names.

Normalising (accent-fold, strip parentheticals, `Rep.`→`Republic`) auto-matches
159 of 196 leaves. The remaining 37 split two ways:

- **7 have a polygon under a different name** — Bosnia and Herzegovina, DR
  Congo, Republic of the Congo, Equatorial Guinea, North Macedonia, Palestine
  State, South Sudan. Hand-mapped.
- **30 have no polygon at 110m** — micro-states and island nations (Singapore,
  Hong Kong, Malta, Bahrain, Mauritius, Seychelles, the Caribbean and Pacific
  states). Singapore already carries live data, so this is not hypothetical.

Micro-states render as **centroid dots**, hoverable and clickable exactly like a
country. This is better than a higher-resolution atlas would be: a two-pixel
Singapore polygon is unhittable at any zoom, and `countries-50m.json` costs
650KB more to still not fix that.

The name→ISO table is the fragile part of this feature. It is explicit, not
inferred at runtime, and a test asserts every live Territory either maps or is
listed as deliberately unmappable. Unmapped names travel in the payload rather
than being dropped.

## Backend

`upande_crm/api/territory.py`, in `analytics.py` house style: every query guarded
by `_has`/`_hascol`, degrading to empty rather than breaking the page. Money sums
`base_*` columns and carries `currency` — this site mixes USD/EUR/KES/GBP.

| Endpoint | Called | Returns |
|---|---|---|
| `crm_territory_map(date_from, date_to, customer)` | once, on mount | per-territory rollup: leads, opps, opp_value, prospects, customers, revenue; plus `groups` (the regional ledger) and `unmapped` |
| `crm_territory_detail(territory, date_from, date_to)` | on click only | top accounts, stage split, recent activity, 12-month sparkline |

Six grouped queries, one per source doctype — not one per territory. Splitting
detail out is what keeps **hover free of the network**: hovering reads data
already in memory.

Aggregates follow this app's established CRM-dashboard visibility model
(see `crm-broad-visibility-intended`): they count what exists, and are not
record-permission scoped.

## Frontend

```
sections/Territories/index.jsx   section shell, metric toggle, data fetch
  WorldMap.jsx                   SVG choropleth + centroid dots, hover/click/zoom
  IntelPanel.jsx                 dark slab; preview on hover, deep on pin
  RegionalLedger.jsx             the un-attributable accounting
lib/geo.js                       projection, zoom-to-feature, quantile bins
lib/territory_iso.js             name → ISO numeric, + micro-state centroids
assets/countries-110m.json       108KB, bundled
```

Lazy-loaded. `App.jsx` already uses `lazy()`/`Suspense`, so d3-geo and the atlas
form their own chunk and never load for anyone who does not open the map.

**One change to existing code:** `App.jsx` hardcodes a padded grid and a 44px
page header for every section. Edge-to-edge needs a `bleed: true` flag in
`SECTION_META` that drops both — extending the existing registry rather than
special-casing the shell.

Rendering is plain SVG `<path>` from `d3-geo`; zoom is an animated transform on a
group element. `d3-zoom` is not needed and not added.

## Look

The ink register of the existing palette, not a second design language: map
surface `--grad-ink`, choropleth in gold-weighted bins, intel panel a dark glass
slab with gold hairlines and Poppins tabular numerals. It survives a theme preset
change because it uses the same tokens everything else does.

Choropleth fills use **inline `rgba`, never Tailwind opacity modifiers** —
`bg-x/55` renders invisible against this app's CSS-var tokens (see
`tailwind-opacity-modifier-broken`).

## Interaction

- **Hover** — country lifts, intel panel previews from loaded data. No request.
- **Click** — zoom to the country's bounds, pin the panel, fetch detail.
- **Esc / ocean click** — release the pin, zoom back to world.
- **Metric toggle** — leads / opportunities / customers / revenue. Reshades from
  data already held; no refetch.

## Error handling

| Case | Behaviour |
|---|---|
| Doctype absent | that metric omitted, map still renders |
| Territory has no data | neutral fill, panel reads "no activity" — not an error |
| Territory unmapped to ISO | counted in the ledger, surfaced as "N unmapped" |
| Detail fetch fails | pinned panel keeps its preview figures, shows a quiet note |

## Testing

`upande_crm/tests/test_territory.py`:

- aggregation matches known counts (115 leads, 60 opps, 380 customers)
- every live Territory maps to ISO or is explicitly listed unmappable
- group territories land in the ledger, never on a country
- country totals + ledger totals reconcile to the ungrouped totals
- date-range filtering narrows results
- a missing doctype degrades instead of raising

## Out of scope

Deep-linking from the panel into filtered Leads/Opportunities lists; continent
level drill-down; editing a record's territory from the map.

---

# Addendum — 2026-09-10: claims, consignees, varieties, logistics, correspondence

A second pass widened the map beyond customers, and added two surfaces beside
it. As before, every decision below came from measuring the data first.

## What was asked for, and what the data supported

| Asked for | Found | Built |
|---|---|---|
| Customers | already mapped | — |
| Claims | `Customer Feedback` 3,378 rows, 3.6M stems, $572K | **yes** |
| Consignees | `Consignee` 1,231 rows with a `country` string | **yes** |
| Flowers selling best | `Sales Invoice Item` 62K rows over four flower Item Groups | **yes** |
| Sales person performance | `Sales Team` 28 rows, all one person; `sales_partner` empty on 13,780 invoices | **replaced** — see below |
| Issues faced | `Customer Feedback Item.reason_category` exists but is filled on 6 of 3,378 claims | **coverage stated, not charted** |
| Delivery points | 41 freight handlers, all at JKIA, no coordinates | **yes, as a schematic** |
| Harvest → dispatch → sales | chain broken at both ends | **middle only** |

## Attribution comes from email, not Sales Team

The field ERPNext provides for "who owns this account" is unusable here, so
`api/correspondence.py` derives it from who actually sends mail:

    Communication.recipients contains Contact Email.email_id   (outbound)
    Contact Email.parent -> Contact -> Dynamic Link -> Customer/Lead/Prospect

15,414 of 15,457 inbound emails match a Contact, and the outbound side yields
194 distinct (staff, party) pairs across 33 people. Automated Messages — 20,735
of 37,196 rows — are excluded, or the notification mailer would rank as the most
active salesperson in the company. Shared mailboxes (`purchasing@`, `info@`) are
counted but flagged, so nobody reads them as an individual's performance.

Surfaced three ways: a **Correspondence** section (staff x account matrix), a
gold **handled-by chip** on every inbox row (one batched lookup per page, not one
per row), and an **In contact** block in the map's pinned panel.

## The Nairobi hub is a schematic, and says so

`Sales Order.custom_delivery_point` is populated on 9,806 of 11,323 orders and
is the real link from handler to customer. But no handler carries a latitude,
an address, or anything else locational, and all of them operate at the same
airport — so a world map would stack them on one pixel.

They are drawn as a ring around JKIA instead. Disc size and distance from the
hub encode order volume; **the angle means nothing**, and the caption says so on
screen. Angular slots are sized by each label's width, because even spacing put
the two busiest handlers adjacent and merged their discs. Clicking one lists the
customers moving through it and, usefully, the destination territories — the one
join that reconnects origin logistics to the world map.

## The fulfilment chain, only where it is joined

    Harvest           19,566 rows — no order, no customer, no forward link
    Farm Pack List     8,612 / 8,614 carry a Sales Order   (100%)
    Order Pick List   13,807 / 13,807 carry a Sales Order  (100%)
    Dispatch Form          1 / 126 carries a Sales Order     (1%)

Only Ordered → Picked → Packed is drawn. Harvest and Dispatch are named as
`gaps` in the payload and printed under the chart. An empty "Dispatched" bar
would read as "no work happened" rather than "no data exists".

## Honesty carried forward

The regional ledger now also reports rows that reached no territory at all: 691
claims naming a company that is not a Customer, and 5 consignees in a country
with no Territory record. `mapped + regional + orphaned` reconciles to source
totals, and a test fails if it stops doing so.

Two data-quality facts the UI states rather than hides: **KES 300.6M of invoice
value carries no `item_code`** and is excluded from every varieties list, and the
consignee master is free text in which many "names" are addresses.

## Not built

Sales-person performance as a chartable dimension — one active person on 28
customers is not a comparison. Claim reasons as a breakdown, until the field is
filled. Anything joining harvest to an order, which the schema cannot express
today.
