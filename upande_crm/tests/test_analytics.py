"""Tests for CRM sales analytics and the company-currency contract.

The currency assertions exist because the dashboard previously rendered
`base_grand_total` (company currency, KES on this site) with a hardcoded '$',
overstating revenue by roughly 130x. These lock that fix in.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import analytics
from upande_crm.api.crm import _company_currency, _top_customers, crm_dashboard_overview

ALL_KEYS = (
    "currency", "kpis", "revenue_trend", "rep_performance",
    "top_products", "territory_revenue", "aging",
)
KPI_KEYS = (
    "booked", "booked_orders", "billed", "billed_invoices",
    "aov", "outstanding", "outstanding_count", "growth_pct",
)


class TestCompanyCurrency(FrappeTestCase):
    def test_resolves_company_default_currency(self):
        ccy = analytics._company_currency()
        self.assertTrue(ccy)
        company = frappe.defaults.get_global_default("company")
        if company:
            expected = frappe.db.get_value("Company", company, "default_currency")
            if expected:
                self.assertEqual(ccy, expected)

    def test_crm_py_and_analytics_agree(self):
        self.assertEqual(_company_currency(), analytics._company_currency())

    def test_is_not_hardcoded_usd_on_this_site(self):
        # Every Company on this site defaults to KES; a 'USD' answer would mean
        # the hardcoded-dollar bug had returned.
        company = frappe.defaults.get_global_default("company")
        if not company:
            self.skipTest("no default company")
        self.assertEqual(analytics._company_currency(), "KES")


class TestOverviewCurrencyContract(FrappeTestCase):
    def test_overview_exposes_currency(self):
        d = crm_dashboard_overview(date_from="2026-01-01", date_to="2026-12-31")
        self.assertIn("currency", d)
        self.assertTrue(d["currency"])

    def test_revenue_kpi_uses_amount_not_usd(self):
        d = crm_dashboard_overview(date_from="2026-01-01", date_to="2026-12-31")
        rev = d["kpis"]["revenue"]
        self.assertIn("amount", rev)
        self.assertNotIn("usd", rev)

    def test_top_customers_rows_use_amount(self):
        rows = _top_customers("2026-01-01", "2026-12-31", limit=3)
        for r in rows:
            self.assertIn("amount", r)
            self.assertNotIn("usd", r)


class TestSalesAnalytics(FrappeTestCase):
    def test_returns_all_documented_keys(self):
        d = analytics.crm_sales_analytics(date_from="2026-01-01", date_to="2026-12-31")
        for k in ALL_KEYS:
            self.assertIn(k, d)
        for k in KPI_KEYS:
            self.assertIn(k, d["kpis"])

    def test_real_revenue_is_reported(self):
        d = analytics.crm_sales_analytics(date_from="2026-01-01", date_to="2026-12-31")
        # The site holds >10k submitted 2026 Sales Orders; a zero here would mean
        # the query silently degraded.
        self.assertGreater(d["kpis"]["booked"], 0)
        self.assertGreater(d["kpis"]["booked_orders"], 0)

    def test_aov_is_zero_not_error_for_empty_range(self):
        d = analytics.crm_sales_analytics(date_from="1990-01-01", date_to="1990-01-31")
        self.assertEqual(d["kpis"]["aov"], 0.0)
        self.assertEqual(d["kpis"]["booked"], 0.0)

    def test_growth_is_zero_when_prior_window_empty(self):
        d = analytics.crm_sales_analytics(date_from="1990-01-01", date_to="1990-01-31")
        self.assertEqual(d["kpis"]["growth_pct"], 0.0)

    def test_empty_range_yields_empty_lists(self):
        d = analytics.crm_sales_analytics(date_from="1990-01-01", date_to="1990-01-31")
        self.assertEqual(d["revenue_trend"], [])
        self.assertEqual(d["rep_performance"], [])
        self.assertEqual(d["top_products"], [])

    def test_aging_has_four_buckets_summing_to_outstanding(self):
        d = analytics.crm_sales_analytics(date_from="2026-01-01", date_to="2026-12-31")
        aging = d["aging"]
        self.assertEqual([r["label"] for r in aging], list(analytics.AGING_LABELS))
        total = sum(r["amount"] for r in aging)
        self.assertAlmostEqual(total, d["kpis"]["outstanding"], places=2)

    def test_aging_is_not_range_scoped(self):
        # What is owed is owed regardless of the dashboard window.
        wide = analytics.crm_sales_analytics(date_from="2026-01-01", date_to="2026-12-31")
        narrow = analytics.crm_sales_analytics(date_from="1990-01-01", date_to="1990-01-31")
        self.assertEqual(wide["kpis"]["outstanding"], narrow["kpis"]["outstanding"])

    def test_revenue_trend_rows_carry_both_series(self):
        d = analytics.crm_sales_analytics(date_from="2026-01-01", date_to="2026-12-31")
        self.assertTrue(d["revenue_trend"])
        for row in d["revenue_trend"][:3]:
            self.assertIn("label", row)
            self.assertIn("booked", row)
            self.assertIn("billed", row)

    def test_rep_performance_shape(self):
        d = analytics.crm_sales_analytics(date_from="2026-01-01", date_to="2026-12-31")
        for row in d["rep_performance"][:3]:
            self.assertIn("label", row)
            self.assertIn("amount", row)
            self.assertIn("orders", row)
            self.assertNotIn("@", row["label"])  # emails are shortened

    def test_guard_rejects_user_without_crm_role(self):
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.PermissionError):
                analytics.crm_sales_analytics()
        finally:
            frappe.set_user("Administrator")
