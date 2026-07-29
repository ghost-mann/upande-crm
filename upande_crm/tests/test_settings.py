"""Tests for organisation-wide CRM settings and the integration health panel.

Two properties matter most here and are asserted directly:

1. **Reads never fail.** A site without the `Upande CRM Settings` doctype, or with
   a broken read, must still get a complete settings dict — otherwise every
   dashboard that now consults settings would break with it.
2. **Writes never pass silently.** Out-of-range values throw rather than being
   clamped, because these numbers end up in reported figures.

The Single is mutated by several tests; `FrappeTestCase` rolls the transaction
back, and `tearDown` clears the document cache so a rolled-back value cannot leak
into the next test through `get_cached_doc`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import settings as S
from upande_crm.api.analytics import crm_sales_analytics
from upande_crm.api.crm import _count, _df, crm_dashboard_overview

SALES_USER = "crm-settings-test@example.com"
KNOWN_STATUSES = {"ok", "warn", "off", "missing"}
EXPECTED_CHECKS = {"sales", "pipeline", "email_out", "email_in", "whatsapp", "activity", "storage"}


def _clear():
    frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)


def _save(**patch):
    """Write a patch straight through the controller, as the endpoint does."""
    doc = frappe.get_single(S.SETTINGS_DOCTYPE)
    doc.update(patch)
    doc.save(ignore_permissions=True)
    _clear()


class SettingsTestCase(FrappeTestCase):
    def tearDown(self):
        frappe.set_user("Administrator")
        _clear()


class TestDefaults(SettingsTestCase):
    def test_get_settings_is_always_complete(self):
        s = S.get_settings()
        for key in S.DEFAULTS:
            self.assertIn(key, s)

    def test_types_are_coerced_not_passed_through(self):
        _save(top_n=12, refresh_interval_sec=45, revenue_target_monthly=1000)
        s = S.get_settings()
        self.assertIsInstance(s["top_n"], int)
        self.assertEqual(s["top_n"], 12)
        self.assertIsInstance(s["revenue_target_monthly"], float)

    def test_falls_back_to_defaults_when_the_read_fails(self):
        # A site mid-migration, or a corrupt Singles row, must not take the
        # dashboard down with it.
        original = frappe.get_cached_doc

        def boom(*args, **kwargs):
            raise Exception("simulated read failure")

        frappe.get_cached_doc = boom
        try:
            self.assertEqual(S.get_settings(), dict(S.DEFAULTS))
        finally:
            frappe.get_cached_doc = original

    def test_doctype_json_defaults_match_the_python_defaults(self):
        # DEFAULTS is the authority for reads; the JSON is what desk shows. They
        # drifting apart would mean the CRM and desk disagree about the defaults.
        meta = frappe.get_meta(S.SETTINGS_DOCTYPE)
        for key, expected in S.DEFAULTS.items():
            field = meta.get_field(key)
            self.assertIsNotNone(field, f"{key} is missing from the doctype")
            if field.default in (None, ""):
                # No JSON default -> the Python default must be the empty/zero value.
                self.assertIn(expected, (0, 0.0, ""), f"{key} has no JSON default")
            else:
                self.assertEqual(S._coerce(field.default, expected), expected, key)


class TestParseList(SettingsTestCase):
    def test_splits_trims_and_drops_blanks(self):
        self.assertEqual(S.parse_list(" Open , Replied ,, "), ["Open", "Replied"])

    def test_preserves_multi_word_statuses(self):
        # Whitespace must not separate: real statuses here include "In Process".
        self.assertEqual(S.parse_list("In Process, Sent/Received Email"),
                         ["In Process", "Sent/Received Email"])

    def test_empty_input_yields_empty_list(self):
        self.assertEqual(S.parse_list(None), [])
        self.assertEqual(S.parse_list(""), [])

    def test_open_statuses_never_returns_empty(self):
        # An empty `in ()` filter would count zero and read as "no open leads".
        self.assertEqual(
            S.open_statuses("lead_open_statuses", {"lead_open_statuses": "  "}),
            S.parse_list(S.DEFAULTS["lead_open_statuses"]),
        )

    def test_open_statuses_honours_configuration(self):
        self.assertEqual(
            S.open_statuses("lead_open_statuses", {"lead_open_statuses": "Open, Lost"}),
            ["Open", "Lost"],
        )


class TestSaveRoundTrip(SettingsTestCase):
    def test_saved_target_is_read_back(self):
        S.crm_settings_save(frappe.as_json({"revenue_target_monthly": 250000}))
        _clear()
        self.assertEqual(S.crm_settings()["settings"]["revenue_target_monthly"], 250000.0)

    def test_unknown_keys_are_dropped_not_written(self):
        S.crm_settings_save(frappe.as_json({"revenue_target_monthly": 10, "owner": "x@y.z"}))
        _clear()
        self.assertNotEqual(frappe.get_single(S.SETTINGS_DOCTYPE).owner, "x@y.z")

    def test_request_with_no_recognised_keys_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            S.crm_settings_save(frappe.as_json({"nonsense": 1}))

    def test_malformed_payload_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            S.crm_settings_save(frappe.as_json(["not", "a", "dict"]))


class TestValidation(SettingsTestCase):
    def test_refresh_interval_below_minimum_throws(self):
        with self.assertRaises(frappe.ValidationError):
            _save(refresh_interval_sec=5)

    def test_top_n_above_maximum_throws(self):
        with self.assertRaises(frappe.ValidationError):
            _save(top_n=99)

    def test_negative_target_throws(self):
        with self.assertRaises(frappe.ValidationError):
            _save(revenue_target_monthly=-1)

    def test_empty_status_list_throws(self):
        with self.assertRaises(frappe.ValidationError):
            _save(lead_open_statuses="   ")

    def test_event_duration_out_of_range_throws(self):
        with self.assertRaises(frappe.ValidationError):
            _save(default_event_duration_mins=0)

    def test_unknown_whatsapp_template_throws(self):
        if not frappe.db.exists("DocType", "WhatsApp Templates"):
            self.skipTest("frappe_whatsapp is not installed")
        with self.assertRaises(frappe.ValidationError):
            _save(default_whatsapp_template="no-such-template")

    def test_unapproved_whatsapp_template_throws(self):
        if not frappe.db.exists("DocType", "WhatsApp Templates"):
            self.skipTest("frappe_whatsapp is not installed")
        unapproved = frappe.get_all("WhatsApp Templates", filters={"status": ["!=", "APPROVED"]},
                                    pluck="name", limit=1)
        if not unapproved:
            self.skipTest("no unapproved template on this site")
        with self.assertRaises(frappe.ValidationError):
            _save(default_whatsapp_template=unapproved[0])

    def test_approved_whatsapp_template_is_accepted(self):
        approved = frappe.get_all("WhatsApp Templates", filters={"status": "APPROVED"},
                                  pluck="name", limit=1) if frappe.db.exists(
            "DocType", "WhatsApp Templates") else []
        if not approved:
            self.skipTest("no approved template on this site")
        _save(default_whatsapp_template=approved[0])
        self.assertEqual(S.get_settings()["default_whatsapp_template"], approved[0])


class TestPermissions(SettingsTestCase):
    @staticmethod
    def _sales_user():
        if not frappe.db.exists("User", SALES_USER):
            frappe.flags.mute_emails = True
            frappe.get_doc({
                "doctype": "User", "email": SALES_USER, "first_name": "CRM Settings Test",
                "send_welcome_email": 0, "roles": [{"role": "Sales User"}],
            }).insert(ignore_permissions=True)
        return SALES_USER

    def test_sales_user_may_read_but_not_write(self):
        frappe.set_user(self._sales_user())
        payload = S.crm_settings()
        self.assertFalse(payload["can_edit"])
        self.assertIn("settings", payload)
        with self.assertRaises(frappe.PermissionError):
            S.crm_settings_save(frappe.as_json({"revenue_target_monthly": 1}))

    def test_guest_is_refused_on_every_endpoint(self):
        frappe.set_user("Guest")
        for fn in (S.crm_settings, S.crm_integration_status):
            with self.assertRaises(frappe.PermissionError):
                fn()
        with self.assertRaises(frappe.PermissionError):
            S.crm_settings_save(frappe.as_json({"revenue_target_monthly": 1}))


class TestIntegrationStatus(SettingsTestCase):
    def test_reports_every_documented_check(self):
        d = S.crm_integration_status()
        self.assertEqual({c["key"] for c in d["checks"]}, EXPECTED_CHECKS)

    def test_every_check_carries_a_known_status(self):
        for c in S.crm_integration_status()["checks"]:
            self.assertIn(c["status"], KNOWN_STATUSES)
            self.assertTrue(c["label"])
            self.assertTrue(c["detail"])

    def test_survives_whatsapp_settings_having_no_table(self):
        # `WhatsApp Settings` still has a DocType row on this site but its table
        # was dropped; a health panel that queried it would raise. This asserts
        # the panel completes and still reports on WhatsApp.
        wa = next(c for c in S.crm_integration_status()["checks"] if c["key"] == "whatsapp")
        self.assertIn(wa["status"], KNOWN_STATUSES)

    def test_whatsapp_reports_off_when_disabled(self):
        if not frappe.db.exists("DocType", "WhatsApp Message"):
            self.skipTest("frappe_whatsapp is not installed")
        _save(whatsapp_enabled=0)
        wa = next(c for c in S.crm_integration_status()["checks"] if c["key"] == "whatsapp")
        self.assertEqual(wa["status"], "off")

    def test_exposes_company_currency_and_user(self):
        d = S.crm_integration_status()
        self.assertTrue(d["currency"])
        self.assertEqual(d["user"]["name"], frappe.session.user)
        self.assertTrue(d["user"]["can_edit"])


class TestDashboardsHonourSettings(SettingsTestCase):
    RANGE = {"date_from": "2000-01-01", "date_to": "2099-12-31"}

    def test_overview_open_leads_follows_the_configured_statuses(self):
        _save(lead_open_statuses="Converted")
        d = crm_dashboard_overview(**self.RANGE)
        expected = _count("Lead", {
            **_df("Lead", "creation", self.RANGE["date_from"], self.RANGE["date_to"]),
            "status": ["in", ["Converted"]],
        })
        self.assertEqual(d["kpis"]["leads"]["open"], expected)

    def test_top_n_bounds_grouped_charts(self):
        _save(top_n=3)
        d = crm_dashboard_overview(**self.RANGE)
        self.assertLessEqual(len(d["lead_status"]), 3)
        self.assertLessEqual(len(d["top_territories"]), 3)

    def test_top_n_bounds_sales_analytics(self):
        _save(top_n=3)
        d = crm_sales_analytics(date_from="2026-01-01", date_to="2026-12-31")
        self.assertLessEqual(len(d["rep_performance"]), 3)
        self.assertLessEqual(len(d["top_products"]), 3)
        self.assertLessEqual(len(d["territory_revenue"]), 3)


class TestTargets(SettingsTestCase):
    def test_targets_block_is_present_and_shaped(self):
        t = crm_sales_analytics(date_from="2026-01-01", date_to="2026-12-31")["targets"]
        for key in ("monthly", "annual", "basis", "mtd", "ytd", "mtd_pct", "ytd_pct",
                    "month_elapsed_pct", "year_elapsed_pct"):
            self.assertIn(key, t)

    def test_attainment_is_zero_not_an_error_without_a_target(self):
        _save(revenue_target_monthly=0, revenue_target_annual=0)
        t = crm_sales_analytics(date_from="2026-01-01", date_to="2026-12-31")["targets"]
        self.assertEqual(t["mtd_pct"], 0.0)
        self.assertEqual(t["ytd_pct"], 0.0)

    def test_attainment_is_computed_against_the_target(self):
        t = crm_sales_analytics(date_from="2026-01-01", date_to="2026-12-31")["targets"]
        if not t["ytd"]:
            self.skipTest("no revenue on this site to measure")
        _save(revenue_target_annual=t["ytd"] * 2, target_basis="Billed")
        t2 = crm_sales_analytics(date_from="2026-01-01", date_to="2026-12-31")["targets"]
        self.assertAlmostEqual(t2["ytd_pct"], 50.0, places=1)

    def test_basis_selects_the_measured_doctype(self):
        _save(target_basis="Booked")
        self.assertEqual(
            crm_sales_analytics(date_from="2026-01-01", date_to="2026-12-31")["targets"]["source"],
            "Sales Order",
        )

    def test_attainment_ignores_the_dashboard_date_range(self):
        # A monthly target belongs to the calendar month; scoping it to the
        # picker would make the percentage meaningless.
        wide = crm_sales_analytics(date_from="2026-01-01", date_to="2026-12-31")["targets"]
        narrow = crm_sales_analytics(date_from="1990-01-01", date_to="1990-01-31")["targets"]
        self.assertEqual(wide["mtd"], narrow["mtd"])
        self.assertEqual(wide["ytd"], narrow["ytd"])
