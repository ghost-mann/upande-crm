"""Tests for the CRM side of catalogues (api/catalogues.py): build, list,
duplicate, and who may edit what."""

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import catalogues as C
from upande_crm.api import settings as S
from upande_crm.tests.test_catalogue_model import _item, make_catalogue

SALES = "crm-catalogue-sales@example.com"


def sales_user(email=SALES, roles=("Sales User", "CRM User")):
    """A plain sales user, created once and reused."""
    if not frappe.db.exists("User", email):
        frappe.get_doc({"doctype": "User", "email": email, "first_name": "Catalogue Test",
                        "send_welcome_email": 0, "user_type": "System User",
                        "roles": [{"role": r} for r in roles]}).insert(ignore_permissions=True)
    return email


def payload(**kw):
    data = {"title": "Autumn offer", "company": frappe.db.get_value("Company", {}, "name"),
            "currencies": "USD, EUR", "volume_tier_qty": 4, "terms": "<p>5 days lead time</p>",
            "lines": [{"item": _item(), "grade": "60 cm", "box_type": "Standard", "color": "White",
                       "pack_qty": 300, "bunch": "x10", "weight": 11.28,
                       "prices": {"USD": {"price": 0.232, "tier": 0.2204}, "EUR": {"price": 0.2}}}]}
    data.update(kw)
    return frappe.as_json(data)


class TestCatalogues(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        from upande_crm.setup import ensure_crm_role_permissions

        ensure_crm_role_permissions()
        sales_user()

    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()
        frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)

    def test_save_and_get_roundtrip(self):
        name = C.crm_catalogue_save(payload())["catalogue"]["name"]
        got = C.crm_catalogue_get(name)
        line = got["catalogue"]["lines"][0]
        self.assertEqual(line["prices"], {"USD": {"price": 0.232, "tier": 0.2204}, "EUR": {"price": 0.2}})
        self.assertEqual(line["grade"], "60 cm")
        self.assertTrue(got["public_url"].endswith("/catalogue/" + got["catalogue"]["public_token"]))

    def test_save_replaces_lines(self):
        name = C.crm_catalogue_save(payload())["catalogue"]["name"]
        C.crm_catalogue_save(payload(name=name, lines=[]))
        self.assertEqual(C.crm_catalogue_get(name)["catalogue"]["lines"], [])

    def test_sales_user_cannot_edit_others_catalogue(self):
        name = C.crm_catalogue_save(payload())["catalogue"]["name"]
        frappe.set_user(SALES)
        with self.assertRaises(frappe.PermissionError):
            C.crm_catalogue_save(payload(name=name, title="Hijacked"))

    def test_sales_user_edits_own_catalogue(self):
        frappe.set_user(SALES)
        name = C.crm_catalogue_save(payload())["catalogue"]["name"]
        C.crm_catalogue_save(payload(name=name, title="Mine"))
        self.assertEqual(C.crm_catalogue_get(name)["catalogue"]["title"], "Mine")

    def test_duplicate_gets_new_token_and_draft(self):
        src = make_catalogue(status="Live")
        new = C.crm_catalogue_duplicate(src.name)["name"]
        doc = frappe.get_doc("CRM Catalogue", new)
        self.assertEqual(doc.status, "Draft")
        self.assertNotEqual(doc.public_token, src.public_token)
        self.assertEqual(len(doc.lines), 1)

    def test_status_change(self):
        src = make_catalogue()
        C.crm_catalogue_status(src.name, "Live")
        self.assertEqual(frappe.db.get_value("CRM Catalogue", src.name, "status"), "Live")
        with self.assertRaises(frappe.ValidationError):
            C.crm_catalogue_status(src.name, "Bogus")

    def test_list_counts(self):
        src = make_catalogue()
        cust = frappe.db.get_value("Customer", {}, "name")
        frappe.get_doc({"doctype": "CRM Catalogue Link", "catalogue": src.name, "party_type": "Customer",
                        "party": cust, "sent_via": "Copied"}).insert(ignore_permissions=True)
        frappe.get_doc({"doctype": "CRM Catalogue Interest", "catalogue": src.name, "party_type": "Customer",
                        "party": cust, "contact_name": "X"}).insert(ignore_permissions=True)
        row = next(r for r in C.crm_catalogues()["rows"] if r["name"] == src.name)
        self.assertEqual((row["links"], row["opened"], row["interests"], row["lines"]), (1, 0, 1, 1))

    def test_module_off_refuses(self):
        doc = frappe.get_single(S.SETTINGS_DOCTYPE)
        doc.module_catalogues = 0
        doc.save(ignore_permissions=True)
        frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)
        with self.assertRaises(frappe.PermissionError):
            C.crm_catalogues()


class TestLineIdentity(FrappeTestCase):
    """Review fix: saving must not re-key lines, or a buyer with the page open
    can no longer submit."""

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def test_save_keeps_line_names(self):
        out = C.crm_catalogue_save(payload())["catalogue"]
        line = dict(out["lines"][0])
        line["prices"] = {"USD": {"price": 0.3}}
        again = C.crm_catalogue_save(payload(name=out["name"], lines=[line]))["catalogue"]
        self.assertEqual(again["lines"][0]["name"], line["name"])
        self.assertEqual(again["lines"][0]["prices"], {"USD": {"price": 0.3}})

    def test_foreign_line_name_is_not_adopted(self):
        a = C.crm_catalogue_save(payload())["catalogue"]
        b = C.crm_catalogue_save(payload())["catalogue"]
        stolen = dict(a["lines"][0])
        out = C.crm_catalogue_save(payload(name=b["name"], lines=[stolen]))["catalogue"]
        self.assertNotEqual(out["lines"][0]["name"], stolen["name"])
        self.assertEqual(len(frappe.get_doc("CRM Catalogue", a["name"]).lines), 1)


class TestDeskPermissions(FrappeTestCase):
    """Review fix: the owner-only and party-visibility rules must hold through
    desk and REST, not only through the CRM's own endpoints."""

    def setUp(self):
        frappe.set_user("Administrator")
        sales_user()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def test_sales_user_cannot_write_others_catalogue_via_desk(self):
        doc = make_catalogue()
        frappe.set_user(SALES)
        self.assertTrue(frappe.has_permission("CRM Catalogue", "read", doc.name))
        self.assertFalse(frappe.has_permission("CRM Catalogue", "write", doc.name))

    def test_sales_user_can_create_via_desk(self):
        frappe.set_user(SALES)
        doc = frappe.new_doc("CRM Catalogue")
        self.assertTrue(frappe.has_permission("CRM Catalogue", "create", doc))
