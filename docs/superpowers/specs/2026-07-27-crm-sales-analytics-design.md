# CRM Sales Analytics — Design

**Date:** 2026-07-27
**Status:** Approved design
**Scope:** Spec 2 of 3. Siblings: Events & Tasks (spec 1, delivered), WhatsApp (spec 3).

## Problem

The CRM Overview leans on lead/opportunity counts and shows almost nothing about money,
despite the site holding 10,155 submitted Sales Orders (KES 638M) and 5,906 Sales Invoices
(KES 640M) for 2026 alone. Revenue appears as a single KPI and one daily order trend.

It also **misreports currency**. Every Company on the site has `default_currency: KES`, so
`base_grand_total` is denominated in KES — but `Overview.jsx` renders it as
`fmtMoneyCompact(k.revenue?.usd, 'USD')` and Top Customers as `${fmtMoney(r.usd)}`. A
KES 638M figure is displayed as **"$638M"**, roughly a 130× overstatement. The API field is
even named `usd`. This is the highest-severity item in this spec: a sales dashboard whose
money numbers are wrong in the customer's favour is worse than one with no money numbers.

## Goals

1. Fix the currency misstatement end to end (API field naming, resolution, formatting).
2. Add a sales analytics band to Overview covering booked vs billed revenue, average order
   value, receivables and their aging, rep performance, top products, and territory revenue.

### Non-goals — deliberately excluded because the data does not support them

| Excluded | Why |
|---|---|
| Value-weighted opportunity pipeline | All 23 open Opportunities have `opportunity_amount` = 0. The chart would be empty. |
| Quotation → Sales Order conversion | 4 Quotations exist site-wide (3 Expired, 1 Open). Meaningless as a rate. |
| Sales Order status mix | 10,153 of 10,155 are "To Deliver and Bill". A one-bar chart. |
| Revenue by customer group | 420M of 638M is "Unknown". Territory is the informative cut instead. |

Building these anyway would fill the dashboard with charts that look broken. They can be
revisited if the underlying data starts being captured.

## Currency handling

A new `_company_currency()` helper resolves the global default Company's `default_currency`,
falling back to `frappe.defaults.get_global_default("currency")` and finally `"KES"`.

`crm_dashboard_overview` gains a top-level `"currency"` key, and the revenue KPI's `usd`
field is **renamed to `amount`**. `_top_customers` likewise returns `amount` rather than `usd`.
The frontend formats with the returned currency code rather than a hardcoded `'USD'`.

Because `base_grand_total` is by definition already in company currency, no conversion is
performed — only correct labelling. Mixed transaction currencies (USD 8,108 / EUR 1,897 /
KES 328 / GBP 292 orders) are exactly why the `base_*` fields are the only summable ones.

## New endpoint

`upande_crm.api.analytics.crm_sales_analytics(date_from, date_to, customer=None)`

A separate module from `crm.py`, consistent with how `activity.py` was split out. This one is
a **read** layer, so it follows `crm.py`'s defensive-degradation house style: a missing
doctype or column yields zeros, never an exception.

Returns:

```python
{
  "currency": "KES",
  "kpis": {
    "booked": float,          # sum base_grand_total, submitted Sales Orders in range
    "booked_orders": int,
    "billed": float,          # sum base_grand_total, submitted Sales Invoices in range
    "billed_invoices": int,
    "aov": float,             # booked / booked_orders
    "outstanding": float,     # sum outstanding_amount, all submitted unpaid invoices
    "outstanding_count": int,
    "growth_pct": float,      # billed vs the immediately preceding equal-length window
  },
  "revenue_trend": [{"label": "YY-MM"|"MM-DD", "booked": float, "billed": float}],
  "rep_performance": [{"label": str, "amount": float, "orders": int}],
  "top_products":   [{"label": str, "amount": float, "qty": float}],
  "territory_revenue": [{"label": str, "amount": float}],
  "aging": [{"label": "Current"|"1-30"|"31-60"|"60+", "amount": float}],
}
```

Bucket granularity for `revenue_trend` follows the existing `_trend_in_range` convention:
daily for spans up to ~92 days, monthly beyond.

`growth_pct` compares billed revenue in the selected range against the immediately preceding
window of equal length. Returns 0 when the prior window is empty, rather than a misleading
infinite/100% figure.

Rep attribution uses `Sales Order.owner`. The site has a real spread across it
(antony.koskei 158M, cynthia.toroitich 149M, abiwott 128M …), whereas `Sales Team` /
`sales_person` is unpopulated. Falls back to an empty list if the column is absent.

## Frontend

`sections/Overview.jsx` is currently 133 lines and would roughly double. It gets split:

```
sections/Overview/index.jsx        pipeline KPIs, funnel, lead status, existing charts
sections/Overview/SalesBand.jsx    the new sales analytics band
components/MoneyKpi.jsx            currency-aware KPI (reuses KpiCard)
```

The sales band renders below the existing pipeline KPI row and above the funnel: a six-tile
money KPI row, a booked-vs-billed dual-series trend, a rep leaderboard, top products, a
territory bar chart, and an aging bar chart with overdue buckets in warning/bad tones.

Charts reuse the existing `Charts.jsx` primitives (`AreaTrendChart`, `BarsChart`,
`HBarsChart`) and the `PAL` palette. **No new npm dependency** — the `vite.config.js`
vendor-chunk hazard applies here as it did in spec 1.

Aging buckets are deliberately coloured by severity rather than by categorical palette:
Current in the neutral/good tone, 1-30 warn, 31-60 warn-darker, 60+ bad. On this site that
makes the 60+ bucket (KES 35.4M of 64.7M outstanding) read as the problem it is.

## Error handling

Read-layer semantics: every query is individually guarded and degrades to `0`/`[]`. A site
without `Sales Invoice` still renders the section with empty cards rather than failing the
whole Overview — matching how the other `crm_dashboard_*` readers behave.

Division guards: `aov` returns 0 when `booked_orders` is 0; `growth_pct` returns 0 when the
prior window is 0.

## Testing

Added to `upande_crm/tests/`, as `test_analytics.py`:

- `_company_currency()` returns the Company default (KES on this site), not a hardcoded USD.
- `crm_dashboard_overview` exposes `currency` and a revenue `amount` key, and no longer a
  `usd` key.
- `_top_customers` rows carry `amount`, not `usd`.
- `crm_sales_analytics` returns every documented key.
- `aov` is 0 rather than a ZeroDivisionError when no orders fall in range.
- `growth_pct` is 0 when the preceding window has no revenue.
- Aging buckets sum to total outstanding.
- A date range with no sales yields zeros and empty lists rather than raising.

## Verification

`bench --site kaitet.local run-tests --app upande_crm`, then `cd frontend && yarn build`, then
the Overview at `http://localhost:8002/customer-relationship-management` must show money
figures prefixed **KES**, not `$`.
