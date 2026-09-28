"""Tests for the quotations view (api/quotations.py).

Conversion is the number that matters and the one easiest to get wrong: it is
submitted quotations that at least one Sales Order line points back at, over all
submitted quotations. Drafts were never sent, so they count in neither.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from upande_crm.api import quotations as Q
from upande_crm.api import settings as S


def _clear():
    frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)


class TestConversionMaths(FrappeTestCase):
    def test_drafts_count_in_neither_side(self):
        quotes = [
            {"name": "Q1", "docstatus": 1}, {"name": "Q2", "docstatus": 1},
            {"name": "Q3", "docstatus": 0}, {"name": "Q4", "docstatus": 1},
        ]
        orders = {"Q1": ["SO-1"], "Q3": ["SO-2"]}
        r = Q._conversion(quotes, orders)
        self.assertEqual((r["submitted"], r["converted"]), (3, 1))
        self.assertAlmostEqual(r["rate"], 33.3, places=1)

    def test_no_submitted_quotes_is_no_rate_not_zero(self):
        self.assertIsNone(Q._conversion([{"name": "Q", "docstatus": 0}], {})["rate"])


class TestQuotationsDashboard(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        _clear()

    def test_shape(self):
        d = Q.crm_dashboard_quotations(add_days(nowdate(), -365), nowdate())
        for k in ("kpis", "trend", "by_status", "rows", "top_items", "followup_days", "currency"):
            self.assertIn(k, d)
        for k in ("drafts", "submitted", "open", "converted", "lost", "expired", "conversion_rate",
                  "avg_value", "median_days_to_order", "needs_followup"):
            self.assertIn(k, d["kpis"])

    def test_rows_carry_their_orders(self):
        d = Q.crm_dashboard_quotations(add_days(nowdate(), -365), nowdate())
        for r in d["rows"]:
            self.assertIsInstance(r["orders"], list)
            self.assertIn("followup", r)

    def test_followup_flags_old_open_quotes(self):
        rows = [frappe._dict(name="Q", docstatus=1, status="Open", transaction_date=add_days(nowdate(), -30))]
        Q._flag(rows, {}, 7)
        self.assertTrue(rows[0]["followup"])
        # Still "Open" in ERPNext, but an order already came from it: no chasing.
        rows = [frappe._dict(name="Q", docstatus=1, status="Open", transaction_date=add_days(nowdate(), -30))]
        Q._flag(rows, {"Q": ["SO"]}, 7)
        self.assertFalse(rows[0]["followup"])

    def test_customer_quotations_and_price_history(self):
        row = frappe.db.sql("select party_name from tabQuotation where quotation_to='Customer' limit 1")
        if not row:
            self.skipTest("no customer quotations on this site")
        d = Q.crm_customer_quotations(row[0][0])
        self.assertTrue(d["rows"])
        for h in d["price_history"]:
            self.assertTrue(h["item_code"])
            self.assertTrue(all("rate" in p and "date" in p for p in h["points"]))

    def test_module_off_refuses(self):
        doc = frappe.get_single(S.SETTINGS_DOCTYPE)
        doc.module_quotations = 0
        doc.save(ignore_permissions=True)
        _clear()
        try:
            with self.assertRaises(frappe.PermissionError):
                Q.crm_dashboard_quotations()
        finally:
            doc = frappe.get_single(S.SETTINGS_DOCTYPE)
            doc.module_quotations = 1
            doc.save(ignore_permissions=True)
