# CRM Reports — Design

**Date:** 2026-07-29
**Status:** Approved shape, one change forced by measurement (see "The filter problem")
**Scope:** Spec 6. Siblings: Events & Tasks (1), Sales analytics (2), WhatsApp (3), CRM Settings
(4), Theming (5) — all delivered. Calls (7) follows.

## Problem

ERPNext already ships the CRM's analytical reports, and this site has **35 of them** across the
CRM and Selling modules — Sales Pipeline Analytics, Lead Owner Efficiency, Lost Opportunity,
Customer Acquisition and Loyalty, Inactive Customers, Territory-wise Sales, and so on, plus
three written for this site (CRM Conversion, Sales Order Report, Sales per Variety Report).

None of them is reachable from the CRM. A sales manager who wants "which leads converted and how
long it took" has to leave for the desk, find the report by name, work out its filters, and read
a dense grid. Meanwhile the CRM has KPI cards, charts and a table component that would render
the same data far better.

The reports themselves are not the problem and should not be reimplemented — duplicating their
logic in `api/` would guarantee the two drift. `frappe.desk.query_report.run` executes any report
type and returns columns plus rows, so the CRM can present ERPNext's own output.

## Goals

1. A **Reports section** in the sidebar with its own icon.
2. Four curated tabs — **Pipeline, Leads, Customers, Sales** — where each report gets a real
   presentation: KPI tiles where the report exposes a summary, its chart where it declares one,
   and a proper CRM table.
3. A **catalogue** tab listing every other report the user may run, so nothing is hidden.
4. Reports run with **the user's own permissions**, unlike the dashboards.

### Non-goals

Writing new report logic, editing or creating reports (that stays in desk), Prepared Report
queueing, CSV/Excel export (desk does it), and charting reports that declare no chart.

## The filter problem — measured, and it changes the design

The approved shape was "curated tabs plus a catalogue that runs everything else". Measurement
says the second half cannot work as stated.

Every one of the 35 reports was executed on this site, bare and then with a set of common filter
defaults:

| | count |
|---|---|
| Runs with **no filters at all** | 13 |
| Runs once given common filters (company, from/to, …) | 11 |
| **Still fails** — needs a specific filter value | 11 |

The failures are not subtle: `Sales Analytics` → `AttributeError: 'NoneType' has no attribute
'startswith'`, `Quotation Trends` → *Based On is mandatory*, `Sales Person-wise Transaction
Summary` → *Please select the document type first*, `Inactive Customers` → *'Days Since Last
Order' must be greater than or equal to zero*.

The cause: **a Script Report's filters are declared in its client-side `.js`, not on the Report
doctype.** `frappe.get_doc("Report", name).filters` is empty for all 35. The server cannot
introspect them, so "run any report generically" means "show a Python traceback for a third of
them".

**Decision.** A per-report **registry** in Python declares the filters each report needs, their
defaults, and which of them the CRM lets the user change. The registry is the curated set. The
catalogue then:

- runs a report when the registry knows it, or when it needs no filters at all;
- otherwise lists it with what it needs and a **deep link to the desk report view**, rather than
  running it into a traceback.

That keeps "nothing hidden" honest without pretending to filter vocabularies we have not
verified. Adding a report to the rich set is a registry entry, reviewed in git — which is
appropriate, since each needs its filters checked against a real run anyway.

Two more traps the measurement exposed, both recorded in the registry:

- The filter is `doc_type` in `Sales Analytics` and `Sales Person-wise Transaction Summary`, but
  `doctype` in `Inactive Customers`. Guessing one name for both fails.
- The two site-custom Query Reports (`Sales Order Report`, `Sales per Variety Report (SO)`)
  declare no filters yet reference `%(from_date)s` in their SQL, so they fail with
  `KeyError: b'from_date'` unless dates are passed anyway.

## Backend — `upande_crm/api/reports.py`

A read layer, so it follows `api/crm.py`'s house style: a broken report degrades to an error
message attached to that one report, never a failed section.

