"""Tests for catalogue interests on the CRM side: who sees them, and turning
one into an Opportunity (api/catalogues.py)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import catalogues as C
from upande_crm.tests.test_catalogue_model import make_catalogue
from upande_crm.tests.test_catalogues import sales_user

RESTRICTED = "crm-catalogue-restricted@example.com"


def interest(cat, party_type, party, qty=5, frequency="Weekly", priced=1):
    line = cat.lines[0]
    price, tier = cat.price_for(line, "USD")
    return frappe.get_doc({
        "doctype": "CRM Catalogue Interest", "catalogue": cat.name, "party_type": party_type, "party": party,
        "contact_name": "Buyer", "email": "b@example.com", "currency": "USD",
        "items": [{"line_ref": line.name, "item": line.item, "item_name": line.item_name, "grade": line.grade,
                   "box_type": "Standard", "pack_qty": line.pack_qty, "qty": qty, "frequency": frequency,
                   "price": price, "tier_price": tier, "priced": priced}],
    }).insert(ignore_permissions=True)


def _setup_users(cls):
    """Shared by both classes: two customers, a plain and a restricted sales user."""
    frappe.set_user("Administrator")
    from upande_crm.setup import ensure_crm_role_permissions

    ensure_crm_role_permissions()
    cls.mine, cls.theirs = frappe.get_all("Customer", pluck="name", limit=2)
    sales_user()
    sales_user(RESTRICTED)
    if not frappe.db.exists("User Permission", {"user": RESTRICTED, "allow": "Customer"}):
        frappe.get_doc({"doctype": "User Permission", "user": RESTRICTED, "allow": "Customer",
                        "for_value": cls.mine, "apply_to_all_doctypes": 1}).insert(ignore_permissions=True)
    frappe.db.commit()
    frappe.clear_cache(user=RESTRICTED)


class TestInterests(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _setup_users(cls)

    def setUp(self):
        frappe.set_user("Administrator")
        self.cat = make_catalogue(status="Live", volume_tier_qty=4)

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def names(self, **kw):
        return {r["name"] for r in C.crm_catalogue_interests(**kw)["rows"]}

    def test_restricted_user_sees_only_readable_parties(self):
        a = interest(self.cat, "Customer", self.mine).name
        b = interest(self.cat, "Customer", self.theirs).name
        frappe.set_user(RESTRICTED)
        seen = self.names(catalogue=self.cat.name)
        self.assertIn(a, seen)
        self.assertNotIn(b, seen)
        with self.assertRaises(frappe.PermissionError):
            C.crm_catalogue_interest_get(b)

    def test_owner_sees_all_on_own_catalogue(self):
        frappe.set_user(RESTRICTED)
        own = make_catalogue(status="Live")
        frappe.set_user("Administrator")
        b = interest(own, "Customer", self.theirs).name
        frappe.set_user(RESTRICTED)
        self.assertIn(b, self.names(catalogue=own.name))
        self.assertEqual(C.crm_catalogue_interest_get(b)["interest"]["name"], b)

    def test_rows_carry_totals(self):
        name = interest(self.cat, "Customer", self.mine, qty=3).name
        row = next(r for r in C.crm_catalogue_interests()["rows"] if r["name"] == name)
        self.assertEqual((row["lines"], row["boxes"], row["weekly"]), (1, 3, True))
        self.assertEqual(row["catalogue_title"], self.cat.title)

    def test_status_change(self):
        name = interest(self.cat, "Customer", self.mine).name
        C.crm_catalogue_interest_status(name, "Contacted")
        self.assertEqual(frappe.db.get_value("CRM Catalogue Interest", name, "status"), "Contacted")
        with self.assertRaises(frappe.ValidationError):
            C.crm_catalogue_interest_status(name, "Nope")

    def test_make_opportunity_weekly_line(self):
        name = interest(self.cat, "Customer", self.mine, qty=5).name
        opp = frappe.get_doc("Opportunity", C.crm_catalogue_make_opportunity(name)["opportunity"])
        self.assertEqual((opp.opportunity_from, opp.party_name, opp.currency), ("Customer", self.mine, "USD"))
        row = opp.items[0]
        self.assertEqual(row.qty, 1500)
        self.assertAlmostEqual(row.rate, 0.2204)
        self.assertIn("Weekly", row.description)
        doc = frappe.get_doc("CRM Catalogue Interest", name)
        self.assertEqual((doc.status, doc.opportunity), ("Converted", opp.name))

    def test_make_opportunity_below_tier_uses_price(self):
        name = interest(self.cat, "Customer", self.mine, qty=2, frequency="One-off").name
        opp = frappe.get_doc("Opportunity", C.crm_catalogue_make_opportunity(name)["opportunity"])
        self.assertAlmostEqual(opp.items[0].rate, 0.232)

    def test_make_opportunity_idempotent(self):
        name = interest(self.cat, "Customer", self.mine).name
        first = C.crm_catalogue_make_opportunity(name)["opportunity"]
        self.assertEqual(C.crm_catalogue_make_opportunity(name)["opportunity"], first)


class TestInterestDeskPermissions(FrappeTestCase):
    """Review fix: desk/REST must apply the same visibility as the CRM."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _setup_users(cls)

    setUp = TestInterests.setUp
    tearDown = TestInterests.tearDown

    def test_list_and_doc_permission_hide_unreadable_party(self):
        a = interest(self.cat, "Customer", self.mine).name
        b = interest(self.cat, "Customer", self.theirs).name
        frappe.set_user(RESTRICTED)
        names = set(frappe.get_list("CRM Catalogue Interest", pluck="name", limit=0))
        self.assertIn(a, names)
        self.assertNotIn(b, names)
        self.assertFalse(frappe.has_permission("CRM Catalogue Interest", "read", b))

    def test_owner_sees_interest_on_own_catalogue_via_desk(self):
        frappe.set_user(RESTRICTED)
        own = make_catalogue(status="Live")
        frappe.set_user("Administrator")
        b = interest(own, "Customer", self.theirs).name
        frappe.set_user(RESTRICTED)
        self.assertIn(b, frappe.get_list("CRM Catalogue Interest", pluck="name", limit=0))
        self.assertTrue(frappe.has_permission("CRM Catalogue Interest", "read", b))
