"""Tests for the purpose-built pipeline analytics.

Two properties matter, and the second is the lesson from the Reports section:

1. Each payload is shaped as documented and degrades rather than raising.
2. **No metric is charted over an unpopulated field.** A chart that renders a flat
   zero line is worse than no chart, because it reads as "the business is at zero"
   instead of "nobody fills this in". `test_no_list_is_empty_on_this_site` and the
   opportunity-amount tests exist to catch that class of mistake.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import pipeline as P

YEAR = {"date_from": "2026-01-01", "date_to": "2026-12-31"}
EMPTY = {"date_from": "1990-01-01", "date_to": "1990-01-31"}

TABS = (
    ("funnel", P.crm_analytics_funnel),
    ("leads", P.crm_analytics_leads),
    ("opps", P.crm_analytics_opportunities),
    ("revenue", P.crm_analytics_revenue),
)


class TestShape(FrappeTestCase):
    def test_every_tab_returns_kpis(self):
        for name, fn in TABS:
            self.assertIn("kpis", fn(**YEAR), name)

    def test_funnel_documents_its_stages_and_linkage(self):
        d = P.crm_analytics_funnel(**YEAR)
        self.assertEqual([s["key"] for s in d["stages"]], ["leads", "opportunities", "won"])
        for key in ("opp_from_lead", "quote_from_opp", "orders", "orders_from_quotation",
                    "chain_broken_after"):
            self.assertIn(key, d["linkage"])
        for key in ("lead_to_opportunity_days", "lead_to_customer_days", "samples"):
            self.assertIn(key, d["velocity"])

    def test_every_tab_survives_an_empty_range(self):
        for name, fn in TABS:
            d = fn(**EMPTY)
            self.assertIsInstance(d["kpis"], dict, name)

    def test_percentages_are_zero_not_errors_on_an_empty_range(self):
        d = P.crm_analytics_funnel(**EMPTY)
        self.assertEqual(d["kpis"]["leads"], 0)
        self.assertEqual(d["kpis"]["win_rate"], 0.0)
        self.assertEqual(d["kpis"]["lead_to_opp_rate"], 0.0)
        self.assertIsNone(d["velocity"]["lead_to_opportunity_days"])


class TestFunnelIsHonest(FrappeTestCase):
    def test_the_funnel_narrows_monotonically(self):
        # A funnel that widens is either wrong or measuring unrelated stages. The
        # quotation step is excluded for exactly this reason on this site.
        counts = [s["count"] for s in P.crm_analytics_funnel(**YEAR)["stages"]]
        self.assertEqual(counts, sorted(counts, reverse=True), counts)

    def test_it_is_a_cohort_not_independent_stage_counts(self):
        # Every opportunity counted must belong to a lead created in the range.
        d = P.crm_analytics_funnel(**YEAR)
        leads = frappe.get_all("Lead", filters={"creation": ["between", ["2026-01-01", "2026-12-31"]]},
                               pluck="name")
        expected = frappe.db.count("Opportunity", {"opportunity_from": "Lead",
                                                   "party_name": ["in", leads or [""]]})
        self.assertEqual(d["stages"][1]["count"], expected)

    def test_orders_are_not_counted_as_a_funnel_stage(self):
        # The bug this replaces: 10k orders appearing downstream of 69 leads.
        d = P.crm_analytics_funnel(**YEAR)
        labels = " ".join(s["label"].lower() for s in d["stages"])
        self.assertNotIn("order", labels)
        self.assertGreater(d["linkage"]["orders"], 0)

    def test_the_broken_chain_is_reported_when_orders_bypass_quotations(self):
        d = P.crm_analytics_funnel(**YEAR)
        if d["linkage"]["orders"] and not d["linkage"]["orders_from_quotation"]:
            self.assertEqual(d["linkage"]["chain_broken_after"], "Opportunity")

    def test_conversion_percentages_are_consistent_with_the_counts(self):
        stages = P.crm_analytics_funnel(**YEAR)["stages"]
        first = stages[0]["count"]
        for i, s in enumerate(stages[1:], start=1):
            prev = stages[i - 1]["count"]
            self.assertAlmostEqual(s["of_previous"],
                                   round(s["count"] / prev * 100, 1) if prev else 0.0, places=1)
            self.assertAlmostEqual(s["of_first"],
                                   round(s["count"] / first * 100, 1) if first else 0.0, places=1)


class TestNothingIsChartedOverEmptyData(FrappeTestCase):
    def test_no_list_is_empty_on_this_site(self):
        # Every list in every payload backs a chart. An empty one means a blank
        # panel — the failure mode the Reports section shipped with.
        empty = []
        for name, fn in TABS:
            for key, value in fn(**YEAR).items():
                if isinstance(value, list) and not value:
                    empty.append(f"{name}.{key}")
        self.assertEqual(empty, [], f"these would render as blank charts: {empty}")

    def test_lead_sources_carry_both_volume_and_conversion(self):
        rows = P.crm_analytics_leads(**YEAR)["by_source"]
        self.assertTrue(rows)
        for r in rows:
            for key in ("label", "leads", "converted", "rate"):
                self.assertIn(key, r)
            self.assertLessEqual(r["converted"], r["leads"])

    def test_opportunity_value_is_flagged_as_unrecorded_not_charted_as_zero(self):
        # opportunity_amount is 0 on every row on this site. The payload must say so
        # via amounts_recorded, so the UI can explain rather than draw a flat line.
        k = P.crm_analytics_opportunities(**YEAR)["kpis"]
        self.assertIn("amounts_recorded", k)
        if not k["amounts_recorded"]:
            self.assertEqual(k["gross_value"], 0.0)
        # Probability IS recorded, so it must be a real number.
        self.assertGreater(k["avg_probability"], 0)

    def test_stage_rows_carry_probability_rather_than_only_value(self):
        for row in P.crm_analytics_opportunities(**YEAR)["by_stage"]:
            self.assertIn("avg_probability", row)
            self.assertIn("count", row)

    def test_revenue_money_metrics_are_non_zero_on_this_site(self):
        # Quotation and order totals ARE populated, unlike opportunity amounts.
        k = P.crm_analytics_revenue(**YEAR)["kpis"]
        self.assertGreater(k["booked"], 0)
        self.assertGreater(k["orders"], 0)
        self.assertGreater(k["quotation_value"], 0)

    def test_fulfilment_percentages_are_in_range(self):
        f = P.crm_analytics_revenue(**YEAR)["fulfilment"]
        for key in ("avg_delivered_pct", "avg_billed_pct"):
            self.assertGreaterEqual(f[key], 0)
            self.assertLessEqual(f[key], 100)

    def test_fulfilment_reports_whether_it_is_recorded_at_all(self):
        # per_delivered/per_billed are zero on every order on this site. Without
        # `recorded` the UI would draw two 0% meters, which reads as a delivery
        # crisis rather than as a field nobody updates.
        f = P.crm_analytics_revenue(**YEAR)["fulfilment"]
        self.assertIn("recorded", f)
        if not f["recorded"]:
            self.assertEqual(f["avg_delivered_pct"], 0)
            self.assertEqual(f["avg_billed_pct"], 0)
            # and the fallback content must be there to fill the space
            self.assertTrue(P.crm_analytics_revenue(**YEAR)["top_customers"])

    def test_top_customers_carry_real_money(self):
        rows = P.crm_analytics_revenue(**YEAR)["top_customers"]
        self.assertTrue(rows)
        self.assertGreater(rows[0]["value"], 0)
        # ordered by value, descending
        values = [r["value"] for r in rows]
        self.assertEqual(values, sorted(values, reverse=True))


class TestCustomerScoping(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        rows = frappe.db.sql("""select customer, count(*) n from `tabSales Order`
                                where docstatus=1 group by customer order by n desc limit 1""",
                             as_dict=True)
        cls.customer = rows[0].customer if rows else None

    def test_revenue_narrows_to_the_customer(self):
        if not self.customer:
            self.skipTest("no billing customer")
        wide = P.crm_analytics_revenue(**YEAR)["kpis"]
        narrow = P.crm_analytics_revenue(**YEAR, customer=self.customer)["kpis"]
        self.assertLess(narrow["orders"], wide["orders"])
        self.assertGreater(narrow["orders"], 0)

    def test_an_unrelated_customer_yields_nothing_rather_than_everything(self):
        d = P.crm_analytics_funnel(**YEAR, customer="no-such-customer-zzz")
        self.assertEqual(d["kpis"]["leads"], 0)
        r = P.crm_analytics_revenue(**YEAR, customer="no-such-customer-zzz")
        self.assertEqual(r["kpis"]["orders"], 0)


class TestGuard(FrappeTestCase):
    def tearDown(self):
        frappe.set_user("Administrator")

    def test_guest_is_refused_on_every_tab(self):
        frappe.set_user("Guest")
        for name, fn in TABS:
            with self.assertRaises(frappe.PermissionError, msg=name):
                fn(**YEAR)
