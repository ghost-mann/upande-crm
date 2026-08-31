"""Tests for what survives when a record becomes a Customer.

Every assertion here exists because the measurement said it would otherwise fail.
On this site, before this module existed, 9 of the 10 lead-derived customers had
no primary contact and no primary address — their email, mobile and phone were
simply gone.

Three properties, in the order they cost the most:

**The required fields arrive.** `Customer.default_currency` and
`default_price_list` are mandatory and the lead carries them under different
names (`custom_billing_currency`, `custom_price_list`). No ERPNext mapper maps
either.

**The email survives.** `Customer.email_id` is Read Only with
`fetch_from = customer_primary_contact.email_id`, so writing it is a silent no-op.
The only way a customer has an email is a linked primary Contact — asserted
through the Contact, not through the fetched field.

**No address is invented.** `Address.address_line1` is mandatory and only 60%
populated on leads. A lead with no street line must produce no Address at all;
this site has 2,913 real addresses and they are used for shipping.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import advance as A
from upande_crm.api import carry_across as C
from upande_crm.tests.pipeline_fixtures import lead_without_address, rich_lead


def _contact_of(customer):
    return frappe.db.get_value("Customer", customer, "customer_primary_contact")


def _address_of(customer):
    return frappe.db.get_value("Customer", customer, "customer_primary_address")


class TestTheRequiredFieldsArrive(FrappeTestCase):
    def test_currency_and_price_list_come_from_the_leads_own_fields(self):
        lead = rich_lead()
        if not (lead.get("custom_billing_currency") or lead.get("custom_price_list")):
            self.skipTest("this site has neither custom field on Lead")
        out = A.crm_lead_to_customer(lead.name, json.dumps({}))
        cust = frappe.db.get_value(
            "Customer", out["name"], ["default_currency", "default_price_list"], as_dict=True)
        if lead.get("custom_billing_currency"):
            self.assertEqual(cust.default_currency, lead.custom_billing_currency)
        if lead.get("custom_price_list"):
            self.assertEqual(cust.default_price_list, lead.custom_price_list)

    def test_the_direct_field_map_reaches_the_customer(self):
        lead = rich_lead()
        out = A.crm_lead_to_customer(lead.name, json.dumps({}))
        cust = frappe.get_doc("Customer", out["name"])
        for src, dest in C.TO_CUSTOMER["Lead"].items():
            if not C._writable("Customer", dest):
                continue
            value = lead.get(src)
            if not value:
                continue
            with self.subTest(field=f"{src}->{dest}"):
                self.assertEqual(cust.get(dest), value)


class TestTheEmailSurvives(FrappeTestCase):
    """The Contact is the whole mechanism: `Customer.email_id` is Read Only with
    `fetch_from = customer_primary_contact.email_id`, so it cannot be written.

    On this site the Contact usually already exists — ERPNext's
    `Lead.after_insert` calls `link_to_contact()` — so what is asserted is that
    the customer ends up pointing at one carrying the lead's details, whether it
    was reused or built.
    """

    def test_a_primary_contact_is_created_and_linked(self):
        lead = rich_lead()
        out = A.crm_lead_to_customer(lead.name, json.dumps({}))
        contact = _contact_of(out["name"])
        self.assertTrue(contact, "the customer has no primary contact, so it has no email")

        doc = frappe.get_doc("Contact", contact)
        self.assertEqual(doc.first_name, "Jane")
        self.assertIn(lead.email_id, [r.email_id for r in doc.email_ids])
        phones = [r.phone for r in doc.phone_nos]
        self.assertIn(lead.mobile_no, phones)
        self.assertIn(lead.phone, phones)
        # Linked back, or the customer's own contact list stays empty.
        self.assertTrue(any(
            l.link_doctype == "Customer" and l.link_name == out["name"] for l in doc.links))

    def test_the_whatsapp_number_is_kept_as_its_own_phone_row(self):
        # Contact has no WhatsApp field; the CRM's WhatsApp section still needs it.
        lead = rich_lead()
        if not lead.get("whatsapp_no"):
            self.skipTest("this site has no whatsapp_no on Lead")
        out = A.crm_lead_to_customer(lead.name, json.dumps({}))
        doc = frappe.get_doc("Contact", _contact_of(out["name"]))
        self.assertIn(lead.whatsapp_no, [r.phone for r in doc.phone_nos])

    def test_the_customers_fetched_email_is_populated_through_the_contact(self):
        lead = rich_lead()
        out = A.crm_lead_to_customer(lead.name, json.dumps({}))
        # The point of the whole exercise: this field cannot be written directly.
        self.assertEqual(frappe.db.get_value("Customer", out["name"], "email_id"),
                         lead.email_id)


class TestTheAddress(FrappeTestCase):
    def test_no_duplicate_contact_or_address_is_created(self):
        # This site already makes both on lead insert. Building second copies
        # would be worse than the problem this module fixes.
        lead = rich_lead()
        before = (frappe.db.count("Contact"), frappe.db.count("Address"))
        A.crm_lead_to_customer(lead.name, json.dumps({}))
        self.assertEqual((frappe.db.count("Contact"), frappe.db.count("Address")), before,
                         "the hop created a duplicate contact or address")

    def test_a_billing_address_is_created_and_linked(self):
        lead = rich_lead()
        out = A.crm_lead_to_customer(lead.name, json.dumps({}))
        address = _address_of(out["name"])
        self.assertTrue(address, "a lead with a street line should produce an address")
        doc = frappe.get_doc("Address", address)
        self.assertEqual(doc.address_line1, "12 Rose Road")
        self.assertEqual(doc.city, "Naivasha")
        self.assertEqual(doc.address_type, "Billing")

    def test_no_street_line_means_no_address_at_all(self):
        lead = lead_without_address()
        out = A.crm_lead_to_customer(lead.name, json.dumps({}))
        self.assertFalse(_address_of(out["name"]),
                         "an address was invented from a lead with no street line")

    def test_the_city_still_survives_in_the_notes(self):
        # It has nowhere else to go: Customer has no city field.
        lead = lead_without_address()
        out = A.crm_lead_to_customer(lead.name, json.dumps({}))
        details = frappe.db.get_value("Customer", out["name"], "customer_details") or ""
        self.assertIn(lead.city or "", details)


class TestTheProvenanceBlock(FrappeTestCase):
    def test_fields_with_no_home_on_customer_are_written_as_notes(self):
        lead = rich_lead()
        out = A.crm_lead_to_customer(lead.name, json.dumps({}))
        details = frappe.db.get_value("Customer", out["name"], "customer_details") or ""
        self.assertIn(lead.name, details, "the block should name where it came from")
        if lead.get("no_of_employees"):
            self.assertIn(str(lead.no_of_employees), details)

    def test_a_numeric_zero_is_not_reported_as_carried_data(self):
        # A live walk wrote "Annual revenue: 0.0" — `annual_revenue` is present on
        # every lead here and zero on nearly all of them.
        lead = rich_lead(annual_revenue=0)
        out = A.crm_lead_to_customer(lead.name, json.dumps({}))
        details = frappe.db.get_value("Customer", out["name"], "customer_details") or ""
        self.assertNotIn("Annual revenue", details)

    def test_the_block_is_empty_when_there_is_nothing_to_say(self):
        doc = frappe.get_doc({"doctype": "Lead", "lead_name": "x"})
        self.assertEqual(C.notes_block(doc), "")


class TestThePreview(FrappeTestCase):
    def test_the_preview_reports_what_the_hop_would_carry(self):
        lead = rich_lead()
        p = A.crm_advance_preview("Lead", lead.name, "Customer")
        self.assertEqual(p["contact"].get("email_id"), lead.email_id)
        self.assertEqual(p["address"].get("address_line1"), "12 Rose Road")
        self.assertGreater(p["notes_count"], 0)
        self.assertEqual(p["already_customer"], "")

    def test_the_preview_says_when_an_address_would_be_skipped(self):
        lead = lead_without_address()
        p = A.crm_advance_preview("Lead", lead.name, "Customer")
        self.assertEqual(p["address"], {})
        self.assertTrue(p["address_skipped"],
                        "the dialog has to be able to say why there is no address")

    def test_the_preview_writes_nothing(self):
        lead = rich_lead()
        before = frappe.db.count("Contact"), frappe.db.count("Address"), frappe.db.count("Customer")
        A.crm_advance_preview("Lead", lead.name, "Customer")
        self.assertEqual(
            (frappe.db.count("Contact"), frappe.db.count("Address"), frappe.db.count("Customer")),
            before)

    def test_the_preview_names_an_existing_customer(self):
        lead = rich_lead()
        out = A.crm_lead_to_customer(lead.name, json.dumps({}))
        p = A.crm_advance_preview("Lead", lead.name, "Customer")
        self.assertEqual(p["already_customer"], out["name"])

    def test_the_preview_degrades_rather_than_throwing(self):
        # A read that sits inside a dialog must never be the thing that breaks it.
        self.assertEqual(A.crm_advance_preview("Lead", "no-such-lead", "Customer"), {})
        self.assertEqual(A.crm_advance_preview("Lead", "", "Customer"), {})
        self.assertEqual(A.crm_advance_preview("Sales Order", "x", "Customer"), {})


class TestWritableDetection(FrappeTestCase):
    def test_fetch_from_fields_are_not_treated_as_writable(self):
        # This is the check that stops `email_id` looking mapped and being empty.
        self.assertFalse(C._writable("Customer", "email_id"))
        self.assertFalse(C._writable("Customer", "mobile_no"))
        self.assertTrue(C._writable("Customer", "territory"))

    def test_an_absent_field_is_not_writable(self):
        self.assertFalse(C._writable("Customer", "no_such_field_at_all"))
