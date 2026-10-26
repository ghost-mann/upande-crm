"""Tests for the buyer's side of catalogues (api/catalogue_public.py).

Guest calls run as Guest. The rules under test are the spec's: a stranger
becomes at most a Lead; a known buyer is never duplicated; a forwarded personal
link does not file a stranger under the person it was sent to; and a closed
offer takes nothing.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from upande_crm.api import catalogue_public as P
from upande_crm.tests.test_catalogue_model import make_catalogue

INTEREST = "CRM Catalogue Interest"


def live(**kw):
    return make_catalogue(status="Live", currencies="USD, EUR", volume_tier_qty=4, **kw)


def contact(**kw):
    data = {"name": "Jane Buyer", "company": "Blooms BV", "email": "jane@blooms.example", "phone": "",
            "country": "Netherlands", "message": ""}
    data.update(kw)
    return json.dumps(data)


def lines(doc, qty=5, frequency="Weekly"):
    return json.dumps([{"line": doc.lines[0].name, "qty": qty, "frequency": frequency}])


class PublicCase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.customer = frappe.db.get_value("Customer", {}, "name")

    def setUp(self):
        frappe.set_user("Administrator")
        self.cat = live()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def submit(self, token=None, **kw):
        frappe.set_user("Guest")
        try:
            return P.catalogue_submit(token or self.cat.public_token, kw.pop("contact", contact()),
                                      kw.pop("lines", lines(self.cat)), kw.pop("currency", "USD"), **kw)
        finally:
            frappe.set_user("Administrator")

    def interests(self):
        return frappe.get_all(INTEREST, filters={"catalogue": self.cat.name},
                              fields=["name", "party_type", "party", "via_link"], order_by="creation asc")

    def customer_contact(self, email=None, phone=None):
        c = frappe.get_doc({"doctype": "Contact", "first_name": "Known", "last_name": "Buyer",
                            "email_ids": [{"email_id": email, "is_primary": 1}] if email else [],
                            "phone_nos": [{"phone": phone, "is_primary_mobile_no": 1}] if phone else [],
                            "links": [{"link_doctype": "Customer", "link_name": self.customer}]})
        return c.insert(ignore_permissions=True)

    def personal_link(self, party_type, party, email):
        return frappe.get_doc({"doctype": "CRM Catalogue Link", "catalogue": self.cat.name, "party_type": party_type,
                               "party": party, "contact_email": email, "sent_via": "Copied"}
                              ).insert(ignore_permissions=True)


class TestView(PublicCase):
    def test_view_groups_lines_by_item_and_counts_public_views(self):
        frappe.set_user("Guest")
        out = P.catalogue_view(self.cat.public_token)
        self.assertTrue(out["open"])
        self.assertEqual(out["currencies"], ["USD", "EUR"])
        self.assertEqual(out["groups"][0]["products"][0]["lines"][0]["prices"]["USD"]["price"], 0.232)
        self.assertNotIn("prefill", out)
        frappe.set_user("Administrator")
        self.assertEqual(frappe.db.get_value("CRM Catalogue", self.cat.name, "views"), 1)

    def test_personal_view_prefills_and_counts_opens(self):
        link = self.personal_link("Customer", self.customer, "someone@cust.example")
        frappe.set_user("Guest")
        out = P.catalogue_view(link.token)
        P.catalogue_view(link.token)
        frappe.set_user("Administrator")
        self.assertEqual(out["prefill"]["email"], "someone@cust.example")
        row = frappe.db.get_value("CRM Catalogue Link", link.name, ["open_count", "first_opened_on"], as_dict=True)
        self.assertEqual(row.open_count, 2)
        self.assertTrue(row.first_opened_on)

    def test_unknown_token(self):
        frappe.set_user("Guest")
        with self.assertRaises(frappe.DoesNotExistError):
            P.catalogue_view("nope" * 6)


class TestSubmit(PublicCase):
    def test_closed_catalogue_refuses_submit(self):
        frappe.db.set_value("CRM Catalogue", self.cat.name, "status", "Closed")
        with self.assertRaises(frappe.ValidationError):
            self.submit()
        frappe.db.set_value("CRM Catalogue", self.cat.name, {"status": "Live", "valid_to": add_days(nowdate(), -1)})
        with self.assertRaises(frappe.ValidationError):
            self.submit()

    def test_new_email_creates_lead_and_interest(self):
        self.submit()
        rows = self.interests()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].party_type, "Lead")
        lead = frappe.get_doc("Lead", rows[0].party)
        self.assertEqual(lead.email_id, "jane@blooms.example")
        self.assertEqual(lead.lead_owner, self.cat.owner)
        self.assertEqual(lead.utm_source, "Catalogue")

    def test_interest_snapshots_line(self):
        self.submit()
        item = frappe.get_doc(INTEREST, self.interests()[0].name).items[0]
        self.assertEqual((item.qty, item.frequency, item.grade, item.pack_qty), (5, "Weekly", "60 cm", 300))
        self.assertAlmostEqual(item.price, 0.232)
        self.assertAlmostEqual(item.tier_price, 0.2204)
        self.assertEqual(item.priced, 1)

    def test_missing_currency_price_snapshots_unpriced(self):
        self.submit(currency="EUR")
        item = frappe.get_doc(INTEREST, self.interests()[0].name).items[0]
        self.assertEqual(item.priced, 0)

    def test_known_customer_email_case_insensitive(self):
        self.customer_contact(email="buyer@cust.example")
        before = frappe.db.count("Lead")
        self.submit(contact=contact(email="  Buyer@Cust.EXAMPLE "))
        row = self.interests()[0]
        self.assertEqual((row.party_type, row.party), ("Customer", self.customer))
        self.assertEqual(frappe.db.count("Lead"), before)

    def test_phone_suffix_match(self):
        self.customer_contact(phone="0712345678")
        self.submit(contact=contact(email="new@else.example", phone="+254 712 345 678"))
        row = self.interests()[0]
        self.assertEqual((row.party_type, row.party), ("Customer", self.customer))

    def test_existing_lead_matched_by_email(self):
        lead = frappe.get_doc({"doctype": "Lead", "first_name": "Old", "email_id": "old@lead.example"}
                              ).insert(ignore_permissions=True)
        self.submit(contact=contact(email="OLD@lead.example"))
        self.assertEqual(self.interests()[0].party, lead.name)

    def test_personal_link_same_email_uses_party(self):
        link = self.personal_link("Customer", self.customer, "p@cust.example")
        self.submit(token=link.token, contact=contact(email="p@cust.example"))
        row = self.interests()[0]
        self.assertEqual((row.party_type, row.party, row.via_link), ("Customer", self.customer, link.name))

    def test_forwarded_link_other_email_rematches(self):
        link = self.personal_link("Customer", self.customer, "p@cust.example")
        self.submit(token=link.token, contact=contact(email="stranger@else.example"))
        row = self.interests()[0]
        self.assertEqual(row.party_type, "Lead")
        self.assertEqual(row.via_link, link.name)

    def test_resubmit_creates_second_interest_not_second_lead(self):
        self.submit()
        before = frappe.db.count("Lead")
        self.submit()
        rows = self.interests()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].party, rows[1].party)
        self.assertEqual(frappe.db.count("Lead"), before)

    def test_no_lines_refused(self):
        with self.assertRaises(frappe.ValidationError):
            self.submit(lines=json.dumps([{"line": self.cat.lines[0].name, "qty": 0}]))

    def test_foreign_line_refused(self):
        with self.assertRaises(frappe.ValidationError):
            self.submit(lines=json.dumps([{"line": "not-a-line", "qty": 2}]))

    def test_email_required_on_public_link(self):
        with self.assertRaises(frappe.ValidationError):
            self.submit(contact=contact(email=""))

    def test_honeypot_saves_nothing(self):
        out = self.submit(website="http://spam.example")
        self.assertTrue(out["ok"])
        self.assertEqual(self.interests(), [])

    def test_lead_with_custom_mandatory_field_still_inserts(self):
        # Made mandatory on the cached meta only: a real Custom Field is DDL, which
        # commits, and would outlive the test's rollback.
        field = frappe.get_meta("Lead").get_field("company_name")
        field.reqd = 1
        try:
            self.submit(contact=contact(company=""))
            self.assertEqual(self.interests()[0].party_type, "Lead")
        finally:
            field.reqd = 0

    def test_owner_notified(self):
        self.submit()
        name = self.interests()[0].name
        self.assertTrue(frappe.db.exists("Email Queue", {"reference_name": name}))
        self.assertTrue(frappe.db.exists("Notification Log", {"document_name": name, "for_user": self.cat.owner}))


class TestReviewFixes(PublicCase):
    def test_stale_line_name_falls_back_to_item_grade_box(self):
        line = self.cat.lines[0]
        picks = json.dumps([{"line": "gone-after-a-save", "qty": 3, "item": line.item, "grade": line.grade,
                             "box_type": line.box_type}])
        self.submit(lines=picks)
        self.assertEqual(frappe.get_doc(INTEREST, self.interests()[0].name).items[0].line_ref, line.name)

    def test_formatted_stored_phone_matches(self):
        self.customer_contact(phone="+254 712 345 678")
        self.submit(contact=contact(email="other@else.example", phone="0712345678"))
        row = self.interests()[0]
        self.assertEqual((row.party_type, row.party), ("Customer", self.customer))

    def test_customer_mobile_no_matches(self):
        frappe.db.set_value("Customer", self.customer, "mobile_no", "+254-733-111-222")
        self.submit(contact=contact(email="other2@else.example", phone="0733 111 222"))
        row = self.interests()[0]
        self.assertEqual((row.party_type, row.party), ("Customer", self.customer))

    def test_personal_link_without_email_matches_by_phone(self):
        link = frappe.get_doc({"doctype": "CRM Catalogue Link", "catalogue": self.cat.name,
                               "party_type": "Customer", "party": self.customer, "contact_email": None,
                               "contact_phone": "+254 799 000 111", "sent_via": "WhatsApp"}
                              ).insert(ignore_permissions=True)
        frappe.db.set_value("Customer", self.customer, "email_id", None)
        before = frappe.db.count("Lead")
        self.submit(token=link.token, contact=contact(email="typed@buyer.example", phone="0799000111"))
        row = self.interests()[0]
        self.assertEqual((row.party_type, row.party), ("Customer", self.customer))
        self.assertEqual(frappe.db.count("Lead"), before)


class TestMagazinePayload(PublicCase):
    """The guest API on the magazine display model (2026-10-26 design)."""

    def test_view_returns_theme_text_groups(self):
        frappe.set_user("Guest")
        out = P.catalogue_view(self.cat.public_token)
        self.assertTrue({"theme", "text", "sections", "groups", "mixes", "frequencies"} <= set(out))
        self.assertEqual(out["text"]["cta"], "Send my interest")

    def _avocado(self):
        return make_catalogue(status="Live", template="Avocado export", currencies="USD",
                              lines=[{"item": self.cat.lines[0].item, "grade": "16", "pack_qty": 1,
                                      "prices": {"USD": {"price": 12.4}}}])

    def test_submit_accepts_template_frequency(self):
        avo = self._avocado()
        self.submit(token=avo.public_token, lines=json.dumps([{"line": avo.lines[0].name, "qty": 400,
                                                               "frequency": "Per shipment"}]))
        name = frappe.get_all(INTEREST, filters={"catalogue": avo.name}, pluck="name")[0]
        self.assertEqual(frappe.get_doc(INTEREST, name).items[0].frequency, "Per shipment")

    def test_missing_frequency_takes_the_first(self):
        avo = self._avocado()
        self.submit(token=avo.public_token, lines=json.dumps([{"line": avo.lines[0].name, "qty": 10}]))
        name = frappe.get_all(INTEREST, filters={"catalogue": avo.name}, pluck="name")[0]
        self.assertEqual(frappe.get_doc(INTEREST, name).items[0].frequency, "Per shipment")

    def test_submit_rejects_unknown_frequency(self):
        avo = self._avocado()
        with self.assertRaises(frappe.ValidationError):
            self.submit(token=avo.public_token, lines=json.dumps([{"line": avo.lines[0].name, "qty": 10,
                                                                   "frequency": "Weekly"}]))
        self.assertFalse(frappe.get_all(INTEREST, filters={"catalogue": avo.name}))


class TestPreview(PublicCase):
    def test_preview_ignores_status_and_records_nothing(self):
        from upande_crm.api import catalogues as C

        frappe.db.set_value("CRM Catalogue", self.cat.name, "status", "Draft")
        out = C.crm_catalogue_preview(self.cat.name)
        self.assertTrue(out["groups"])
        self.assertTrue(out["preview"])
        self.assertEqual(frappe.db.get_value("CRM Catalogue", self.cat.name, "views"), 0)

    def test_preview_uses_unsaved_template(self):
        from upande_crm.api import catalogues as C

        draft = frappe.get_doc("CRM Catalogue Template", "Flowers almanac").as_dict()
        draft["headline"] = "Draft headline"
        out = C.crm_catalogue_preview(self.cat.name, frappe.as_json(draft))
        self.assertEqual(out["text"]["headline"], "Draft headline")
        self.assertNotEqual(frappe.db.get_value("CRM Catalogue Template", "Flowers almanac", "headline"),
                            "Draft headline")

    def test_preview_rejects_bad_draft_colour(self):
        from upande_crm.api import catalogues as C

        draft = frappe.get_doc("CRM Catalogue Template", "Flowers almanac").as_dict()
        draft["brand"] = "red; background:url(x)"
        with self.assertRaises(frappe.ValidationError):
            C.crm_catalogue_preview(self.cat.name, frappe.as_json(draft))

    def test_preview_requires_crm_user(self):
        from upande_crm.api import catalogues as C

        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            C.crm_catalogue_preview(self.cat.name)
