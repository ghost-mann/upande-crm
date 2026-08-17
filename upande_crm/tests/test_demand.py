"""Tests for the flowers-in-demand reader.

The card is thin by nature — it reads item lines that reps have to enter, and on
most sites almost nobody has. So the tests assert *shape and honesty* rather than
volume: the payload must always report its own sample size, the per-variety
figures must add up to the totals, and a site with no Opportunity Item at all must
get an empty card rather than an error.

One regression is pinned deliberately. `lines` is a reserved word in MariaDB, and
aliasing the line tally with it made both queries fail silently — the card then
reported "no demand" on a site that had some. A failure that looks like an answer
is the worst kind here, so the queries are asserted to actually run.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import demand

WIDE = {"date_from": "2000-01-01", "date_to": "2099-12-31"}
EMPTY = {"date_from": "1990-01-01", "date_to": "1990-01-02"}
KEYS = ("currency", "range", "rows", "totals", "sources")


class TestShape(FrappeTestCase):
    def test_returns_every_key_the_card_reads(self):
        d = demand.crm_demand(**WIDE)
        for key in KEYS:
            self.assertIn(key, d)

    def test_rows_are_bounded(self):
        self.assertLessEqual(len(demand.crm_demand(**WIDE)["rows"]), demand.DEMAND_LIMIT)

    def test_each_row_bounds_its_client_list(self):
        for r in demand.crm_demand(**WIDE)["rows"]:
            self.assertLessEqual(len(r["top_clients"]), demand.CLIENT_LIMIT)
            self.assertLessEqual(len(r["top_clients"]), r["clients"])

    def test_rows_are_ranked_by_stems(self):
        qtys = [r["qty"] for r in demand.crm_demand(**WIDE)["rows"]]
        self.assertEqual(qtys, sorted(qtys, reverse=True))

    def test_an_empty_window_is_an_empty_card_not_an_error(self):
        d = demand.crm_demand(**EMPTY)
        self.assertEqual(d["rows"], [])
        self.assertEqual(d["totals"]["varieties"], 0)
        self.assertEqual(d["sources"]["opportunity_lines"], 0)


class TestArithmetic(FrappeTestCase):
    def test_a_rows_sources_sum_to_its_total(self):
        for r in demand.crm_demand(**WIDE)["rows"]:
            self.assertAlmostEqual(
                r["from_opportunities"] + r["from_quotations"], r["qty"], places=6,
                msg=f"{r['key']}: the two sources do not add up to the stems shown",
            )

    def test_client_stems_never_exceed_the_variety_total(self):
        for r in demand.crm_demand(**WIDE)["rows"]:
            self.assertLessEqual(sum(c["qty"] for c in r["top_clients"]) - r["qty"], 1e-6)

    def test_totals_cover_at_least_the_rows_shown(self):
        # `rows` is the top N; the totals count every variety found.
        d = demand.crm_demand(**WIDE)
        self.assertGreaterEqual(d["totals"]["varieties"], len(d["rows"]))
        self.assertGreaterEqual(d["totals"]["qty"] + 1e-6, sum(r["qty"] for r in d["rows"]))


class TestQueriesActuallyRun(FrappeTestCase):
    """`lines` is reserved in MariaDB. Aliasing on it failed silently and the card
    reported no demand on a site that had some — pinned so it cannot come back."""

    def test_the_opportunity_query_executes(self):
        rows = demand._opportunity_lines("2000-01-01", "2099-12-31")
        self.assertIsInstance(rows, list)
        for r in rows:
            self.assertIn("line_count", r)

    def test_the_quotation_query_executes(self):
        rows = demand._quotation_lines("2000-01-01", "2099-12-31")
        self.assertIsInstance(rows, list)
        for r in rows:
            self.assertIn("line_count", r)

    def test_the_reported_sample_size_matches_the_rows_read(self):
        d = demand.crm_demand(**WIDE)
        opp = sum(int(r["line_count"]) for r in demand._opportunity_lines("2000-01-01", "2099-12-31"))
        self.assertEqual(d["sources"]["opportunity_lines"], opp)

    def test_a_site_with_demand_reports_some(self):
        # Guards the silent-failure mode directly: if the underlying tables hold
        # open lines, the card must not come back empty.
        has_lines = frappe.db.count("Opportunity Item") or frappe.db.count("Quotation Item")
        if not has_lines:
            self.skipTest("no opportunity or quotation lines on this site")
        d = demand.crm_demand(**WIDE)
        self.assertGreater(d["sources"]["opportunity_lines"] + d["sources"]["quotation_lines"], 0)


class TestDegradation(FrappeTestCase):
    def test_a_missing_doctype_yields_an_empty_card(self):
        real = demand._has
        try:
            demand._has = lambda dt: False
            d = demand.crm_demand(**WIDE)
            self.assertEqual(d["rows"], [])
            self.assertEqual(d["sources"]["opportunity_lines"], 0)
        finally:
            demand._has = real

    def test_a_customer_filter_narrows_rather_than_raising(self):
        customer = frappe.get_all("Customer", pluck="name", limit=1)
        if not customer:
            self.skipTest("no customers on this site")
        scoped = demand.crm_demand(**WIDE, customer=customer[0])
        everything = demand.crm_demand(**WIDE)
        self.assertLessEqual(scoped["totals"]["varieties"], everything["totals"]["varieties"])
