"""Tests for the CRM Catalogue record (see docs/superpowers/specs/
2026-10-25-crm-catalogues-design.md).

A catalogue owns the facts the buyer's page and every submission are built on:
an unguessable token, currencies that exist, prices only in those currencies,
and whether the offer is open today.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from upande_crm.modules import enabled_map

DOCTYPE = "CRM Catalogue"


def _item():
    return frappe.db.get_value("Item", {"disabled": 0}, "name")


def make_catalogue(**kw):
    """A saved catalogue with one USD-priced line. Shared with the other
    catalogue tests."""
    data = {
        "doctype": DOCTYPE,
        "title": "Test offer",
        "company": frappe.db.get_value("Company", {}, "name"),
        "currencies": "USD",
        "lines": [{"item": _item(), "grade": "60 cm", "pack_qty": 300, "bunch": "x10",
                   "prices": {"USD": {"price": 0.232, "tier": 0.2204}}}],
    }
    data.update(kw)
    return frappe.get_doc(data).insert(ignore_permissions=True)


class TestCatalogueModel(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.db.rollback()

    def test_token_is_set_and_unique(self):
        a, b = make_catalogue(), make_catalogue()
        self.assertEqual(len(a.public_token), 24)
        self.assertNotEqual(a.public_token, b.public_token)

    def test_currencies_validated(self):
        with self.assertRaises(frappe.ValidationError):
            make_catalogue(currencies="USD, XXX")
        doc = make_catalogue(currencies="usd, eur")
        self.assertEqual(doc.currencies, "USD, EUR")
        self.assertEqual(doc.currency_list(), ["USD", "EUR"])

    def test_line_prices_only_for_catalogue_currencies(self):
        with self.assertRaises(frappe.ValidationError):
            make_catalogue(lines=[{"item": _item(), "prices": {"GBP": {"price": 1}}}])

    def test_missing_currency_price_is_none(self):
        doc = make_catalogue(currencies="USD, EUR")
        self.assertEqual(doc.price_for(doc.lines[0], "EUR"), (None, None))
        self.assertEqual(doc.price_for(doc.lines[0], "USD"), (0.232, 0.2204))

    def test_is_open(self):
        doc = make_catalogue()
        self.assertFalse(doc.is_open())
        doc.status = "Live"
        self.assertTrue(doc.is_open())
        doc.valid_to = add_days(nowdate(), -1)
        self.assertFalse(doc.is_open())
        doc.valid_to = None
        doc.status = "Closed"
        self.assertFalse(doc.is_open())

    def test_product_photo_survives_save(self):
        doc = make_catalogue()
        doc.products[0].image = "/files/aster.jpg"
        doc.save()
        doc.reload()
        self.assertEqual(doc.products[0].image, "/files/aster.jpg")

    def test_new_product_rows_reach_the_database(self):
        # Replacing the product table with fresh rows (as the desk, REST or an
        # MCP update does) must store them, not only keep them in memory.
        doc = make_catalogue()
        item = doc.lines[0].item
        doc.set("products", [])
        doc.append("products", {"item": item, "image": "/files/new.jpg", "note": "Fresh"})
        doc.save()
        stored = frappe.get_all("CRM Catalogue Product", filters={"parent": doc.name},
                                fields=["item", "image", "note"])
        self.assertEqual([(r.item, r.image, r.note) for r in stored], [(item, "/files/new.jpg", "Fresh")])

    def test_module_registered(self):
        self.assertIn("cat", enabled_map())


class TestInfoUrl(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_only_web_links_are_kept(self):
        doc = make_catalogue(lines=[{"item": _item(), "info_url": "javascript:alert(1)"},
                                    {"item": _item(), "info_url": "https://www.marginpar.com/x"}])
        self.assertIsNone(doc.lines[0].info_url)
        self.assertEqual(doc.lines[1].info_url, "https://www.marginpar.com/x")
