"""Tests for the customer page API (`upande_crm.api.customer`).

Two customers are used: a fresh one with an awkward name and no history at all,
which every tab must answer with empty structures rather than errors, and the
real customer on this site with the most invoices, whose header figures are
checked against direct SQL.
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import customer as C
from upande_crm.api import settings as S

EMPTY_NAME = "_CP Test / O'Brien & Co"


def _clear():
    frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)


def _save(**patch_):
    doc = frappe.get_single(S.SETTINGS_DOCTYPE)
    doc.update(patch_)
    doc.save(ignore_permissions=True)
    _clear()


def _leaf(doctype):
    return frappe.db.get_value(doctype, {"is_group": 0}, "name")


class CustomerPageCase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        existing = frappe.db.get_value("Customer", {"customer_name": EMPTY_NAME}, "name")
        if existing:
            cls.empty = existing
        else:
            # ignore_mandatory: this site makes currency and price list
            # mandatory; the point of this customer is that it has neither.
            doc = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": EMPTY_NAME,
                "customer_type": "Company",
                "customer_group": _leaf("Customer Group"),
                "territory": _leaf("Territory"),
            })
            doc.flags.ignore_mandatory = True
            cls.empty = doc.insert(ignore_permissions=True).name
        row = frappe.db.sql(
            """select customer from `tabSales Invoice` where docstatus=1
               group by customer order by count(*) desc limit 1"""
        )
        cls.busy = row[0][0] if row else None

    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        _clear()


class TestHeader(CustomerPageCase):
    def test_awkward_names_resolve(self):
        h = C.crm_customer_header(self.empty)
        self.assertEqual(h["customer"]["name"], self.empty)

    def test_empty_customer_has_zero_figures(self):
        f = C.crm_customer_header(self.empty)["figures"]
        self.assertEqual(f["order_count"], 0)
        self.assertEqual(f["lifetime_revenue"], 0)
        self.assertIsNone(f["last_order_date"])
        self.assertIsNone(f["days_since_last_order"])

    def test_header_matches_direct_sql(self):
        h = C.crm_customer_header(self.busy)
        total = frappe.db.sql(
            "select coalesce(sum(base_grand_total),0) from `tabSales Invoice` where customer=%s and docstatus=1",
            self.busy,
        )[0][0]
        self.assertAlmostEqual(h["figures"]["lifetime_revenue"], float(total), places=2)
        self.assertEqual(
            h["figures"]["order_count"],
            frappe.db.count("Sales Order", {"customer": self.busy, "docstatus": 1}),
        )

    def test_header_carries_configured_tabs(self):
        _save(custpage_tabs="orders\ntimeline", custpage_default_tab="timeline")
        h = C.crm_customer_header(self.empty)
        self.assertEqual(h["tabs"], ["orders", "timeline"])
        self.assertEqual(h["default_tab"], "timeline")

    def test_unknown_customer_raises(self):
        with self.assertRaises(frappe.DoesNotExistError):
            C.crm_customer_header("__no_such_customer__")


class TestTabs(CustomerPageCase):
    def test_empty_customer_returns_empty_structures(self):
        self.assertEqual(C.crm_customer_orders(self.empty)["rows"], [])
        self.assertEqual(C.crm_customer_orders(self.empty)["total"], 0)
        self.assertEqual(C.crm_customer_contracts(self.empty)["rows"], [])
        ov = C.crm_customer_overview(self.empty)
        self.assertEqual(ov["top_items"], [])
        self.assertEqual(len(ov["trend"]), 12)
        self.assertTrue(all(r["amount"] == 0 for r in ov["trend"]))

    def test_orders_page_and_total(self):
        r = C.crm_customer_orders(self.busy, kind="Sales Invoice", page_len=5)
        self.assertLessEqual(len(r["rows"]), 5)
        self.assertEqual(
            r["total"], frappe.db.count("Sales Invoice", {"customer": self.busy, "docstatus": ["<", 2]})
        )

    def test_orders_second_page_differs(self):
        a = C.crm_customer_orders(self.busy, kind="Sales Invoice", page_len=5)
        b = C.crm_customer_orders(self.busy, kind="Sales Invoice", start=5, page_len=5)
        if a["total"] > 5:
            self.assertFalse({r["name"] for r in a["rows"]} & {r["name"] for r in b["rows"]})

    def test_orders_page_len_is_clamped(self):
        r = C.crm_customer_orders(self.busy, kind="Sales Invoice", page_len=10_000)
        self.assertLessEqual(len(r["rows"]), 100)

    def test_orders_status_filter(self):
        r = C.crm_customer_orders(self.busy, kind="Sales Invoice", status="Paid", page_len=20)
        self.assertTrue(all(row["status"] == "Paid" for row in r["rows"]))

    def test_orders_rejects_unknown_kind(self):
        with self.assertRaises(frappe.ValidationError):
            C.crm_customer_orders(self.busy, kind="User")

    def test_pricing_names_its_source(self):
        p = C.crm_customer_pricing(self.busy)
        self.assertIn(p["source"], ("customer", "customer_group", None))
        if p["price_list"] is None:
            self.assertEqual(p["rows"], [])

    def test_pricing_search_with_underscore_is_literal(self):
        p = C.crm_customer_pricing(self.busy, search="_")
        for r in p["rows"]:
            self.assertTrue("_" in (r["item_code"] or "") or "_" in (r["item_name"] or ""))

    def test_contracts_report_availability(self):
        self.assertIn("available", C.crm_customer_contracts(self.busy))


class TestAccess(CustomerPageCase):
    ENDPOINTS = ("crm_customer_header", "crm_customer_overview", "crm_customer_orders",
                 "crm_customer_pricing", "crm_customer_contracts")

    def test_customer_endpoints_require_customer_read(self):
        # Patch the permission check: building a real user who passes _guard but
        # lacks Customer read depends on site DocPerms this test should not own.
        with patch("upande_crm.api.customer.frappe.has_permission", side_effect=frappe.PermissionError):
            for name in self.ENDPOINTS:
                with self.assertRaises(frappe.PermissionError, msg=name):
                    getattr(C, name)(self.busy)

    def test_module_off_refuses(self):
        _save(module_customer_page=0)
        for name in self.ENDPOINTS:
            with self.assertRaises(frappe.PermissionError, msg=name):
                getattr(C, name)(self.busy)

    def test_guest_is_refused(self):
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            C.crm_customer_header(self.busy)
