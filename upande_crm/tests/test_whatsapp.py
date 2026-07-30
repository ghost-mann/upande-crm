"""Tests for the CRM WhatsApp surface.

No test may reach Meta. Send tests assert the validation branches that reject
*before* insert (insert is what dispatches), so nothing leaves the building.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from upande_crm.api import whatsapp as wa


class TestNormalisation(FrappeTestCase):
    def test_strips_punctuation_and_plus(self):
        self.assertEqual(wa._norm("+254 727 273 549"), "254727273549")
        self.assertEqual(wa._norm("254-727273549"), "254727273549")
        self.assertEqual(wa._norm(None), "")

    def test_inconsistent_site_formats_normalise_equal(self):
        # Both of these forms exist in WhatsApp Profiles on this site.
        self.assertEqual(wa._norm("254-727273549"), wa._norm("+254727273549"))

    def test_suffix_matches_across_country_code(self):
        self.assertEqual(wa._suffix("+254727273549"), wa._suffix("0727273549"))

    def test_suffix_of_short_number_is_whole_number(self):
        self.assertEqual(wa._suffix("12345"), "12345")

    def test_unrelated_numbers_do_not_share_suffix(self):
        self.assertNotEqual(wa._suffix("254727273549"), wa._suffix("254711111111"))


class TestWindow(FrappeTestCase):
    def test_open_within_24h(self):
        self.assertTrue(wa._window_open(add_to_date(now_datetime(), hours=-2)))

    def test_closed_beyond_24h(self):
        self.assertFalse(wa._window_open(add_to_date(now_datetime(), hours=-30)))

    def test_closed_when_never_inbound(self):
        self.assertFalse(wa._window_open(None))


class TestMatching(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_matches_an_existing_lead_by_its_phone(self):
        # Uses real site data rather than inserting a Lead: Lead here carries nine
        # customised mandatory fields, so a fixture would test the fixture.
        row = frappe.db.sql(
            """select name, lead_name, mobile_no from tabLead
               where coalesce(mobile_no,'') <> '' limit 1""", as_dict=True)
        if not row:
            self.skipTest("no Lead with a mobile number")
        lead = row[0]
        hit = wa._candidate_index().get(wa._suffix(lead.mobile_no))
        self.assertIsNotNone(hit, f"no match for {lead.mobile_no}")
        # Some other record may legitimately share the number; the contract is
        # that a known CRM number resolves to *something* linkable.
        self.assertIn(hit["doctype"], ("Lead", "Contact", "Customer"))

    def test_index_is_keyed_by_normalised_suffix(self):
        idx = wa._candidate_index()
        if not idx:
            self.skipTest("no phone data on site")
        for key in list(idx)[:20]:
            self.assertTrue(key.isdigit())
            self.assertLessEqual(len(key), wa.SUFFIX)

    def test_unknown_number_returns_none(self):
        self.assertIsNone(wa._candidate_index().get(wa._suffix("999888777666")))

    def test_match_endpoint_does_not_raise_on_unknown(self):
        self.assertIsNone(wa.crm_whatsapp_match("999888777666"))


class TestConversations(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def _msg(self, **kw):
        doc = frappe.get_doc({"doctype": "WhatsApp Message", **kw})
        # Bypass the controller so no Meta dispatch is attempted.
        doc.flags.ignore_validate = True
        doc.db_insert()
        return doc

    def test_groups_outgoing_by_to_and_incoming_by_from(self):
        data = wa.crm_whatsapp_conversations(limit=200)
        self.assertTrue(data["available"])
        for row in data["rows"]:
            self.assertTrue(row["party"])
            self.assertIn("unread", row)
            self.assertIn("window_open", row)

    def test_unread_total_matches_row_sum(self):
        data = wa.crm_whatsapp_conversations(limit=200)
        self.assertEqual(data["unread_total"], sum(r["unread"] for r in data["rows"]))

    def test_read_status_is_not_counted_unread(self):
        # 192 incoming on this site are 'marked as read' and must not inflate unread.
        total_incoming = frappe.db.count("WhatsApp Message", {"type": "Incoming"})
        data = wa.crm_whatsapp_conversations(limit=200)
        self.assertLess(data["unread_total"], total_incoming)

    def test_thread_returns_messages_oldest_first(self):
        convos = wa.crm_whatsapp_conversations(limit=1)
        if not convos["rows"]:
            self.skipTest("no WhatsApp messages on site")
        party = convos["rows"][0]["party"]
        t = wa.crm_whatsapp_thread(party)
        self.assertEqual(t["party"], party)
        stamps = [m["creation"] for m in t["messages"]]
        self.assertEqual(stamps, sorted(stamps))

    def test_thread_has_window_and_link_keys(self):
        convos = wa.crm_whatsapp_conversations(limit=1)
        if not convos["rows"]:
            self.skipTest("no WhatsApp messages on site")
        t = wa.crm_whatsapp_thread(convos["rows"][0]["party"])
        for k in ("window_open", "last_inbound_at", "link", "display_name"):
            self.assertIn(k, t)

    def test_mark_read_clears_unread_for_party(self):
        row = frappe.db.sql(
            """select `from` p from `tabWhatsApp Message`
               where type='Incoming' and coalesce(status,'') <> %s limit 1""",
            (wa.READ_STATUS,), as_dict=True)
        if not row:
            self.skipTest("no unread inbound messages")
        party = row[0].p
        wa.crm_whatsapp_mark_read(party)
        left = frappe.db.sql(
            """select count(*) from `tabWhatsApp Message`
               where `from`=%s and type='Incoming' and coalesce(status,'') <> %s""",
            (party, wa.READ_STATUS))[0][0]
        self.assertEqual(left, 0)


class TestTemplateRendering(FrappeTestCase):
    """`frappe_whatsapp` stores `str(payload_dict)` in `message` for template sends
    (whatsapp_notification.py), so the raw Meta payload is what reaches the thread.
    These assert we rebuild readable text instead of showing it."""

    # Exactly what sits in `tabWhatsApp Message`.`message` on this site.
    PAYLOAD = (
        "{'name': 'visitor_host_alert_v2', 'language': {'code': 'en'}, 'components': "
        "[{'type': 'body', 'parameters': [{'type': 'text', 'text': 'Evans Kemoi Kiprono'}, "
        "{'type': 'text', 'text': 'Gilbert kiprop'}, {'type': 'text', 'text': 'To service'}]}, "
        "{'type': 'button', 'sub_type': 'url', 'index': '0', 'parameters': "
        "[{'type': 'text', 'text': 'APMT-Gilbert%20kiprop-2265780'}]}]}"
    )

    def test_detects_a_payload(self):
        self.assertTrue(wa._looks_like_payload(self.PAYLOAD))

    def test_does_not_mistake_ordinary_text_for_a_payload(self):
        self.assertFalse(wa._looks_like_payload("Hello, are we still on for tomorrow?"))
        self.assertFalse(wa._looks_like_payload(""))
        self.assertFalse(wa._looks_like_payload("{not a dict"))

    def test_extracts_body_parameters_only(self):
        # The button's URL suffix is not part of what was said.
        self.assertEqual(
            wa._payload_params(self.PAYLOAD),
            ["Evans Kemoi Kiprono", "Gilbert kiprop", "To service"])

    def test_extraction_survives_garbage(self):
        self.assertEqual(wa._payload_params("{'name': broken"), [])

    def test_substitutes_positional_placeholders(self):
        body = "Hello {{1}}, {{2}} has arrived to see you regarding {{3}}."
        self.assertEqual(
            wa._fill(body, ["Evans", "Gilbert", "service"]),
            "Hello Evans, Gilbert has arrived to see you regarding service.")

    def test_missing_parameter_leaves_no_raw_placeholder(self):
        self.assertNotIn("{{2}}", wa._fill("Hi {{1}}, re {{2}}", ["Evans"]))

    def test_renders_a_real_template_row(self):
        row = frappe.db.sql(
            """select name, message, message_type, template, template_parameters
               from `tabWhatsApp Message`
               where message_type='Template' and coalesce(template,'') <> ''
               order by creation desc limit 1""", as_dict=True)
        if not row:
            self.skipTest("no template messages on site")
        text = wa._message_text(row[0])
        self.assertFalse(wa._looks_like_payload(text), f"still a payload: {text[:80]}")
        self.assertNotIn("'components'", text)
        params = frappe.parse_json(row[0].template_parameters or "[]")
        if params:
            self.assertIn(str(params[0]), text)

    def test_thread_never_returns_a_raw_payload(self):
        party = frappe.db.sql(
            """select `to` p from `tabWhatsApp Message`
               where message_type='Template' and coalesce(`to`,'') <> '' limit 1""")
        if not party:
            self.skipTest("no template messages on site")
        t = wa.crm_whatsapp_thread(party[0][0])
        for m in t["messages"]:
            self.assertFalse(wa._looks_like_payload(m.get("message")),
                             f"{m['name']} leaked a payload")

    def test_conversation_preview_never_shows_a_payload(self):
        for r in wa.crm_whatsapp_conversations(limit=200)["rows"]:
            self.assertFalse(wa._looks_like_payload(r["last_message"]),
                             f"{r['party']} preview leaked a payload")


class TestDeliverabilityWarning(FrappeTestCase):
    """Free text outside Meta's 24h window is warned about, not refused."""

    def tearDown(self):
        frappe.db.rollback()

    def test_warns_when_contact_has_never_messaged_in(self):
        self.assertIsNotNone(wa._free_text_warning("254799000111"))

    def test_no_warning_when_window_is_open(self):
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message", "type": "Incoming",
            "from": "254799000222", "message": "hi", "content_type": "text",
        })
        doc.flags.ignore_validate = True
        doc.db_insert()
        self.assertIsNone(wa._free_text_warning("254799000222"))


