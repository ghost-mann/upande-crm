"""Tests for campaigns.

The behaviours worth locking down are the ones discovered by reading ERPNext's own
controller rather than guessing:

* enrolment is bulk, and one rejected recipient must not lose the batch;
* a campaign with no schedule cannot be enrolled against at all;
* attribution writes `Lead.utm_campaign` and bridges the UTM row back to the
  Campaign via `crm_campaign` — without it no campaign can be evaluated, since
  utm_campaign is unset on every lead on this site.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import campaigns as C

WIDE = {"date_from": "2000-01-01", "date_to": "2099-12-31"}

# Campaign's primary key is its title on this site, so every test mints its own
# rather than sharing one fixture name.
_seq = iter(range(1, 10_000))


def _title():
    return f"ZZ Test Campaign {next(_seq)}"


def _template():
    rows = frappe.get_all("Email Template", pluck="name", limit=1)
    return rows[0] if rows else None


def _lead_with_email():
    rows = frappe.get_all("Lead", filters={"email_id": ["!=", ""]}, pluck="name", limit=2)
    return rows


def _lead_without_email():
    rows = frappe.get_all("Lead", filters={"email_id": ["in", ["", None]]}, pluck="name", limit=1)
    return rows[0] if rows else None


def _make(title=None, days=(0, 3)):
    tpl = _template()
    return C.crm_campaign_save(json.dumps({
        "campaign_name": title or _title(),
        "description": "test",
        "schedule": [{"email_template": tpl, "send_after_days": d} for d in days],
    }))


class CampaignTestCase(FrappeTestCase):
    def setUp(self):
        if not frappe.db.exists("DocType", "Campaign"):
            self.skipTest("ERPNext CRM module not installed")
        if not _template():
            self.skipTest("no Email Template on this site")
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")


class TestCampaignSave(CampaignTestCase):
    def test_a_campaign_round_trips_with_its_schedule(self):
        r = _make(days=(0, 5))
        self.assertEqual(r["steps"], 2)
        d = C.crm_campaign_detail(r["name"])
        self.assertEqual(d["title"], r["title"])
        self.assertEqual([s["send_after_days"] for s in d["schedule"]], [0, 5])

    def test_the_schedule_is_sorted_by_day(self):
        r = _make(days=(9, 2, 5))
        d = C.crm_campaign_detail(r["name"])
        self.assertEqual([s["send_after_days"] for s in d["schedule"]], [2, 5, 9])

    def test_a_name_is_required(self):
        with self.assertRaises(frappe.ValidationError):
            C.crm_campaign_save(json.dumps({"campaign_name": "  ", "schedule": []}))

    def test_an_unknown_template_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            C.crm_campaign_save(json.dumps({
                "campaign_name": _title(),
                "schedule": [{"email_template": "No Such Template", "send_after_days": 0}]}))

    def test_a_negative_offset_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            C.crm_campaign_save(json.dumps({
                "campaign_name": _title(),
                "schedule": [{"email_template": _template(), "send_after_days": -1}]}))

    def test_two_steps_on_the_same_day_are_refused(self):
        # Legal in the doctype, but impossible to reason about in a drip.
        with self.assertRaises(frappe.ValidationError):
            C.crm_campaign_save(json.dumps({
                "campaign_name": _title(),
                "schedule": [{"email_template": _template(), "send_after_days": 2},
                             {"email_template": _template(), "send_after_days": 2}]}))

    def test_the_schedule_is_replaced_wholesale_on_update(self):
        r = _make(days=(0, 3, 7))
        C.crm_campaign_save(json.dumps({
            "name": r["name"], "campaign_name": r["title"],
            "schedule": [{"email_template": _template(), "send_after_days": 1}]}))
        d = C.crm_campaign_detail(r["name"])
        self.assertEqual(len(d["schedule"]), 1)

    def test_a_duplicate_name_is_refused_with_a_readable_message(self):
        # Campaign is named by its title here, so a repeat is a primary-key
        # collision — it must not surface as a DuplicateEntryError traceback.
        first = _make()
        with self.assertRaises(frappe.DuplicateEntryError) as caught:
            _make(title=first["title"])
        self.assertIn("already exists", str(caught.exception))

    def test_unknown_payload_fields_are_dropped(self):
        r = C.crm_campaign_save(json.dumps({
            "campaign_name": _title(), "owner": "nobody@example.com",
            "schedule": [{"email_template": _template(), "send_after_days": 0}]}))
        self.assertNotEqual(frappe.db.get_value("Campaign", r["name"], "owner"),
                            "nobody@example.com")


class TestEnrolment(CampaignTestCase):
    def test_enrolling_leads_creates_one_email_campaign_each(self):
        leads = _lead_with_email()
        if len(leads) < 2:
            self.skipTest("need two leads with an email address")
        camp = _make()
        r = C.crm_campaign_enrol(campaign=camp["name"], target="Lead",
                                 recipients=json.dumps(leads),
                                 start_date=frappe.utils.today())
        self.assertEqual(r["enrolled"], 2)
        self.assertEqual(r["failed"], 0)
        for lead in leads:
            self.assertTrue(frappe.db.exists("Email Campaign",
                                             {"campaign_name": camp["name"], "recipient": lead}))

    def test_the_end_date_is_derived_from_the_longest_step(self):
        leads = _lead_with_email()
        if not leads:
            self.skipTest("no lead with an email address")
        camp = _make(days=(0, 11))
        r = C.crm_campaign_enrol(campaign=camp["name"], target="Lead",
                                 recipients=json.dumps(leads[:1]),
                                 start_date=frappe.utils.today())
        name = r["results"][0]["name"]
        row = frappe.db.get_value("Email Campaign", name, ["start_date", "end_date"], as_dict=True)
        self.assertEqual((frappe.utils.getdate(row.end_date)
                          - frappe.utils.getdate(row.start_date)).days, 11)

    def test_a_campaign_without_a_schedule_cannot_be_enrolled(self):
        # ERPNext's controller refuses this; catching it up front gives a better
        # message than "Please set up the Campaign Schedule".
        doc = frappe.get_doc({"doctype": "Campaign", "campaign_name": _title() + " no schedule"})
        doc.insert(ignore_permissions=True)
        leads = _lead_with_email()
        with self.assertRaises(frappe.ValidationError):
            C.crm_campaign_enrol(campaign=doc.name, target="Lead",
                                 recipients=json.dumps(leads[:1] or ["x"]))

    def test_one_bad_recipient_does_not_lose_the_batch(self):
        leads = _lead_with_email()
        if not leads:
            self.skipTest("no lead with an email address")
        camp = _make()
        r = C.crm_campaign_enrol(
            campaign=camp["name"], target="Lead",
            recipients=json.dumps(leads[:1] + ["NO-SUCH-LEAD-ZZZ"]),
            start_date=frappe.utils.today())
        self.assertEqual(r["enrolled"], 1)
        self.assertEqual(r["failed"], 1)
        bad = next(x for x in r["results"] if not x["ok"])
        self.assertIn("not found", bad["error"])

    def test_a_lead_without_an_email_fails_with_a_reason(self):
        lead = _lead_without_email()
        if not lead:
            self.skipTest("every lead on this site has an email address")
        camp = _make()
        r = C.crm_campaign_enrol(campaign=camp["name"], target="Lead",
                                 recipients=json.dumps([lead]),
                                 start_date=frappe.utils.today())
        self.assertEqual(r["enrolled"], 0)
        self.assertTrue(r["results"][0]["error"])

    def test_a_past_start_date_is_refused(self):
        camp = _make()
        with self.assertRaises(frappe.ValidationError):
            C.crm_campaign_enrol(campaign=camp["name"], target="Lead",
                                 recipients=json.dumps(["x"]), start_date="2020-01-01")

    def test_an_off_list_target_is_refused(self):
        camp = _make()
        with self.assertRaises(frappe.ValidationError):
            C.crm_campaign_enrol(campaign=camp["name"], target="Customer",
                                 recipients=json.dumps(["x"]))

    def test_no_recipients_is_refused(self):
        camp = _make()
        with self.assertRaises(frappe.ValidationError):
            C.crm_campaign_enrol(campaign=camp["name"], target="Lead",
                                 recipients=json.dumps([]))

    def test_an_unknown_campaign_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            C.crm_campaign_enrol(campaign="ZZ Nope", target="Lead",
                                 recipients=json.dumps(["x"]))

    def test_enrolling_an_email_group_works(self):
        groups = frappe.get_all("Email Group", pluck="name", limit=1)
        if not groups:
            self.skipTest("no email groups")
        camp = _make()
        r = C.crm_campaign_enrol(campaign=camp["name"], target="Email Group",
                                 recipients=json.dumps(groups),
                                 start_date=frappe.utils.today())
        self.assertEqual(r["enrolled"], 1)


class TestAttribution(CampaignTestCase):
    def test_enrolment_tags_the_lead_and_bridges_the_utm_row(self):
        leads = _lead_with_email()
        if not leads:
            self.skipTest("no lead with an email address")
        camp = _make()
        r = C.crm_campaign_enrol(campaign=camp["name"], target="Lead",
                                 recipients=json.dumps(leads[:1]),
                                 start_date=frappe.utils.today(), attribute=1)
        self.assertEqual(r["utm_campaign"], camp["title"])
        self.assertEqual(frappe.db.get_value("Lead", leads[0], "utm_campaign"), camp["title"])
        # crm_campaign is ERPNext's own bridge between UTM Campaign and Campaign.
        self.assertEqual(frappe.db.get_value("UTM Campaign", camp["title"], "crm_campaign"),
                         camp["name"])
        self.assertTrue(r["results"][0]["attributed"])

    def test_attribution_can_be_declined(self):
        leads = _lead_with_email()
        if not leads:
            self.skipTest("no lead with an email address")
        before = frappe.db.get_value("Lead", leads[0], "utm_campaign")
        camp = _make()
        r = C.crm_campaign_enrol(campaign=camp["name"], target="Lead",
                                 recipients=json.dumps(leads[:1]),
                                 start_date=frappe.utils.today(), attribute=0)
        self.assertIsNone(r["utm_campaign"])
        self.assertEqual(frappe.db.get_value("Lead", leads[0], "utm_campaign"), before)
        self.assertFalse(r["results"][0]["attributed"])

    def test_a_group_enrolment_tags_nothing(self):
        # Attribution applies to leads; an Email Group has no utm_campaign field.
        groups = frappe.get_all("Email Group", pluck="name", limit=1)
        if not groups:
            self.skipTest("no email groups")
        camp = _make()
        r = C.crm_campaign_enrol(campaign=camp["name"], target="Email Group",
                                 recipients=json.dumps(groups),
                                 start_date=frappe.utils.today(), attribute=1)
        self.assertFalse(r["results"][0]["attributed"])


class TestDashboard(CampaignTestCase):
    def test_shape(self):
        d = C.crm_dashboard_campaigns(**WIDE)
        for key in ("available", "kpis", "campaigns", "enrolments", "status_mix",
                    "target_mix", "audiences", "sends_via_scheduler"):
            self.assertIn(key, d)

    def test_it_reports_the_real_campaigns_on_this_site(self):
        d = C.crm_dashboard_campaigns(**WIDE)
        self.assertGreater(d["kpis"]["campaigns"], 0)
        self.assertEqual(len(d["campaigns"]), d["kpis"]["campaigns"])

    def test_campaigns_without_a_schedule_are_counted_separately(self):
        # They cannot send, so the UI needs to flag them rather than list them as
        # equal to the rest.
        d = C.crm_dashboard_campaigns(**WIDE)
        k = d["kpis"]
        self.assertEqual(k["with_schedule"] + k["without_schedule"], k["campaigns"])

    def test_every_campaign_row_carries_its_schedule_and_counts(self):
        for row in C.crm_dashboard_campaigns(**WIDE)["campaigns"][:5]:
            for key in ("title", "schedule", "steps", "duration_days", "enrolled",
                        "active", "attributed_leads"):
                self.assertIn(key, row)

    def test_enrolments_carry_a_readable_campaign_title(self):
        for row in C.crm_dashboard_campaigns(**WIDE)["enrolments"][:5]:
            self.assertIn("campaign_title", row)

    def test_audiences_report_live_member_counts(self):
        for g in C.crm_email_groups()[:3]:
            self.assertEqual(g["total"], g["active"] + g["unsubscribed"])


class TestRecipientPicker(CampaignTestCase):
    def test_leads_are_flagged_eligible_only_with_an_email(self):
        rows = C.crm_campaign_recipients(target="Lead", limit=25)
        for r in rows:
            self.assertEqual(r["eligible"], bool(r["detail"] and "@" in r["detail"]))

    def test_groups_report_their_subscriber_counts(self):
        rows = C.crm_campaign_recipients(target="Email Group", limit=5)
        for r in rows:
            self.assertIn("subscribers", r["detail"])

    def test_an_off_list_target_returns_nothing(self):
        self.assertEqual(C.crm_campaign_recipients(target="Customer"), [])


class TestPermissions(CampaignTestCase):
    def test_a_non_owner_non_manager_cannot_edit_someone_elses_campaign(self):
        camp = _make()
        email = "crm-campaign-test@example.com"
        if not frappe.db.exists("User", email):
            frappe.flags.mute_emails = True
            frappe.get_doc({"doctype": "User", "email": email, "first_name": "Camp Test",
                            "send_welcome_email": 0,
                            "roles": [{"role": "Sales User"}]}).insert(ignore_permissions=True)
        frappe.set_user(email)
        with self.assertRaises(frappe.PermissionError):
            C.crm_campaign_save(json.dumps({
                "name": camp["name"], "campaign_name": "hijacked",
                "schedule": [{"email_template": _template(), "send_after_days": 0}]}))

    def test_guest_is_refused_everywhere(self):
        frappe.set_user("Guest")
        for call in (
            lambda: C.crm_dashboard_campaigns(),
            lambda: C.crm_email_templates(),
            lambda: C.crm_email_groups(),
            lambda: C.crm_campaign_recipients(target="Lead"),
            lambda: C.crm_campaign_save(json.dumps({"campaign_name": "x"})),
            lambda: C.crm_campaign_enrol(campaign="x", target="Lead", recipients="[]"),
            lambda: C.crm_campaign_cancel("x"),
        ):
            with self.assertRaises(frappe.PermissionError):
                call()
