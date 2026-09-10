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