**Permissions are the deliberate exception to this app's house rule.** Every other endpoint
role-gates and then reads with `ignore_permissions=True`, because the dashboards are a shared
command centre (recorded as intended). Reports are different: `Customer Credit Balance` and
`Sales Person Commission Summary` are financial, and the report runner already enforces Report
permissions plus the referenced doctype's. So `crm_report_run` calls
`frappe.desk.query_report.run` **without** widening, and a user who may not read a report gets a
clean refusal. `_guard()` still gates the endpoints themselves.

| Endpoint | Returns |
|---|---|
| `crm_reports()` | the registry: groups, each report's label, description, filter spec, and whether it is runnable here |
| `crm_report_run(report, filters)` | `{columns, rows, chart, summary, execution_time}` — or `{error}` for that report alone |
| `crm_report_catalogue()` | every Report the user may see, with `runnable`, its group, and a desk URL |

`crm_report_run` validates the report name against the registry **or** the set of reports the
user can actually see, so the endpoint cannot be turned into a runner for arbitrary server
scripts. Filters are merged over the registry's defaults, and only keys the registry declares
are accepted from the client — a client cannot inject an arbitrary filter into someone else's
SQL.

### Registry shape

```python
REPORTS = (
  Report(
    key="pipeline_by_stage",
    report="Opportunity Summary by Sales Stage",
    group="pipeline",
    label="Pipeline by sales stage",
    blurb="Open opportunity value at each stage.",
    filters={"company": COMPANY, "from_date": RANGE_FROM, "to_date": RANGE_TO},
    editable=("company",),
  ),
  ...
)
```

`COMPANY`, `RANGE_FROM`, `RANGE_TO` are sentinels resolved per request from the default company
and the header's date range, so the section obeys the same date pill as the rest of the CRM.

## Frontend

```
sections/Reports/index.jsx      tab router on `table`
  Group.jsx                     one curated group: report cards, each expandable
  ReportView.jsx                one report: summary tiles, chart, table
  Catalogue.jsx                 everything else, with desk links
  columns.js                    Frappe column types -> CRM cell renderers
```

Nav gains a **Reports** group, icon `lab_profile`, with tabs Pipeline / Leads / Customers /
Sales / All reports.

Each curated report renders collapsed as a card with its label, blurb and row count, and expands
to the full result: `report_summary` becomes KPI tiles, a declared `chart` becomes a CRM chart,
and the rows become a `DataTable` with types mapped by `columns.js` (Currency via `fmtMoney` in
the company currency, Date via `fmtDate`, Link as a desk link, Percent, Int, Float, Duration).
Reports load **on expand, not on tab open** — `Sales Analytics` over 11k orders is not something
to fire five of in parallel.

The date pill and the customer filter both apply where a report declares the matching filter,
and the card says so; where it does not, the card says the report is not date-scoped rather than
implying it is.

## Testing

`upande_crm/tests/test_reports.py`:

- **Every registry entry actually runs on this site.** The registry is the promise; this test is
  what keeps it true, and is the reason the registry exists rather than a guess.
- Registry keys are unique, every `group` is a real tab, and every `editable` filter is one the
  entry declares.
- `crm_report_run` refuses a report outside the registry that the user cannot otherwise see.
- Undeclared filter keys sent by a client are dropped, not forwarded.
- A report that throws returns `{error}` rather than propagating.
- Sentinels resolve: `RANGE_FROM`/`RANGE_TO` reach the report as the requested dates.
- `crm_report_catalogue()` covers all 35 CRM/Selling reports and marks the 11 unrunnable ones
  `runnable: False` with a desk URL.
- `_guard` rejects Guest; a report the user lacks permission for is refused rather than widened.

## Verification

`bench --site kaitet.local run-tests --app upande_crm`, `cd frontend && npm run build`, then
Reports → Pipeline should render Opportunity Summary by Sales Stage with real stage values, and
the catalogue should show `Sales Analytics` as needing desk filters rather than erroring.
