"""Tests for the pipeline board, lead qualification and lead channels.

The stages and channels are the organisation's, not ERPNext's stock list: the
board's columns must follow Settings, and a stage or channel named there must
exist as a record the moment settings are saved, or the board and the lead form
would offer something that cannot be selected.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from upande_crm.api import board as B
from upande_crm.api import leads as L
from upande_crm.api import settings as S
from upande_crm.tests.pipeline_fixtures import required_values


def _clear():
    frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)


def _save(**patch):
    doc = frappe.get_single(S.SETTINGS_DOCTYPE)
    doc.update(patch)
    doc.save(ignore_permissions=True)
    _clear()


class BoardCase(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        _clear()

    def _lead(self, **kw):
        body = {**required_values(), "lead_name": "Board Test Buyer", "company_name": "Board Test BV",
                "email_id": f"board-{frappe.generate_hash(length=8)}@example.com", **kw}
        return L.crm_lead_save(frappe.as_json(body))["name"]


class TestSettingsCreateRecords(BoardCase):
    def test_saving_settings_creates_missing_stages_and_channels(self):
        _save(opportunity_stages="Prospecting\nSample Dispatch Test", lead_channels="Email\nTrade Event Test")
        self.assertTrue(frappe.db.exists("Sales Stage", "Sample Dispatch Test"))
        self.assertTrue(frappe.db.exists("UTM Source", "Trade Event Test"))


class TestBoard(BoardCase):
    def test_columns_follow_settings(self):
        _save(opportunity_stages="Prospecting\nNegotiation")
        b = B.crm_pipeline_board(add_days(nowdate(), -90), nowdate())
        keys = [c["key"] for c in b["columns"] if c["key"] != "other"]
        self.assertEqual(keys, ["leads", "Prospecting", "Negotiation", "customers"])
        for c in b["columns"]:
            self.assertIn("cards", c)
            self.assertIn("count", c)

    def test_opportunities_in_unlisted_stages_are_not_lost(self):
        _save(opportunity_stages="Prospecting")
        b = B.crm_pipeline_board(add_days(nowdate(), -3650), nowdate())
        keys = [c["key"] for c in b["columns"]]
        # Anything open in a stage no longer listed shows in an "Other stages" column.
        other = frappe.db.count("Opportunity", {"status": ["in", ["Open", "Quotation", "Replied"]],
                                                "sales_stage": ["not in", ["Prospecting"]]})
        if other:
            self.assertIn("other", keys)

    def test_moving_an_opportunity(self):
        opp = frappe.db.get_value("Opportunity", {"status": "Open"}, "name")
        if not opp:
            self.skipTest("no open opportunity")
        _save(opportunity_stages="Prospecting\nNegotiation")
        r = B.crm_opportunity_set_stage(opp, "Negotiation")
        self.assertEqual(r["sales_stage"], "Negotiation")
        self.assertEqual(frappe.db.get_value("Opportunity", opp, "sales_stage"), "Negotiation")

    def test_moving_to_an_unconfigured_stage_is_refused(self):
        opp = frappe.db.get_value("Opportunity", {}, "name")
        with self.assertRaises(frappe.ValidationError):
            B.crm_opportunity_set_stage(opp, "Nonsense")

    def test_moving_needs_write_permission(self):
        from unittest.mock import patch

        opp = frappe.db.get_value("Opportunity", {}, "name")
        with patch("upande_crm.api.board.frappe.has_permission", return_value=False):
            with self.assertRaises(frappe.PermissionError):
                B.crm_opportunity_set_stage(opp, "Prospecting")


class TestQualification(BoardCase):
    def test_qualifying_a_lead_records_who_and_when(self):
        lead = self._lead()
        r = B.crm_lead_qualify(lead, "Qualified")
        self.assertEqual(r["qualification_status"], "Qualified")
        doc = frappe.get_doc("Lead", lead)
        self.assertEqual(doc.qualified_by, "Administrator")
        self.assertEqual(str(doc.qualified_on), nowdate())

    def test_unqualifying_clears_who_and_when(self):
        lead = self._lead()
        B.crm_lead_qualify(lead, "Qualified")
        B.crm_lead_qualify(lead, "In Process")
        doc = frappe.get_doc("Lead", lead)
        self.assertFalse(doc.qualified_by)
        self.assertFalse(doc.qualified_on)

    def test_unknown_status_refused(self):
        with self.assertRaises(frappe.ValidationError):
            B.crm_lead_qualify(self._lead(), "Maybe")


class TestLeadCapture(BoardCase):
    def test_lead_saves_its_channel_and_qualification(self):
        _save(lead_channels="Email\nTrade Event")
        lead = self._lead(utm_source="Trade Event", qualification_status="Qualified")
        doc = frappe.get_doc("Lead", lead)
        self.assertEqual(doc.utm_source, "Trade Event")
        self.assertEqual(doc.qualification_status, "Qualified")
        self.assertEqual(doc.qualified_by, "Administrator")

    def test_form_offers_configured_channels_first(self):
        _save(lead_channels="Trade Event\nEmail")
        opts = L.crm_lead_form_options()
        self.assertEqual(opts["sources"][:2], ["Trade Event", "Email"])
        self.assertEqual(opts["qualification_statuses"], ["Unqualified", "In Process", "Qualified"])

    def test_new_channel_is_counted_in_lead_source_reporting(self):
        from upande_crm.api.pipeline import crm_analytics_leads

        _save(lead_channels="Email\nBoard Test Channel")
        self._lead(utm_source="Board Test Channel")
        d = crm_analytics_leads(add_days(nowdate(), -1), nowdate())
        labels = {r["label"] for r in d.get("by_source") or d.get("sources") or []}
        self.assertIn("Board Test Channel", labels)


class TestRangeIncludesItsLastDay(BoardCase):
    """`creation` is a datetime; a range ending today must include today's records."""

    def test_where_clause_includes_the_whole_last_day(self):
        from upande_crm.api.crm import _dw

        self._lead()
        where = _dw("Lead", "creation", nowdate(), nowdate())
        self.assertGreaterEqual(frappe.db.sql(f"select count(*) from `tabLead` {where}")[0][0], 1)

    def test_filters_include_the_whole_last_day(self):
        from upande_crm.api.crm import _df

        self._lead()
        self.assertGreaterEqual(frappe.db.count("Lead", _df("Lead", "creation", nowdate(), nowdate())), 1)


class TestSetupCreatesRecords(BoardCase):
    """Nobody may ever save Settings on a site, so the defaults must exist after
    install/migrate too — or moving a card to "Sample Dispatch" fails its Link check."""

    def test_setup_creates_configured_stages_and_channels(self):
        from upande_crm.setup import setup

        frappe.db.delete("Sales Stage", {"name": "Sample Dispatch"})
        frappe.db.delete("UTM Source", {"name": "Referral"})
        setup()
        self.assertTrue(frappe.db.exists("Sales Stage", "Sample Dispatch"))
        self.assertTrue(frappe.db.exists("UTM Source", "Referral"))