class TestSendValidation(FrappeTestCase):
    """Every case here must reject BEFORE insert — insert is what dispatches."""

    def test_empty_recipient_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            wa.crm_whatsapp_send("", "hello")

    def test_non_numeric_recipient_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            wa.crm_whatsapp_send("not-a-number", "hello")

    def test_empty_message_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            wa.crm_whatsapp_send("254799000111", "   ")

    def test_html_only_message_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            wa.crm_whatsapp_send("254799000111", "<div><br></div>")

    def test_off_allowlist_reference_rejected(self):
        with self.assertRaises(frappe.PermissionError):
            wa.crm_whatsapp_send("254799000111", "hi",
                                 reference_doctype="Sales Invoice", reference_name="x")

    # A closed window no longer refuses: free text is attempted and Meta's own
    # rejection is surfaced. There is deliberately no endpoint test for that path —
    # calling it would dispatch. See TestDeliverabilityWarning for the warning.

    def test_template_send_requires_a_template(self):
        with self.assertRaises(frappe.ValidationError):
            wa.crm_whatsapp_send_template("254799000111", "")

    def test_template_send_rejects_unknown_template(self):
        with self.assertRaises(frappe.ValidationError):
            wa.crm_whatsapp_send_template("254799000111", "no-such-template-xyz")

    def test_template_send_rejects_unapproved_template(self):
        row = frappe.get_all("WhatsApp Templates",
                             filters={"status": ["!=", "APPROVED"]}, limit=1)
        if not row:
            self.skipTest("no unapproved template on site")
        with self.assertRaises(frappe.ValidationError):
            wa.crm_whatsapp_send_template("254799000111", row[0].name)


