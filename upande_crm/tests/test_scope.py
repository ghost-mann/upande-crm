"""Tests for the customer filter.

The bug being locked out: eight endpoints accepted a `customer` argument and four
ignored it, while `crm_dashboard_overview` honoured it for revenue alone. So the
header pill narrowed one number and left the funnel, the lead counts, the tasks
and the entire sales band global.

Every test here therefore asserts *narrowing actually happened* — filtered <=
unfiltered, and equal to what a direct query says. A test that only checked the
response shape would have passed against the broken version.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import scope as SC
from upande_crm.api.analytics import crm_sales_analytics
from upande_crm.api.crm import (
    crm_dashboard_customers,
    crm_dashboard_events_tasks,
    crm_dashboard_leads,
    crm_dashboard_opportunities,
    crm_dashboard_overview,
    crm_dashboard_prospects,
)

WIDE = {"date_from": "2000-01-01", "date_to": "2099-12-31"}

# Endpoints that must all narrow. Kept as one list so a new dashboard reader
# cannot quietly join the set that ignores the filter.
READERS = (
    crm_dashboard_overview,
    crm_dashboard_leads,
    crm_dashboard_opportunities,
    crm_dashboard_prospects,
    crm_dashboard_customers,
    crm_dashboard_events_tasks,
    crm_sales_analytics,
)


def _converted_customer():
    """A customer that was actually converted from a lead, so the chain has
    something to walk. Skips rather than inventing fixtures — the point is to test
    against this site's real linkage."""
    rows = frappe.get_all(
        "Customer", filters={"lead_name": ["!=", ""]},
        fields=["name", "lead_name"], limit=1,
    )
    return rows[0] if rows else None


def _billing_customer():
    rows = frappe.db.sql(
        """select customer, count(*) n from `tabSales Order`
           where docstatus=1 group by customer order by n desc limit 1""",
        as_dict=True,
    )
    return rows[0].customer if rows else None


class TestScopeResolution(FrappeTestCase):
    def test_no_customer_yields_an_entirely_empty_scope(self):
        for empty in (None, ""):
            s = SC.customer_scope(empty)
            for doctype in ("Customer",) + SC.SCOPE_DOCTYPES:
                self.assertEqual(s[doctype], [], f"{doctype} for {empty!r}")

    def test_scope_always_contains_the_customer_itself(self):
        s = SC.customer_scope("EFLOWERS B.V.")
        self.assertEqual(s["Customer"], ["EFLOWERS B.V."])

    def test_scope_has_a_key_per_scoped_doctype(self):
        s = SC.customer_scope("EFLOWERS B.V.")
        for doctype in ("Customer",) + SC.SCOPE_DOCTYPES:
            self.assertIn(doctype, s)
            self.assertIsInstance(s[doctype], list)

    def test_unknown_customer_resolves_to_nothing_rather_than_raising(self):
        s = SC.customer_scope("no-such-customer-zzz")
        for doctype in SC.SCOPE_DOCTYPES:
            self.assertEqual(s[doctype], [], doctype)

    def test_converted_customer_pulls_in_its_originating_lead(self):
        row = _converted_customer()
        if not row:
            self.skipTest("no customer on this site carries lead_name")
        s = SC.customer_scope(row.name)
        self.assertIn(row.lead_name, s["Lead"])

    def test_the_chain_reaches_opportunities_raised_against_the_lead(self):
        # 45 of this site's opportunities came in as a Lead and only 6 directly
        # against a Customer, so a filter that matched party_name = customer
        # missed nearly all of them.
        row = _converted_customer()
        if not row:
            self.skipTest("no converted customer")
        s = SC.customer_scope(row.name)
        expected = frappe.get_all(
            "Opportunity",
            filters={"opportunity_from": "Lead", "party_name": ["in", s["Lead"] or [""]]},
            pluck="name",
        )
        for name in expected:
            self.assertIn(name, s["Opportunity"])

    def test_in_scope_matches_nothing_when_the_scope_is_empty(self):
        # The whole point: an empty scope must NOT widen back to every record.
        s = SC.customer_scope("no-such-customer-zzz")
        self.assertEqual(SC.in_scope(s, "Lead"), {"name": ["in", [""]]})

    def test_in_scope_returns_the_names_when_present(self):
        s = {"Lead": ["A", "B"]}
        self.assertEqual(SC.in_scope(s, "Lead"), {"name": ["in", ["A", "B"]]})

    def test_scope_sql_is_escaped_not_interpolated(self):
        sql = SC.scope_sql({"Lead": ["O'Brien Ltd"]}, "Lead")
        # The bare name must never appear: it has to arrive escaped by the driver.
        self.assertNotIn("'O'Brien Ltd'", sql)
        self.assertEqual(sql, f"`name` in ({frappe.db.escape(chr(79) + chr(39) + 'Brien Ltd')})")

    def test_scope_sql_survives_an_injection_attempt(self):
        sql = SC.scope_sql({"Lead": ["x'); drop table `tabLead`; --"]}, "Lead")
        # The payload stays inside one string literal: its quote and backticks
        # come back escaped, so it can never close the IN list and start a new
        # statement. Asserted on the raw SQL — stripping the backslashes first
        # would undo the very escaping under test.
        self.assertNotIn("x');", sql)
        self.assertIn("x\\');", sql)
        self.assertIn("\\`tabLead\\`", sql)

    def test_scope_sql_never_matches_on_an_empty_scope(self):
        self.assertEqual(SC.scope_sql({"Lead": []}, "Lead"), "1=0")

    def test_scope_pairs_flattens_to_doctype_name_tuples(self):
        pairs = SC.scope_pairs({"Customer": ["C"], "Lead": ["L1", "L2"]})
        self.assertIn(("Customer", "C"), pairs)
        self.assertIn(("Lead", "L1"), pairs)


