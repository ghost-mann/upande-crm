"""Tests for lead capture and conversion.

A write module, so these lean on the same principle as `test_calls.py`: every
rejection path is asserted, because a lead that appears to save and does not is
the worst outcome here.

Two properties get the most attention.

**The allowlist holds.** A payload carrying `owner` or `docstatus` must have them
dropped, not written. The allowlist is partly computed at runtime — it widens to
whatever fields this site has made mandatory — so "it widens correctly" and "it
still refuses the protected fields" are separate assertions.

**A failed conversion leaves the source alone.** Building an Opportunity with a
bad item line must not half-convert the Lead.
"""

import itertools
import json

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import leads as L


def _an_item():
    rows = frappe.get_all("Item", filters={"disabled": 0}, pluck="name", limit=1)
    return rows[0] if rows else None


# A Data field's `options` carries its format. Filling one with free text fails
# validation — `email_id` is mandatory here and rejected anything without an @.
FORMATTED = {
    "Email": "probe-test@example.com",
    "Phone": "+254700111222",
    "URL": "https://example.com",
}


def _required_values():
    """Plausible values for whatever this site insists on, so a create can succeed.

    Read from the meta rather than hardcoded: the install these tests run against
    has made eleven Lead fields mandatory, two of them custom, and a fixture that
    named them would break on the next site.
    """
    out = {}
    for f in L._required_lead_fields():
        name, ftype, opts = f["fieldname"], f["fieldtype"], f["options"]
        if f.get("default"):
            out[name] = f["default"]
        elif ftype == "Link":
            rows = frappe.get_all(opts, pluck="name", limit=1) if opts else []
            if rows:
                out[name] = rows[0]
        elif ftype == "Select":
            choices = [o for o in str(opts or "").split("\n") if o]
            if choices:
                out[name] = choices[0]
        elif ftype in ("Int", "Float", "Currency", "Percent"):
            out[name] = 1
        elif opts in FORMATTED:
            out[name] = FORMATTED[opts]
        elif "email" in name:
            out[name] = FORMATTED["Email"]
        elif "mobile" in name or "phone" in name or "whatsapp" in name:
            out[name] = FORMATTED["Phone"]
        else:
            out[name] = f"probe-{name}"
    return out


# Lead enforces a unique email, and Prospect is named by its company, so two
# fixtures built from the same constants collide with each other rather than with
# anything real. Every payload gets its own identity.
_seq = itertools.count()


def _lead_payload(**over):
    # Site requirements first, then this module's own identity fields on top, so a
    # generated placeholder never displaces the name the test is asserting on.
    n = next(_seq)
    body = _required_values()
    body.update({
        "lead_name": f"Probe Buyer {n}",
        "company_name": f"Probe Florals Test {n} Ltd",
        "email_id": f"probe-test-{n}@example.com",
        "status": "Lead",
    })
    body.update(over)
    return body


def _save(**over):
    return L.crm_lead_save(json.dumps(_lead_payload(**over)))


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


class TestConversion(FrappeTestCase):
    def test_lead_becomes_a_prospect(self):
        r = _save()
        out = L.crm_lead_to_prospect(r["name"])
        self.assertTrue(out["created"])
        self.assertTrue(frappe.db.exists("Prospect", out["prospect"]))
        self.assertTrue(frappe.db.exists("Prospect Lead",
                                         {"parent": out["prospect"], "lead": r["name"]}))

    def test_a_second_prospect_with_the_same_company_is_refused(self):
        r = _save()
        L.crm_lead_to_prospect(r["name"])
        with self.assertRaises(frappe.ValidationError):
            L.crm_lead_to_prospect(r["name"])

    def test_lead_becomes_an_opportunity(self):
        r = _save()
        out = L.crm_lead_to_opportunity(r["name"], json.dumps({"sales_stage": ""}))
        self.assertTrue(frappe.db.exists("Opportunity", out["name"]))
        self.assertEqual(out["party_name"], r["name"])
        self.assertEqual(out["opportunity_from"], "Lead")

    def test_item_lines_reach_the_opportunity(self):
        item = _an_item()
        if not item:
            self.skipTest("no items on this site")
        r = _save()
        out = L.crm_lead_to_opportunity(r["name"], json.dumps({
            "items": [{"item_code": item, "qty": 1200, "rate": 42}],
        }))
        self.assertEqual(out["items"], 1)
        rows = frappe.get_all("Opportunity Item", filters={"parent": out["name"]},
                              fields=["item_code", "qty"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].item_code, item)
        self.assertEqual(rows[0].qty, 1200)

    def test_a_missing_source_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            L.crm_lead_to_opportunity("Lead-does-not-exist")
        with self.assertRaises(frappe.ValidationError):
            L.crm_prospect_to_opportunity("Prospect-does-not-exist")


class TestFailedConversionLeavesTheLeadAlone(FrappeTestCase):
    """The property that matters most: no half-converted state."""

    def _assert_lead_survives_intact(self, payload):
        r = _save()
        before = frappe.db.get_value("Lead", r["name"], ["status", "modified"], as_dict=True)
        opps_before = frappe.db.count("Opportunity", {"party_name": r["name"]})
        with self.assertRaises(frappe.ValidationError):
            L.crm_lead_to_opportunity(r["name"], json.dumps(payload))
        after = frappe.db.get_value("Lead", r["name"], ["status", "modified"], as_dict=True)
        self.assertEqual(before.status, after.status)
        self.assertEqual(frappe.db.count("Opportunity", {"party_name": r["name"]}), opps_before)

    def test_an_unknown_item_leaves_the_lead_alone(self):
        self._assert_lead_survives_intact({"items": [{"item_code": "NOT-AN-ITEM", "qty": 1}]})

    def test_a_zero_quantity_leaves_the_lead_alone(self):
        item = _an_item()
        if not item:
            self.skipTest("no items on this site")
        self._assert_lead_survives_intact({"items": [{"item_code": item, "qty": 0}]})

    def test_a_bad_closing_date_leaves_the_lead_alone(self):
        self._assert_lead_survives_intact({"expected_closing": "not-a-date"})


class TestItemValidation(FrappeTestCase):
    def test_rejects_more_lines_than_the_cap(self):
        item = _an_item()
        if not item:
            self.skipTest("no items on this site")
        rows = [{"item_code": item, "qty": 1}] * (L.MAX_ITEMS + 1)
        with self.assertRaises(frappe.ValidationError):
            L._items({"items": rows})

    def test_rejects_malformed_lines(self):
        for bad in ("not json", {"items": "nope"}, {"items": [1, 2]}):
            with self.assertRaises(frappe.ValidationError):
                L._items(bad if isinstance(bad, dict) else {"items": bad})

    def test_no_lines_is_not_an_error(self):
        self.assertEqual(L._items({}), [])


class TestFormOptions(FrappeTestCase):
    def test_returns_every_key_the_dialogs_read(self):
        o = L.crm_lead_form_options()
        for key in ("sources", "territories", "industries", "market_segments",
                    "sales_stages", "opportunity_types", "lead_statuses", "users",
                    "required_fields", "can_create_lead"):
            self.assertIn(key, o)

    def test_flower_search_ranks_word_boundary_matches_first(self):
        # "rose" matches "Dextrose" as a substring; a picker that offers medicine
        # to a flower farm looks broken even though the query was obeyed.
        rows = L.crm_flower_search("rose", 10)
        for r in rows[:3]:
            self.assertNotIn("dextrose", r["label"].lower())

    def test_flower_search_degrades_on_an_empty_query(self):
        self.assertIsInstance(L.crm_flower_search("", 5), list)
