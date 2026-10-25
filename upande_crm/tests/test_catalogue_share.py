"""Tests for sending personal catalogue links (api/catalogues.py sharing).

No test reaches Meta: WhatsApp sends are patched at the CRM's own send
functions, and the template-parameter test captures the WhatsApp Message before
its insert (insert is what dispatches).
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import catalogues as C
from upande_crm.api import settings as S
from upande_crm.api import whatsapp as wa
from upande_crm.tests.test_catalogue_model import make_catalogue


def _settings(**patch_):
    doc = frappe.get_single(S.SETTINGS_DOCTYPE)
    doc.update(patch_)
    doc.save(ignore_permissions=True)
    frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)


class TestShare(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.cat = make_catalogue(status="Live")
        self.lead = frappe.get_doc({"doctype": "Lead", "first_name": "Share", "last_name": "Target",
                                    "email_id": "share-target@example.com", "mobile_no": "+254700111222"}
                                   ).insert(ignore_permissions=True).name

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()
        frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)

    def share(self, channel, **kw):
        return C.crm_catalogue_share(self.cat.name, "Lead", self.lead, channel, **kw)

    def test_copy_creates_link_with_token_url(self):
        out = self.share("Copied")
        link = frappe.get_doc("CRM Catalogue Link", out["link"])
        self.assertTrue(out["url"].endswith("/catalogue/" + link.token))
        self.assertEqual((link.party, link.sent_via, link.contact_email), (self.lead, "Copied", "share-target@example.com"))
        self.assertFalse(out["sent"])

    def test_same_party_and_channel_reuses_link(self):
        self.assertEqual(self.share("Copied")["link"], self.share("Copied")["link"])

    def test_email_send_creates_communication_with_link(self):
        out = self.share("Email")
        self.assertTrue(out["sent"])
        comm = frappe.get_all("Communication", filters={"reference_doctype": "Lead", "reference_name": self.lead},
                              fields=["content", "subject", "recipients"])
        self.assertEqual(len(comm), 1)
        self.assertIn(out["url"], comm[0].content)
        self.assertIn(self.cat.title, comm[0].subject)
        self.assertEqual(comm[0].recipients, "share-target@example.com")

    def test_email_hidden_when_mail_module_off(self):
        _settings(module_mail=0)
        opts = C.crm_catalogue_share_options(self.cat.name, "Lead", self.lead)
        self.assertFalse(opts["channels"]["email"])
        self.assertTrue(opts["channels"]["copy"])
        with self.assertRaises(frappe.PermissionError):
            self.share("Email")

    def test_whatsapp_text_inside_window(self):
        _settings(whatsapp_enabled=1)
        with patch.object(wa, "_available", return_value=True), \
             patch.object(wa, "_last_inbound_at", return_value=frappe.utils.now_datetime()), \
             patch.object(wa, "crm_whatsapp_send", return_value={"name": "x"}) as send:
            opts = C.crm_catalogue_share_options(self.cat.name, "Lead", self.lead)
            self.assertEqual(opts["channels"]["whatsapp_mode"], "text")
            out = self.share("WhatsApp")
        self.assertIn(out["url"], send.call_args.kwargs["message"])

    def test_whatsapp_template_used_outside_window(self):
        _settings(catalogue_whatsapp_template="catalogue_offer", whatsapp_enabled=1)
        with patch.object(wa, "_available", return_value=True), \
             patch.object(wa, "_last_inbound_at", return_value=None), \
             patch.object(wa, "crm_whatsapp_send_template", return_value={"name": "x"}) as send:
            out = self.share("WhatsApp")
        self.assertEqual(send.call_args.kwargs["template"], "catalogue_offer")
        self.assertEqual(json.loads(send.call_args.kwargs["body_params"]), [out["url"]])

    def test_whatsapp_disabled_without_template_outside_window(self):
        _settings(catalogue_whatsapp_template="", whatsapp_enabled=1)
        with patch.object(wa, "_available", return_value=True), \
             patch.object(wa, "_last_inbound_at", return_value=None):
            opts = C.crm_catalogue_share_options(self.cat.name, "Lead", self.lead)
            self.assertFalse(opts["channels"]["whatsapp"])
            self.assertTrue(opts["reason"]["whatsapp"])
            with self.assertRaises(frappe.ValidationError):
                self.share("WhatsApp")

    def test_whatsapp_unavailable_without_app(self):
        with patch.object(wa, "_available", return_value=False):
            opts = C.crm_catalogue_share_options(self.cat.name, "Lead", self.lead)
        self.assertFalse(opts["channels"]["whatsapp"])

    def test_links_list_shows_opens(self):
        link = self.share("Copied")["link"]
        frappe.db.set_value("CRM Catalogue Link", link, "open_count", 3)
        row = next(r for r in C.crm_catalogue_links(self.cat.name)["rows"] if r["name"] == link)
        self.assertEqual(row["open_count"], 3)


class TestTemplateParams(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_send_template_body_params_stored(self):
        if not frappe.db.exists("DocType", "WhatsApp Message"):
            self.skipTest("frappe_whatsapp is not installed on this site")
        captured = {}

        def fake_insert(doc, *a, **kw):
            captured["body_param"] = doc.body_param
            return doc

        tpl = frappe.db.get_value("WhatsApp Templates", {"status": "APPROVED"}, "name")
        if not tpl:
            self.skipTest("no approved template")
        with patch("frappe.model.document.Document.insert", fake_insert):
            wa.crm_whatsapp_send_template("+254700111222", tpl, body_params=json.dumps(["https://x/catalogue/abc"]))
        self.assertEqual(json.loads(captured["body_param"]), {"1": "https://x/catalogue/abc"})
