"""Tests for moving a record along the pipeline.

The write module with the most ways to go wrong, so the emphasis is the same as
`test_leads.py`'s and pushed harder.

**The chain holds end to end.** One test walks Lead -> Opportunity -> Quotation ->
Customer and asserts each link, because the hops passing individually does not
prove the chain does: the quotation route only works if the opportunity carried
its party across, and the customer route only works if the quotation is addressed
to the lead.

**A failed hop leaves the source alone.** Insert is the last step in `_advance`,
so a bad item line must throw with the source untouched and no orphan document.
Asserted per rejection path rather than once.

**The duplicate guard is ours, not ERPNext's.** `lead.make_customer` will happily
create a second customer for the same lead; ERPNext's Lead form avoids it only by
hiding the button. The guard is therefore tested directly.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import advance as A
from upande_crm.tests.pipeline_fixtures import an_item, save_lead


def _quote_payload(item, **over):
    body = {"items": [{"item_code": item, "qty": 1200, "rate": 42}]}
    body.update(over)
    return json.dumps(body)


class TestTheChain(FrappeTestCase):
    """Lead -> Opportunity -> Quotation -> Customer, in one walk."""

    def test_a_lead_reaches_a_customer_through_every_document(self):
        item = an_item()
        if not item:
            self.skipTest("no items on this site")
        lead = save_lead()["name"]

        opp = A.crm_lead_to_opportunity(lead, json.dumps({
            "items": [{"item_code": item, "qty": 1200, "rate": 42}],
        }))
        self.assertTrue(frappe.db.exists("Opportunity", opp["name"]))
        self.assertEqual(
            frappe.db.get_value("Opportunity", opp["name"], "party_name"), lead)

        quote = A.crm_opportunity_to_quotation(opp["name"], json.dumps({}))
        self.assertTrue(frappe.db.exists("Quotation", quote["name"]))
        row = frappe.db.get_value(
            "Quotation", quote["name"],
            ["quotation_to", "party_name", "opportunity", "docstatus"], as_dict=True)
        self.assertEqual(row.quotation_to, "Lead")
        self.assertEqual(row.party_name, lead)
        self.assertEqual(row.opportunity, opp["name"])
        # Drafts, deliberately: nothing here submits.
        self.assertEqual(row.docstatus, 0)
        # The varieties survive the hop, which is what the demand card reads.
        self.assertEqual(quote["items"], 1)

        cust = A.crm_quotation_to_customer(quote["name"])
        self.assertTrue(frappe.db.exists("Customer", cust["name"]))
        self.assertEqual(frappe.db.get_value("Customer", cust["name"], "lead_name"), lead)
        self.assertFalse(cust["existing"])

    def test_resolving_the_same_quotation_twice_returns_the_same_customer(self):
        item = an_item()
        if not item:
            self.skipTest("no items on this site")
        lead = save_lead()["name"]
        quote = A.crm_lead_to_quotation(lead, _quote_payload(item))
        first = A.crm_quotation_to_customer(quote["name"])
        second = A.crm_quotation_to_customer(quote["name"])
        self.assertEqual(first["name"], second["name"])
        # The second call has to say it found rather than made one.
        self.assertTrue(second["existing"])


class TestQuotationHops(FrappeTestCase):
    def test_a_lead_can_be_quoted_before_it_is_a_customer(self):
        item = an_item()
        if not item:
            self.skipTest("no items on this site")
        lead = save_lead()["name"]
        out = A.crm_lead_to_quotation(lead, _quote_payload(item))
        row = frappe.db.get_value("Quotation", out["name"],
                                  ["quotation_to", "party_name"], as_dict=True)
        self.assertEqual(row.quotation_to, "Lead")
        self.assertEqual(row.party_name, lead)
        self.assertFalse(frappe.db.exists("Customer", {"lead_name": lead}),
                         "quoting a lead must not create a customer")

    def test_a_quotation_needs_at_least_one_variety(self):
        lead = save_lead()["name"]
        with self.assertRaises(frappe.ValidationError):
            A.crm_lead_to_quotation(lead, json.dumps({}))

    def test_the_chained_route_creates_both_documents_and_links_them(self):
        item = an_item()
        if not item:
            self.skipTest("no items on this site")
        lead = save_lead()["name"]
        out = A.crm_lead_to_quotation(lead, _quote_payload(item), with_opportunity=1)
        self.assertTrue(out.get("opportunity"))
        self.assertTrue(frappe.db.exists("Opportunity", out["opportunity"]))
        self.assertEqual(
            frappe.db.get_value("Quotation", out["name"], "opportunity"), out["opportunity"])
        # The mapper carries the opportunity's lines across; they must not double.
        rows = frappe.get_all("Quotation Item", filters={"parent": out["name"]})
        self.assertEqual(len(rows), 1)

    def test_valid_till_is_carried_and_validated(self):
        item = an_item()
        if not item:
            self.skipTest("no items on this site")
        lead = save_lead()["name"]
        out = A.crm_lead_to_quotation(lead, _quote_payload(item, valid_till="2027-01-31"))
        self.assertEqual(
            str(frappe.db.get_value("Quotation", out["name"], "valid_till")), "2027-01-31")

        other = save_lead()["name"]
        with self.assertRaises(frappe.ValidationError):
            A.crm_lead_to_quotation(other, _quote_payload(item, valid_till="not-a-date"))


class TestCustomerHops(FrappeTestCase):
    def test_a_lead_becomes_a_customer(self):
        lead = save_lead()["name"]
        out = A.crm_lead_to_customer(lead, json.dumps({}))
        self.assertTrue(frappe.db.exists("Customer", out["name"]))
        self.assertEqual(frappe.db.get_value("Customer", out["name"], "lead_name"), lead)

    def test_a_second_customer_for_the_same_lead_is_refused(self):
        # ERPNext's mapper would create one; the guard is ours.
        lead = save_lead()["name"]
        A.crm_lead_to_customer(lead, json.dumps({}))
        with self.assertRaises(frappe.ValidationError):
            A.crm_lead_to_customer(lead, json.dumps({}))
        self.assertEqual(frappe.db.count("Customer", {"lead_name": lead}), 1)

    def test_a_prospect_becomes_a_customer(self):
        lead = save_lead()["name"]
        prospect = A.crm_lead_to_prospect(lead)["prospect"]
        out = A.crm_prospect_to_customer(prospect, json.dumps({}))
        self.assertTrue(frappe.db.exists("Customer", out["name"]))
        self.assertEqual(
            frappe.db.get_value("Customer", out["name"], "prospect_name"), prospect)

    def test_an_opportunity_becomes_a_customer(self):
        lead = save_lead()["name"]
        opp = A.crm_lead_to_opportunity(lead, json.dumps({}))["name"]
        out = A.crm_opportunity_to_customer(opp, json.dumps({}))
        self.assertTrue(frappe.db.exists("Customer", out["name"]))


class TestTheRouteTable(FrappeTestCase):
    def test_every_mapper_in_the_table_resolves(self):
        # A typo in a dotted path would otherwise only surface when a user
        # pressed the button.
        for (src, target), hop in A.HOPS.items():
            with self.subTest(hop=f"{src}->{target}"):
                self.assertTrue(callable(frappe.get_attr(hop.mapper)))

    def test_a_route_that_does_not_exist_is_refused(self):
        lead = save_lead()["name"]
        with self.assertRaises(frappe.ValidationError):
            A._advance("Lead", lead, "Sales Order")

    def test_a_missing_source_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            A.crm_lead_to_opportunity("Lead-does-not-exist")
        with self.assertRaises(frappe.ValidationError):
            A.crm_prospect_to_opportunity("Prospect-does-not-exist")
        with self.assertRaises(frappe.ValidationError):
            A.crm_lead_to_quotation("Lead-does-not-exist")
        with self.assertRaises(frappe.ValidationError):
            A.crm_lead_to_customer("Lead-does-not-exist")

    def test_the_header_allowlist_drops_protected_fields(self):
        lead = save_lead()["name"]
        out = A.crm_lead_to_opportunity(lead, json.dumps({
            "owner": "Guest", "docstatus": 1, "party_name": "somebody-else",
        }))
        doc = frappe.db.get_value("Opportunity", out["name"],
                                  ["owner", "docstatus", "party_name"], as_dict=True)
        self.assertNotEqual(doc.owner, "Guest")
        self.assertEqual(doc.docstatus, 0)
        self.assertEqual(doc.party_name, lead)


class TestConversionToProspect(FrappeTestCase):
    def test_lead_becomes_a_prospect(self):
        r = save_lead()
        out = A.crm_lead_to_prospect(r["name"])
        self.assertTrue(out["created"])
        self.assertTrue(frappe.db.exists("Prospect", out["prospect"]))
        self.assertTrue(frappe.db.exists("Prospect Lead",
                                         {"parent": out["prospect"], "lead": r["name"]}))

    def test_a_second_prospect_with_the_same_company_is_refused(self):
        r = save_lead()
        A.crm_lead_to_prospect(r["name"])
        with self.assertRaises(frappe.ValidationError):
            A.crm_lead_to_prospect(r["name"])


class TestConversionToOpportunity(FrappeTestCase):
    def test_lead_becomes_an_opportunity(self):
        r = save_lead()
        out = A.crm_lead_to_opportunity(r["name"], json.dumps({"sales_stage": ""}))
        self.assertTrue(frappe.db.exists("Opportunity", out["name"]))
        self.assertEqual(
            frappe.db.get_value("Opportunity", out["name"], "party_name"), r["name"])

    def test_item_lines_reach_the_opportunity(self):
        item = an_item()
        if not item:
            self.skipTest("no items on this site")
        r = save_lead()
        out = A.crm_lead_to_opportunity(r["name"], json.dumps({
            "items": [{"item_code": item, "qty": 1200, "rate": 42}],
        }))
        self.assertEqual(out["items"], 1)
        rows = frappe.get_all("Opportunity Item", filters={"parent": out["name"]},
                              fields=["item_code", "qty"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].item_code, item)
        self.assertEqual(rows[0].qty, 1200)


class TestAFailedHopLeavesTheSourceAlone(FrappeTestCase):
    """The property that matters most: no half-advanced state."""

    def _assert_lead_survives_intact(self, payload, hop="opportunity"):
        r = save_lead()
        before = frappe.db.get_value("Lead", r["name"], ["status", "modified"], as_dict=True)
        opps_before = frappe.db.count("Opportunity", {"party_name": r["name"]})
        quotes_before = frappe.db.count("Quotation", {"party_name": r["name"]})
        with self.assertRaises(frappe.ValidationError):
            if hop == "opportunity":
                A.crm_lead_to_opportunity(r["name"], json.dumps(payload))
            else:
                A.crm_lead_to_quotation(r["name"], json.dumps(payload))
        after = frappe.db.get_value("Lead", r["name"], ["status", "modified"], as_dict=True)
        self.assertEqual(before.status, after.status)
        self.assertEqual(frappe.db.count("Opportunity", {"party_name": r["name"]}), opps_before)
        self.assertEqual(frappe.db.count("Quotation", {"party_name": r["name"]}), quotes_before)

    def test_an_unknown_item_leaves_the_lead_alone(self):
        self._assert_lead_survives_intact({"items": [{"item_code": "NOT-AN-ITEM", "qty": 1}]})

    def test_a_zero_quantity_leaves_the_lead_alone(self):
        item = an_item()
        if not item:
            self.skipTest("no items on this site")
        self._assert_lead_survives_intact({"items": [{"item_code": item, "qty": 0}]})

    def test_a_bad_closing_date_leaves_the_lead_alone(self):
        self._assert_lead_survives_intact({"expected_closing": "not-a-date"})

    def test_an_unknown_item_leaves_the_lead_unquoted(self):
        self._assert_lead_survives_intact(
            {"items": [{"item_code": "NOT-AN-ITEM", "qty": 1}]}, hop="quotation")


class TestItemValidation(FrappeTestCase):
    def test_rejects_more_lines_than_the_cap(self):
        item = an_item()
        if not item:
            self.skipTest("no items on this site")
        rows = [{"item_code": item, "qty": 1}] * (A.MAX_ITEMS + 1)
        with self.assertRaises(frappe.ValidationError):
            A._items({"items": rows})

    def test_rejects_malformed_lines(self):
        for bad in ("not json", {"items": "nope"}, {"items": [1, 2]}):
            with self.assertRaises(frappe.ValidationError):
                A._items(bad if isinstance(bad, dict) else {"items": bad})

    def test_no_lines_is_not_an_error(self):
        self.assertEqual(A._items({}), [])


class TestRoutesEndpoint(FrappeTestCase):
    def test_routes_are_offered_per_source_doctype(self):
        routes = A.crm_advance_routes()
        self.assertIsInstance(routes, dict)
        # Administrator can create all of them, so every source should be offered.
        self.assertIn("Customer", routes.get("Lead", []))
        self.assertIn("Quotation", routes.get("Opportunity", []))
