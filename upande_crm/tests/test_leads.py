"""Tests for lead capture.

A write module, so these lean on the same principle as `test_calls.py`: every
rejection path is asserted, because a lead that appears to save and does not is
the worst outcome here.

**The allowlist holds.** A payload carrying `owner` or `docstatus` must have them
dropped, not written. The allowlist is partly computed at runtime — it widens to
whatever fields this site has made mandatory — so "it widens correctly" and "it
still refuses the protected fields" are separate assertions.

Conversion moved to `api/advance.py`; its tests moved with it, to
`test_advance.py`. What used to live here as `TestFailedConversionLeavesTheLeadAlone`
is now `TestAFailedHopLeavesTheSourceAlone` there.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import leads as L
from upande_crm.tests.pipeline_fixtures import lead_payload as _lead_payload
from upande_crm.tests.pipeline_fixtures import required_values as _required_values
from upande_crm.tests.pipeline_fixtures import save_lead as _save


class TestAllowlist(FrappeTestCase):
    def test_protected_fields_are_dropped_not_written(self):
        r = _save(owner="Guest", docstatus=1, name=None)
        doc = frappe.get_doc("Lead", r["name"])
        self.assertNotEqual(doc.owner, "Guest")
        self.assertEqual(doc.docstatus, 0)

    def test_an_unknown_field_is_ignored(self):
        # Not an error — a stale client sending an extra key should still save.
        r = L.crm_lead_save(json.dumps(_lead_payload(no_such_field_here="x")))
        self.assertTrue(r["name"])

    def test_the_allowlist_widens_to_this_sites_mandatory_fields(self):
        required = {f["fieldname"] for f in L._required_lead_fields()}
        self.assertTrue(required <= L._lead_fields(),
                        "a mandatory field is not writable, so a lead cannot be created")

    def test_protected_fields_stay_out_however_the_meta_changes(self):
        self.assertFalse(L._lead_fields() & L.PROTECTED_FIELDS)

    def test_required_fields_never_include_layout_elements(self):
        for f in L._required_lead_fields():
            self.assertNotIn(f["fieldtype"], L.NON_INPUT_FIELDTYPES)


class TestLeadSave(FrappeTestCase):
    def test_creates_a_lead(self):
        payload = _lead_payload()
        r = L.crm_lead_save(json.dumps(payload))
        self.assertTrue(frappe.db.exists("Lead", r["name"]))
        self.assertEqual(r["company_name"], payload["company_name"])

    def test_updates_an_existing_lead(self):
        r = _save()
        again = L.crm_lead_save(json.dumps({"name": r["name"], "company_name": "Renamed Ltd"}))
        self.assertEqual(again["name"], r["name"])
        self.assertEqual(frappe.db.get_value("Lead", r["name"], "company_name"), "Renamed Ltd")

    def test_rejects_a_lead_with_no_name_and_no_company(self):
        body = _required_values()
        body.pop("company_name", None)
        body.pop("first_name", None)
        body.pop("last_name", None)
        with self.assertRaises(frappe.ValidationError):
            L.crm_lead_save(json.dumps({**body, "email_id": "x@y.z"}))

    def test_rejects_a_malformed_payload(self):
        with self.assertRaises(frappe.ValidationError):
            L.crm_lead_save("not json")
        with self.assertRaises(frappe.ValidationError):
            L.crm_lead_save("[1, 2, 3]")


class TestFormOptions(FrappeTestCase):
    def test_returns_every_key_the_dialogs_read(self):
        o = L.crm_lead_form_options()
        for key in ("sources", "territories", "industries", "market_segments",
                    "sales_stages", "opportunity_types", "lead_statuses", "users",
                    "required_fields", "can_create_lead", "order_types",
                    "customer_groups", "can_create_quotation", "can_create_customer"):
            self.assertIn(key, o)

    def test_flower_search_ranks_word_boundary_matches_first(self):
        # "rose" matches "Dextrose" as a substring; a picker that offers medicine
        # to a flower farm looks broken even though the query was obeyed.
        rows = L.crm_flower_search("rose", 10)
        for r in rows[:3]:
            self.assertNotIn("dextrose", r["label"].lower())

    def test_flower_search_degrades_on_an_empty_query(self):
        self.assertIsInstance(L.crm_flower_search("", 5), list)