class TestTemplatesAndAnalytics(FrappeTestCase):
    def test_only_approved_templates_returned(self):
        for t in wa.crm_whatsapp_templates():
            self.assertEqual(
                frappe.db.get_value("WhatsApp Templates", t["name"], "status"), "APPROVED")

    def test_analytics_shape(self):
        d = wa.crm_whatsapp_analytics(date_from="2026-01-01", date_to="2026-12-31")
        for k in ("available", "kpis", "status_mix", "trend", "top"):
            self.assertIn(k, d)
        for k in ("sent", "received", "failed", "conversations", "unread", "fail_rate"):
            self.assertIn(k, d["kpis"])

    def test_analytics_fail_rate_is_zero_not_error_when_nothing_sent(self):
        d = wa.crm_whatsapp_analytics(date_from="1990-01-01", date_to="1990-01-31")
        self.assertEqual(d["kpis"]["fail_rate"], 0.0)

    def test_analytics_reports_real_traffic(self):
        d = wa.crm_whatsapp_analytics(date_from="2020-01-01", date_to="2030-01-01")
        # The site holds 386 messages; zero would mean the query degraded silently.
        self.assertGreater(d["kpis"]["sent"] + d["kpis"]["received"], 0)


class TestGuard(FrappeTestCase):
    def test_guard_rejects_non_crm_user(self):
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.PermissionError):
                wa.crm_whatsapp_conversations()
        finally:
            frappe.set_user("Administrator")
