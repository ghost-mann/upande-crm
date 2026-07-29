# Sales Analytics section — Design

**Date:** 2026-07-29
**Status:** Built. Written alongside the code after the Reports section under-delivered.
**Scope:** Spec 8. Supersedes the Reports section as the CRM's analytics story; Reports
(spec 6) remains as the catalogue and viewer for ERPNext's raw reports.

## Why this exists: the Reports section was the wrong answer

The ask was "the default CRM reports, but visually better". Reports (spec 6) delivered a
faithful viewer of ERPNext's own reports, and James's verdict was blunt and correct: *the
reports suck*.

The evidence was in my own verification screenshots and I did not read it as failure:

- **Pipeline by sales stage** rendered a chart of all-zero bars over a table that was nine
  columns of `—` with a single `1` in it.
- **Item-wise sales history** dumped nineteen raw ERPNext columns, truncated at 500 of 39,232.
- **Not one** of the 23 registered reports returns a `report_summary`, so the KPI-tile code
  written for them never renders.
- Most return zero rows over a 30-day window, so the default view is largely blank.

The mistake was verifying that reports **ran** rather than that they had anything to **show**.
Re-skinning a nineteen-column grid is not analytics. The part of this app that already worked
— the Overview sales band, with its pace markers and derived rates — works because it is
purpose-built, not because it renders someone else's columns.

## The rule this section is built on

**Measure field population before charting anything.** Every metric here was checked against
real values first, and three would have shipped as permanently-zero panels:

| Field | Naive check said | Truth |
|---|---|---|
| `Opportunity.opportunity_amount` | 100% populated | **0 on all 59** — max is 0 |
| `Sales Order.per_delivered` / `per_billed` | 100% populated | **0 on all 10,625** |
| `Lead.industry`, `request_type` | 0% | 0% (correctly excluded) |

The naive check was `coalesce(col,'') not in ('','0')`, which reports a numeric column as
populated when every value is `0.000000`. Corrected by comparing numerically.

Where a metric cannot be computed, the section **says so and explains why**, rather than
drawing a flat line: two 0% fulfilment meters read as a delivery crisis, not as a field nobody
updates. Those slots are given to figures that do mean something.

`tests/test_pipeline.py::test_no_list_is_empty_on_this_site` walks every list in every payload
and fails if any is empty. That test is the guard against repeating the Reports mistake.

## The funnel, and where the data stops

Counting each stage independently — what the Overview funnel does — produces nonsense when the
stages are not linked. It reports 4 leads and 1,429 orders in one funnel, as though orders were
300x the leads that produced them.

The document chain, measured:

| Link | Rows |
|---|---|
| Lead → Opportunity | **45** — usable |
| Opportunity → Quotation | 3 — too thin to rate |
| Quotation → Sales Order | **0** — chain not used |
| Submitted orders | 10,625 |

Orders are raised directly, never from quotations. So:

- The funnel is **cohort-based**: it takes the leads created in the range and follows *those*
  leads forward. Stages are Lead → Became an opportunity → Won, and it narrows monotonically
  (a test asserts this).
- **Quotations are not a stage.** 3 of 30 opportunities have one while 20 were won, so
  inserting it would draw a funnel that narrows to 3 then widens back to 20 — visibly wrong,
  and wrong about the process.
- The order book gets its own panel, *Where the document chain stops*, naming the gap: 0 of
  10,155 orders came from a quotation. Reporting "0% quote-to-order conversion" as a
  performance number would be a lie about a process fact.

## Tabs

**Funnel** — cohort stages, conversion at each step, velocity (median days lead→opportunity
and lead→customer, with sample sizes shown), and the chain-linkage panel.

**Leads** — conversion *by source*, which is the tab's point: Exhibition converts at 50% and
Website at 17%, so volume and quality are visibly different things. Plus qualification mix,
open-lead ageing, territory, segment and owner.

**Opportunities** — stage distribution with each stage's average recorded probability, open
ageing, per-owner volume against win rate, and status/type/source/territory. Value is absent
and a panel explains that `opportunity_amount` is unrecorded on all of them, noting that
filling it in would make weighted pipeline value available with no further work.

**Quotes & revenue** — quotation value (real: 21.4M), order value distribution in bands
(7,222 orders under 50k worth 108.5M against 49 orders over 1M worth 102.8M — the
concentration is the insight), top customers by value, customers-per-month with new-buyer
approximation, and the status mixes.

## Range picker

Analytics needs wider windows than the dashboards — a funnel over 30 days on this pipeline is
single digits. Rather than a hidden per-section default, a segmented picker sits at the top of
the section with 7d / 30d / 60d / 90d / 6m / YTD / 12m / All time. It is bound to the same
store range as the header pill, so the two never disagree, and the longer presets are added to
the shared vocabulary so every section and the settings default gain them.

## Backend

`upande_crm/api/pipeline.py`, one endpoint per tab so a tab nobody opened costs nothing:
`crm_analytics_funnel`, `_leads`, `_opportunities`, `_revenue`. A read layer — every query
individually guarded, degrading to empty. Customer filtering reuses `api/scope.py`, so "this
customer's funnel" means the same thing here as everywhere else.

## Testing

`tests/test_pipeline.py` (20 tests). Beyond shape and guard coverage:

- the funnel narrows monotonically;
- stage 2 equals a direct count of opportunities belonging to leads created in range, proving
  it is a cohort and not independent counts;
- no stage label mentions orders, and the linkage panel still reports them;
- **no list in any payload is empty on this site**;
- opportunity value is flagged as unrecorded rather than charted as zero, while probability is
  asserted non-zero;
- fulfilment reports `recorded`, and when it is zero the replacement content is present;
- revenue money metrics are asserted non-zero, since those fields *are* real.

## Verification

189+ suite green, and each tab driven in a headless browser at YTD with no console errors and
no empty panels.
