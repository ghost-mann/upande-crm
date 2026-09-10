"""The demo seeder's vocabulary must match the doctypes it writes to.

This exists because the same mistake happened twice while writing
`demo_extras`: invented Select values ("Cold Chain", "Broken stems") lost 37 of
48 claims, and then a truncated read of the option list lost 12 more to
"Other " when the real option is "Other disease / disorder". Both runs reported
success, because the inserts were wrapped in a bare except.

Checking the constants against the live meta is far cheaper than seeding, and
catches the failure at its cause rather than as a missing row somewhere.
"""

import unittest

import frappe

from upande_crm.demo_extras import (
    _CATEGORY_WEIGHTS,
    _CLAIM_TYPES,
    _REASONS_BY_CATEGORY,
    _pick_reason,
)


def _options(doctype, fieldname):
    if not frappe.db.exists("DocType", doctype):
        return None
    field = frappe.get_meta(doctype).get_field(fieldname)
    if not field or not field.options:
        return None
    return [o for o in field.options.split("\n")]


class TestClaimVocabulary(unittest.TestCase):
    def test_every_category_is_a_real_option(self):
        options = _options("Customer Feedback Item", "reason_category")
        if options is None:
            self.skipTest("Customer Feedback Item not on this site")
        for category in _REASONS_BY_CATEGORY:
            self.assertIn(category, options, f"invented reason_category {category!r}")

    def test_every_reason_is_a_real_option(self):
        options = _options("Customer Feedback Item", "reason")
        if options is None:
            self.skipTest("Customer Feedback Item not on this site")
        for category, reasons in _REASONS_BY_CATEGORY.items():
            for reason in reasons:
                self.assertIn(reason, options, f"invented reason {reason!r} under {category}")

    def test_claim_types_are_real_options(self):
        options = _options("Customer Feedback", "claim_type")
        if options is None:
            self.skipTest("Customer Feedback not on this site")
        for t in _CLAIM_TYPES:
            self.assertIn(t, options, f"invented claim_type {t!r}")

    def test_weights_cover_every_category(self):
        """A category with reasons but no weight would never be picked."""
        weighted = {c for c, _ in _CATEGORY_WEIGHTS}
        self.assertEqual(weighted, set(_REASONS_BY_CATEGORY))

    def test_picker_only_returns_valid_pairs(self):
        cats = _options("Customer Feedback Item", "reason_category")
        reasons = _options("Customer Feedback Item", "reason")
        if cats is None or reasons is None:
            self.skipTest("Customer Feedback Item not on this site")
        for _ in range(200):
            variety, category, reason = _pick_reason()
            self.assertTrue(variety)
            self.assertIn(category, cats)
            self.assertIn(reason, reasons)
            self.assertIn(reason, _REASONS_BY_CATEGORY[category])


class TestDemoOwnership(unittest.TestCase):
    """The demo belongs to named staff, not to whoever holds a sales role.

    `_cfg()` used to return the first five users with a sales role, which on
    this site meant a test account, two gmail addresses and a user at another
    company's domain — so demo mail arrived from "Koskey" and "Roletest Crm
    User". These check the preference holds and the fallback still exists.
    """

    def test_named_people_are_preferred_when_they_exist(self):
        from upande_crm.demo_data import SALES_PEOPLE, sales_users

        resolved = sales_users()
        for _, email in SALES_PEOPLE:
            if frappe.db.exists("User", email):
                self.assertIn(email, resolved)

    def test_cfg_uses_them(self):
        from upande_crm.demo_data import SALES_PEOPLE, _cfg, sales_users

        if not sales_users():
            self.skipTest("neither named user exists on this site")
        users = _cfg()["users"]
        self.assertTrue(users)
        expected = {e for _, e in SALES_PEOPLE if frappe.db.exists("User", e)}
        self.assertEqual(set(users), expected, "demo owners drifted off the named staff")

    def test_no_foreign_domain_owners(self):
        """A demo owned by another company's user is a data-hygiene problem."""
        from upande_crm.demo_data import sales_users

        for email in sales_users():
            self.assertNotIn("lokitelaorchards.com", email)
            self.assertNotIn("example.com", email)

    def test_fallback_survives_missing_users(self):
        """A site without these two must still seed, not crash."""
        import upande_crm.demo_data as mod

        real = mod.sales_users
        mod.sales_users = lambda: []
        try:
            self.assertTrue(mod._cfg()["users"], "fallback returned no owner at all")
        finally:
            mod.sales_users = real


class TestTeardownCoverage(unittest.TestCase):
    def test_extras_doctypes_are_in_the_teardown_list(self):
        """Anything seeded must also be removable, or clear_demo leaves litter."""
        from upande_crm.demo_data import _TAGGED_DOCTYPES
        from upande_crm.demo_extras import EXTRA_DOCTYPES

        # Email Group Member is deleted by group rather than by tag, so it is
        # the one deliberate omission.
        for dt in EXTRA_DOCTYPES:
            if dt == "Email Group Member":
                continue
            self.assertIn(dt, _TAGGED_DOCTYPES, f"{dt} is seeded but never cleared")