class TestEveryReaderNarrows(FrappeTestCase):
    """The regression net: no reader may ignore the filter."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = _billing_customer()

    def setUp(self):
        if not self.customer:
            self.skipTest("no billing customer on this site")

    def test_no_reader_returns_identical_results_filtered_and_unfiltered(self):
        # If a reader ignores `customer`, its two payloads are byte-identical.
        # Targets are excluded: they are company-wide on purpose.
        unchanged = []
        for reader in READERS:
            wide = reader(**WIDE)
            narrow = reader(**WIDE, customer=self.customer)
            if isinstance(wide, dict):
                wide = {k: v for k, v in wide.items() if k != "targets"}
                narrow = {k: v for k, v in narrow.items() if k != "targets"}
            if wide == narrow:
                unchanged.append(reader.__name__)
        self.assertEqual(unchanged, [], f"these readers ignore the customer filter: {unchanged}")

    def test_overview_kpis_all_narrow_or_hold(self):
        wide = crm_dashboard_overview(**WIDE)["kpis"]
        narrow = crm_dashboard_overview(**WIDE, customer=self.customer)["kpis"]
        for group in ("leads", "opps", "prosp"):
            for key, value in narrow[group].items():
                self.assertLessEqual(value, wide[group][key], f"{group}.{key}")
        self.assertLessEqual(narrow["revenue"]["amount"], wide["revenue"]["amount"])
        self.assertLessEqual(narrow["tasks"]["open"], wide["tasks"]["open"])

    def test_overview_funnel_narrows(self):
        wide = {f["label"]: f["count"] for f in crm_dashboard_overview(**WIDE)["funnel"]}
        narrow = {f["label"]: f["count"]
                  for f in crm_dashboard_overview(**WIDE, customer=self.customer)["funnel"]}
        self.assertEqual(set(wide), set(narrow))
        for label, count in narrow.items():
            self.assertLessEqual(count, wide[label], label)

    def test_overview_selected_customer_is_never_reported_as_zero(self):
        # The customer KPI drops the date window when one is selected, so picking
        # an account created years ago must not read "0 active customers".
        narrow = crm_dashboard_overview(**WIDE, customer=self.customer)["kpis"]
        disabled = frappe.db.get_value("Customer", self.customer, "disabled")
        self.assertEqual(narrow["cust"]["active"], 0 if disabled else 1)

    def test_overview_charts_narrow_with_the_kpis(self):
        narrow = crm_dashboard_overview(**WIDE, customer=self.customer)
        scope = SC.customer_scope(self.customer)
        # A lead status mix wider than the resolved lead set would mean the chart
        # stayed global while the KPI above it narrowed.
        self.assertLessEqual(sum(r["count"] for r in narrow["lead_status"]), len(scope["Lead"]))

    def test_sales_analytics_narrows_every_money_figure(self):
        wide = crm_sales_analytics(**WIDE)["kpis"]
        narrow = crm_sales_analytics(**WIDE, customer=self.customer)["kpis"]
        for key in ("booked", "booked_orders", "billed", "billed_invoices", "outstanding"):
            self.assertLessEqual(narrow[key], wide[key], key)
        self.assertGreater(narrow["booked"], 0, "the busiest customer should have revenue")

    def test_sales_analytics_booked_matches_a_direct_query(self):
        narrow = crm_sales_analytics(**WIDE, customer=self.customer)["kpis"]
        expected = frappe.db.sql(
            """select coalesce(sum(base_grand_total), 0), count(*) from `tabSales Order`
               where docstatus=1 and customer=%s""", (self.customer,))[0]
        self.assertAlmostEqual(narrow["booked"], float(expected[0]), places=2)
        self.assertEqual(narrow["booked_orders"], int(expected[1]))

    def test_aging_narrows_and_still_sums_to_outstanding(self):
        d = crm_sales_analytics(**WIDE, customer=self.customer)
        self.assertAlmostEqual(
            sum(r["amount"] for r in d["aging"]), d["kpis"]["outstanding"], places=2)

    def test_targets_stay_company_wide(self):
        # An organisational target measured against one account would be nonsense.
        wide = crm_sales_analytics(**WIDE)["targets"]
        narrow = crm_sales_analytics(**WIDE, customer=self.customer)["targets"]
        self.assertEqual(wide, narrow)

    def test_opportunities_reader_narrows_beyond_direct_party_matches(self):
        row = _converted_customer()
        if not row:
            self.skipTest("no converted customer")
        d = crm_dashboard_opportunities(**WIDE, customer=row.name)
        scope = SC.customer_scope(row.name)
        self.assertEqual(d["kpis"]["total"], len(scope["Opportunity"]))

    def test_leads_reader_matches_the_resolved_lead_set(self):
        row = _converted_customer()
        if not row:
            self.skipTest("no converted customer")
        d = crm_dashboard_leads(**WIDE, customer=row.name)
        scope = SC.customer_scope(row.name)
        self.assertEqual(d["kpis"]["total"], len(scope["Lead"]))
        self.assertLessEqual(len(d["rows"]), len(scope["Lead"]))

    def test_events_and_tasks_narrow(self):
        wide = crm_dashboard_events_tasks(**WIDE)["kpis"]
        narrow = crm_dashboard_events_tasks(**WIDE, customer=self.customer)["kpis"]
        for key in ("events_total", "tasks_open", "emails_sent", "emails_recv"):
            self.assertLessEqual(narrow[key], wide[key], key)

    def test_an_unrelated_customer_yields_empty_pipeline_not_everything(self):
        d = crm_dashboard_overview(**WIDE, customer="no-such-customer-zzz")
        self.assertEqual(d["kpis"]["leads"]["total"], 0)
        self.assertEqual(d["kpis"]["opps"]["total"], 0)
        self.assertEqual(d["kpis"]["revenue"]["amount"], 0)

    def test_a_quote_bearing_name_does_not_break_the_query(self):
        # Customer names on this site include apostrophes; the scope is escaped,
        # not interpolated.
        d = crm_dashboard_overview(**WIDE, customer="O'Brien's ; drop table x")
        self.assertEqual(d["kpis"]["leads"]["total"], 0)
