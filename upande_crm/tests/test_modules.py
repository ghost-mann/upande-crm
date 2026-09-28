"""Tests for the module switches on Upande CRM Settings.

A switch that only hides a button is decoration: the property that matters is
that a switched-off module's endpoints refuse to answer. That is asserted in
`TestEnforcement`, against the same endpoint map the decorator is applied from
(`test_modules_gated.GATED`), so adding a gated endpoint without a test is not
possible without editing that map.
"""

import inspect

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm import modules as M
from upande_crm.api import settings as S


def _clear():
    frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)


def _save(**patch):
    doc = frappe.get_single(S.SETTINGS_DOCTYPE)
    doc.update(patch)
    doc.save(ignore_permissions=True)
    _clear()


class TestRegistry(FrappeTestCase):
    def tearDown(self):
        _clear()

    def test_every_module_field_is_on_the_doctype(self):
        meta = frappe.get_meta(S.SETTINGS_DOCTYPE)
        for m in M.MODULES:
            self.assertTrue(meta.has_field(m.field), m.field)

    def test_every_module_field_has_a_default(self):
        for m in M.MODULES:
            self.assertIn(m.field, S.DEFAULTS)

    def test_keys_and_sections_are_unique(self):
        keys = [m.key for m in M.MODULES]
        self.assertEqual(len(keys), len(set(keys)))
        secs = [s for m in M.MODULES for s in m.sections]
        self.assertEqual(len(secs), len(set(secs)))

    def test_available_modules_default_on_placeholders_off(self):
        for m in M.MODULES:
            self.assertEqual(S.DEFAULTS[m.field], 1 if m.available else 0, m.key)

    def test_unavailable_module_is_never_enabled(self):
        _save(module_claims=1)
        self.assertFalse(M.is_enabled("claims"))

    def test_switching_off_is_reflected(self):
        _save(module_calls=0)
        self.assertFalse(M.is_enabled("calls"))
        self.assertFalse(M.enabled_map()["calls"])
        self.assertTrue(M.enabled_map()["leads"])

    def test_whatsapp_uses_its_existing_field(self):
        _save(whatsapp_enabled=0)
        self.assertFalse(M.is_enabled("wa"))

    def test_unknown_key_is_disabled(self):
        self.assertFalse(M.is_enabled("nope"))

    def test_settings_payload_carries_modules(self):
        frappe.set_user("Administrator")
        out = S.crm_settings()
        self.assertEqual(set(out["modules"]), {m.key for m in M.MODULES})
        self.assertTrue(all(r["label"] and r["help"] for r in out["module_meta"]))

    def test_custpage_tabs_default_lists_all_tabs(self):
        self.assertEqual(S.parse_lines(S.DEFAULTS["custpage_tabs"]), list(M.CUSTPAGE_TABS))

    def test_custpage_tabs_reject_unknown_tab(self):
        with self.assertRaises(frappe.ValidationError):
            _save(custpage_tabs="overview\nfinances")

    def test_custpage_default_tab_must_be_listed(self):
        with self.assertRaises(frappe.ValidationError):
            _save(custpage_tabs="overview\norders", custpage_default_tab="pricing")


class TestBackfillPatch(FrappeTestCase):
    """New Check fields on an already-saved Single read as 0, not their default.

    Without the backfill every module on an existing site would switch itself
    off the first time anyone saved settings.
    """

    def tearDown(self):
        _clear()

    def _unset(self, field):
        frappe.db.sql(
            "delete from `tabSingles` where doctype=%s and field=%s", (S.SETTINGS_DOCTYPE, field)
        )

    def test_unset_fields_are_backfilled_to_their_default(self):
        from upande_crm.patches.backfill_module_switches import execute

        self._unset("module_leads")
        self._unset("module_claims")
        execute()
        _clear()
        self.assertEqual(frappe.db.get_single_value(S.SETTINGS_DOCTYPE, "module_leads"), 1)
        self.assertEqual(frappe.db.get_single_value(S.SETTINGS_DOCTYPE, "module_claims"), 0)

    def test_a_saved_choice_is_left_alone(self):
        from upande_crm.patches.backfill_module_switches import execute

        frappe.db.set_single_value(S.SETTINGS_DOCTYPE, "module_calls", 0)
        execute()
        _clear()
        self.assertEqual(frappe.db.get_single_value(S.SETTINGS_DOCTYPE, "module_calls"), 0)
