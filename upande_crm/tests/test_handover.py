"""Tests for the field and contact handover between pipeline stages.

Measured on this site before any of this was written, because the shape of the
bug decides the shape of the fix:

    prospect-sourced opportunities        8, of which 0 carried a contact email,
                                          0 a contact person
    customers                           887, of which 11 had a primary address
                                          and 18 any lead back-link
    Customer <-> Address links        2,751, i.e. re-entered by hand afterwards

Two hops in ERPNext already work, and are deliberately **not** tested here — a test
that passes the moment it is written proves nothing:

  * **Lead -> Opportunity.** Frappe's mapper copies same-named fields on its own, and
    `lead.make_opportunity`'s `_set_missing_values` already walks the Dynamic Links
    for the address and contact person.
  * **Lead -> Prospect.** Not `create_prospect`, which only copies scalars, but
    `Prospect.on_update` -> `link_with_lead_contact_and_address`, which re-links every
    linked lead's Contact and Address onto the prospect. Three tests asserting this
    were written and deleted once they passed unchanged.

  * **Lead -> Customer.** Expected to be the worst of them and it is not:
    `_make_customer` really does name the lead's Contact and Address on the Customer
    without linking them to it, and `Customer.create_primary_contact` really does
    bail out whenever `lead_name` is set — but `Customer.on_update` ->
    `link_address_and_contact` extends the Dynamic Links from the Lead, Opportunity
    *and* Prospect onto the new Customer, which repairs both. `TestLeadToCustomer`
    keeps those assertions as regression guards, since this app now hooks an insert
    path and that property is what a careless hook would break.

**One gap is real,** and `TestProspectToOpportunity` covers it:
`Prospect.make_opportunity` maps four fields, and Prospect has no email, mobile or
contact field of its own — so every prospect-sourced opportunity loses the person to
call, even though `link_with_lead_contact_and_address` has by then given the prospect
a Contact to offer.

What remains wrong at the Customer stage is not a mapping. Only 18 of 887 customers
carry any lead back-link, because the conversion is barely used — a missing step, not
a broken mapper, and out of scope here.

`TestItLeavesThingsAlone` asserts the inverse property. The hook sits in the insert
path of every Opportunity on the site, so "does nothing when there is no CRM source"
and "never overwrites a value already set" are what keep it from becoming a liability.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm import handover
from upande_crm.api import advance as A
from upande_crm.api import leads as L

# The lead fixture is imported rather than copied: this site has made eleven Lead
# fields mandatory, two of them custom, and a second hand-written fixture naming
# them would rot the moment the site changes. It lives in `pipeline_fixtures`,
# shared with the capture, advance and carry-across tests.
from upande_crm.tests.pipeline_fixtures import save_lead as _save


def _a_country():
    for name in ("Kenya", "Netherlands"):
        if frappe.db.exists("Country", name):
            return name
    rows = frappe.get_all("Country", pluck="name", limit=1)
    return rows[0] if rows else None


def _links_to(parenttype, doctype, name):
    """The `parenttype` documents whose Dynamic Links point at `doctype`/`name`."""
    return set(frappe.get_all(
        "Dynamic Link",
        filters={"link_doctype": doctype, "link_name": name, "parenttype": parenttype},
        pluck="parent",
    ))


def _contact_of(doctype, name):
    rows = _links_to("Contact", doctype, name)
    return sorted(rows)[0] if rows else None


def _add_address(doctype, name, title):
    country = _a_country()
    doc = frappe.get_doc({
        "doctype": "Address",
        "address_title": title,
        "address_type": "Billing",
        "address_line1": "Moi South Lake Road",
        "city": "Naivasha",
        **({"country": country} if country else {}),
        "links": [{"link_doctype": doctype, "link_name": name}],
    })
    doc.insert()
    return doc.name


def _add_contact(doctype, name, first_name, email, mobile):
    doc = frappe.get_doc({
        "doctype": "Contact",
        "first_name": first_name,
        "email_ids": [{"email_id": email, "is_primary": 1}],
        "phone_nos": [{"phone": mobile, "is_primary_mobile_no": 1}],
        "links": [{"link_doctype": doctype, "link_name": name}],
    })
    doc.insert()
    return doc.name


# Fieldtypes that hold no writable scalar, mirroring `api/leads.py`.
_NON_INPUT = {
    "Section Break", "Column Break", "Tab Break", "HTML", "Heading", "Fold",
    "Button", "Image", "Table", "Table MultiSelect", "Read Only",
}

_FORMATTED = {"Email": "probe-test@example.com", "Phone": "+254700111222",
              "URL": "https://example.com"}


def _plausible(field):
    if field.default:
        return field.default
    if field.fieldtype == "Link":
        return frappe.db.get_default(field.options) or next(
            iter(frappe.get_all(field.options, pluck="name", limit=1)), None)
    if field.fieldtype == "Select":
        return next((o for o in str(field.options or "").split("\n") if o), None)
    if field.fieldtype in ("Int", "Float", "Currency", "Percent"):
        return 1
    return _FORMATTED.get(field.options) or f"probe-{field.fieldname}"


def _fill_required(doc):
    """Fill whatever this site has made mandatory and the mapper left empty.

    Read from the meta rather than named, for the same reason `test_leads` does it:
    this install has made `default_currency` and `default_price_list` mandatory on
    Customer, which means ERPNext's own Lead -> Customer button raises MandatoryError
    here before any of the handover can matter. The desk form fills them; so does this.
    """
    for f in frappe.get_meta(doc.doctype).fields:
        if not f.reqd or f.fieldtype in _NON_INPUT or doc.get(f.fieldname):
            continue
        value = _plausible(f)
        if value is not None:
            doc.set(f.fieldname, value)
    return doc


def _a_lead():
    """A lead with an Address and a Contact of its own.

    The Lead controller creates a Contact itself when CRM Settings says to, so the
    existing one is reused when it is there — a second contact would make
    "which contact carried across" ambiguous for no gain.
    """
    lead = _save()["name"]
    contact = _contact_of("Lead", lead)
    if not contact:
        contact = _add_contact("Lead", lead, f"Probe Contact {lead}",
                               f"probe-contact-{lead}@example.com", "+254700111222")
    address = _add_address("Lead", lead, f"Probe Farm {lead}")
    return lead, contact, address


class TestProspectToOpportunity(FrappeTestCase):
    """The hop that loses the person to call: 0 of 8 on this site carried one."""

    def _a_prospect(self):
        """A prospect with a Contact and an Address of its own."""
        lead, _, _ = _a_lead()
        prospect = A.crm_lead_to_prospect(lead)["prospect"]
        contact = _add_contact("Prospect", prospect, f"Probe Buyer {prospect}",
                               f"probe-prospect-{prospect}@example.com".replace(" ", "-"),
                               "+254700333444")
        address = _add_address("Prospect", prospect, f"Probe Depot {prospect}")
        return prospect, contact, address

    def test_the_opportunity_keeps_the_contact_person(self):
        prospect, contact, _ = self._a_prospect()
        opp = A.crm_prospect_to_opportunity(prospect)["name"]
        self.assertEqual(frappe.db.get_value("Opportunity", opp, "contact_person"), contact)

    def test_the_opportunity_keeps_the_contact_email(self):
        prospect, contact, _ = self._a_prospect()
        expected = frappe.db.get_value("Contact Email", {"parent": contact, "is_primary": 1},
                                       "email_id")
        opp = A.crm_prospect_to_opportunity(prospect)["name"]
        self.assertEqual(frappe.db.get_value("Opportunity", opp, "contact_email"), expected)

    def test_the_opportunity_keeps_the_contact_mobile(self):
        prospect, contact, _ = self._a_prospect()
        expected = frappe.db.get_value("Contact Phone",
                                       {"parent": contact, "is_primary_mobile_no": 1}, "phone")
        opp = A.crm_prospect_to_opportunity(prospect)["name"]
        self.assertEqual(frappe.db.get_value("Opportunity", opp, "contact_mobile"), expected)

    def test_the_opportunity_shows_who_the_contact_is(self):
        """`contact_display` is the name the desk and the CRM list actually render."""
        prospect, contact, _ = self._a_prospect()
        expected = frappe.db.get_value("Contact", contact, "first_name")
        opp = A.crm_prospect_to_opportunity(prospect)["name"]
        self.assertEqual(frappe.db.get_value("Opportunity", opp, "contact_display"), expected)

    def test_the_opportunity_keeps_the_billing_address(self):
        prospect, _, address = self._a_prospect()
        opp = A.crm_prospect_to_opportunity(prospect)["name"]
        self.assertEqual(frappe.db.get_value("Opportunity", opp, "customer_address"), address)


class TestLeadToCustomer(FrappeTestCase):
    """Regression guards, not new coverage — every one of these passed unchanged.

    Written expecting a bug that is not there. `_make_customer` does name the lead's
    Contact and Address on the Customer without linking them to it, and
    `Customer.create_primary_contact` does bail out whenever `lead_name` is set — but
    `Customer.on_update` -> `link_address_and_contact` extends the Dynamic Links from
    the Lead, Opportunity *and* Prospect onto the new Customer, which repairs both.

    They stay as the boundary of what was checked: the handover deliberately does not
    hook Customer, and these are the assertions that would have justified doing so.
    What *is* wrong at this stage is not the mapping:
    only 18 of 887 customers on this site carry any lead back-link, because the
    conversion is barely used. That is a missing step, not a broken mapper.
    """

    def _a_customer(self):
        from erpnext.crm.doctype.lead.lead import make_customer

        lead, contact, address = _a_lead()
        doc = _fill_required(make_customer(lead))
        doc.insert()
        return doc.reload() or doc, lead, contact, address

    def test_the_primary_contact_is_linked_to_the_customer(self):
        customer, _, contact, _ = self._a_customer()
        self.assertIn(contact, _links_to("Contact", "Customer", customer.name))

    def test_the_primary_address_is_linked_to_the_customer(self):
        customer, _, _, address = self._a_customer()
        self.assertIn(address, _links_to("Address", "Customer", customer.name))

    def test_the_customer_names_a_primary_contact_it_owns(self):
        customer, _, _, _ = self._a_customer()
        named = customer.customer_primary_contact
        self.assertTrue(named, "customer_primary_contact was left empty")
        self.assertIn(named, _links_to("Contact", "Customer", customer.name))

    def test_the_customer_names_a_primary_address_it_owns(self):
        customer, _, _, _ = self._a_customer()
        named = customer.customer_primary_address
        self.assertTrue(named, "customer_primary_address was left empty")
        self.assertIn(named, _links_to("Address", "Customer", customer.name))

    def test_the_lead_back_link_survives(self):
        """`api/pipeline.py` joins lead-to-customer velocity on this field."""
        customer, lead, _, _ = self._a_customer()
        self.assertEqual(customer.lead_name, lead)


class TestItLeavesThingsAlone(FrappeTestCase):
    """The hook sits in the insert path of every Opportunity on this site."""

    def test_a_value_already_set_is_not_overwritten(self):
        lead, _, _ = _a_lead()
        prospect = A.crm_lead_to_prospect(lead)["prospect"]
        _add_contact("Prospect", prospect, f"Probe Buyer {prospect}",
                     f"probe-keep-{prospect}@example.com".replace(" ", "-"), "+254700555666")
        import json
        opp = A.crm_prospect_to_opportunity(prospect, json.dumps({
            "contact_email": "chosen-by-the-salesperson@example.com",
        }))["name"]
        self.assertEqual(frappe.db.get_value("Opportunity", opp, "contact_email"),
                         "chosen-by-the-salesperson@example.com")

    def test_a_customer_with_no_crm_source_is_untouched(self):
        doc = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": f"Probe Direct {frappe.generate_hash(length=8)}",
            "customer_type": "Company",
        })
        _fill_required(doc)
        doc.insert()
        doc.reload()
        self.assertFalse(doc.lead_name)
        self.assertFalse(doc.customer_primary_contact)
        self.assertEqual(_links_to("Contact", "Customer", doc.name), set())
        self.assertEqual(_links_to("Address", "Customer", doc.name), set())

    def test_an_absent_field_is_skipped_rather_than_raising(self):
        doc = frappe.new_doc("Opportunity")
        handover.set_if_empty(doc, "not_a_field_on_opportunity", "value")
        self.assertIsNone(doc.get("not_a_field_on_opportunity"))

    def test_a_source_that_no_longer_exists_does_not_block_the_save(self):
        """A carry-over failure must never stop a document being created."""
        doc = frappe.new_doc("Opportunity")
        doc.opportunity_from = "Prospect"
        doc.party_name = "Prospect-that-was-deleted"
        handover.before_insert(doc)  # must return, not throw
