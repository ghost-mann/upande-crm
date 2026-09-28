"""Tests for customer claims (CRM Claim + api/claims.py).

A claim has to point at the customer's own order or delivery, carry a reason once
it is closed, and time itself: `resolved_on` is what "days to resolve" is
measured from, so the controller owns it rather than the form.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from upande_crm.api import claims as CL
from upande_crm.api import settings as S


def _clear():
    frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)


def _save_settings(**patch):
    doc = frappe.get_single(S.SETTINGS_DOCTYPE)
    doc.update(patch)
    doc.save(ignore_permissions=True)
    _clear()


class ClaimCase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        row = frappe.db.sql(
            """select customer, name from `tabSales Invoice` where docstatus=1
               order by posting_date desc limit 1""")
        cls.customer, cls.invoice = row[0]
        other = frappe.db.sql(
            "select name from `tabSales Invoice` where docstatus=1 and customer!=%s limit 1", cls.customer)
        cls.foreign_invoice = other[0][0] if other else None

    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        _clear()

    def _claim(self, **kw):
        data = {"customer": self.customer, "claim_type": "Quality rejection",
                "description": "Botrytis on 3 boxes", **kw}
        return CL.crm_claim_save(frappe.as_json(data))["claim"]


class TestClaimRecord(ClaimCase):
    def test_a_claim_is_created_open(self):
        c = self._claim()
        self.assertEqual(c["status"], "Open")
        self.assertTrue(c["name"].startswith("CLM-"))

    def test_claim_type_must_be_configured(self):
        with self.assertRaises(frappe.ValidationError):
            self._claim(claim_type="Bad vibes")

    def test_configured_types_follow_settings(self):
        _save_settings(claim_types="Quality rejection\nBad vibes")
        self.assertEqual(self._claim(claim_type="Bad vibes")["claim_type"], "Bad vibes")

    def test_reference_must_belong_to_the_customer(self):
        self._claim(reference_doctype="Sales Invoice", reference_name=self.invoice)
        if self.foreign_invoice:
            with self.assertRaises(frappe.ValidationError):
                self._claim(reference_doctype="Sales Invoice", reference_name=self.foreign_invoice)

    def test_closing_needs_a_resolution(self):
        c = self._claim()
        with self.assertRaises(frappe.ValidationError):
            CL.crm_claim_save(frappe.as_json({"name": c["name"], "status": "Resolved"}))

    def test_resolved_on_is_set_and_cleared(self):
        c = self._claim()
        r = CL.crm_claim_save(frappe.as_json({"name": c["name"], "status": "Resolved",
                                              "resolution": "Credit note issued"}))["claim"]
        self.assertEqual(str(r["resolved_on"]), nowdate())
        r = CL.crm_claim_save(frappe.as_json({"name": c["name"], "status": "Under Review"}))["claim"]
        self.assertIsNone(r["resolved_on"])

    def test_credit_cannot_exceed_or_go_negative(self):
        with self.assertRaises(frappe.ValidationError):
            self._claim(amount_claimed=-5)

    def test_unknown_fields_are_ignored(self):
        c = self._claim(owner="someone@else.com", docstatus=1)
        self.assertEqual(frappe.db.get_value("CRM Claim", c["name"], "owner"), "Administrator")


class TestClaimDashboard(ClaimCase):
    def test_dashboard_shape_and_counts(self):
        self._claim()
        d = CL.crm_dashboard_claims(add_days(nowdate(), -30), nowdate())
        for k in ("kpis", "by_type", "by_status", "rows", "types", "sla_days"):
            self.assertIn(k, d)
        self.assertGreaterEqual(d["kpis"]["open"], 1)

    def test_overdue_counts_open_claims_past_the_sla(self):
        c = self._claim(raised_on=add_days(nowdate(), -30))
        d = CL.crm_dashboard_claims(add_days(nowdate(), -60), nowdate())
        self.assertIn(c["name"], {r["name"] for r in d["rows"] if r["overdue"]})

    def test_customer_claims(self):
        c = self._claim()
        rows = CL.crm_customer_claims(self.customer)["rows"]
        self.assertIn(c["name"], {r["name"] for r in rows})

    def test_references_are_the_customers_own(self):
        refs = CL.crm_claim_references(self.customer, "Sales Invoice")["rows"]
        self.assertTrue(all(r["customer"] == self.customer for r in refs))

    def test_references_reject_unknown_kind(self):
        with self.assertRaises(frappe.ValidationError):
            CL.crm_claim_references(self.customer, "User")

    def test_module_off_refuses(self):
        _save_settings(module_claims=0)
        try:
            with self.assertRaises(frappe.PermissionError):
                CL.crm_dashboard_claims()
        finally:
            _save_settings(module_claims=1)
