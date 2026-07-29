"""Tests for call logging.

A write module, so these lean on the same principle as `test_activity.py`: every
rejection path is asserted, because a call that appears to save and does not is the
worst outcome here. The follow-up task is tested for the inverse too — a failing
follow-up must leave the call itself saved.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import calls as C
from upande_crm.api.crm import crm_dashboard_events_tasks

WIDE = {"date_from": "2000-01-01", "date_to": "2099-12-31"}
NUMBER = "+254700000001"


def _a_customer():
    rows = frappe.get_all("Customer", pluck="name", limit=1)
    return rows[0] if rows else None


def _save(**payload):
    body = {"type": "Outgoing", "to": NUMBER, "status": "Completed"}
    body.update(payload)
    return C.crm_call_save(json.dumps(body))


class CallTestCase(FrappeTestCase):
    def setUp(self):
        if not C._available():
            self.skipTest("Telephony's Call Log is not installed")
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")


class TestSaveAndRoundTrip(CallTestCase):
    def test_a_logged_call_round_trips(self):
        r = _save(summary="Talked about the June order", duration=3)
        doc = frappe.get_doc("Call Log", r["name"])
        self.assertEqual(doc.type, "Outgoing")
        self.assertEqual(doc.status, "Completed")
        self.assertEqual(doc.summary, "Talked about the June order")
        self.assertEqual(doc.to, NUMBER)

    def test_minutes_are_stored_as_seconds(self):
        # `duration` is a Duration field (seconds); nobody logs a call in seconds.
        r = _save(duration=4.5)
        self.assertEqual(frappe.db.get_value("Call Log", r["name"], "duration"), 270)

    def test_incoming_stores_the_number_on_the_from_side(self):
        r = C.crm_call_save(json.dumps({"type": "Incoming", "from": NUMBER,
                                        "status": "No Answer"}))
        doc = frappe.get_doc("Call Log", r["name"])
        self.assertEqual(doc.get("from"), NUMBER)
        self.assertEqual(doc.status, "No Answer")

    def test_a_manual_call_gets_an_id_without_a_provider(self):
        r = _save()
        self.assertTrue(frappe.db.get_value("Call Log", r["name"], "id"))
        self.assertEqual(frappe.db.get_value("Call Log", r["name"], "medium"), "Manual")

    def test_an_existing_call_can_be_updated(self):
        r = _save(summary="first")
        C.crm_call_save(json.dumps({"name": r["name"], "type": "Outgoing", "to": NUMBER,
                                    "status": "Completed", "summary": "second"}))
        self.assertEqual(frappe.db.get_value("Call Log", r["name"], "summary"), "second")

    def test_unknown_payload_fields_are_dropped(self):
        r = _save(owner="nobody@example.com", docstatus=2)
        doc = frappe.get_doc("Call Log", r["name"])
        self.assertNotEqual(doc.owner, "nobody@example.com")
        self.assertEqual(doc.docstatus, 0)


class TestValidation(CallTestCase):
    def test_direction_is_required_and_constrained(self):
        for direction in (None, "", "Sideways"):
            with self.assertRaises(frappe.ValidationError, msg=repr(direction)):
                C.crm_call_save(json.dumps({"type": direction, "to": NUMBER}))

    def test_a_number_is_required(self):
        with self.assertRaises(frappe.ValidationError):
            C.crm_call_save(json.dumps({"type": "Outgoing", "to": "   "}))

    def test_a_live_status_is_refused_for_a_manual_log(self):
        # Ringing / In Progress describe a call in flight, which one being written
        # down afterwards never is.
        for status in ("Ringing", "In Progress", "Queued", "Nonsense"):
            with self.assertRaises(frappe.ValidationError, msg=status):
                _save(status=status)

    def test_negative_duration_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            _save(duration=-1)

    def test_end_before_start_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            _save(start_time="2026-07-01 10:00:00", end_time="2026-07-01 09:00:00")

    def test_an_off_allowlist_reference_is_refused(self):
        with self.assertRaises(frappe.PermissionError):
            _save(reference_doctype="User", reference_name="Administrator")

    def test_a_reference_type_without_a_record_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            _save(reference_doctype="Customer", reference_name="")

    def test_a_missing_linked_record_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            _save(reference_doctype="Customer", reference_name="No Such Customer ZZZ")

    def test_an_unknown_call_type_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            _save(type_of_call="Not A Real Disposition")


class TestLinking(CallTestCase):
    def test_an_explicit_reference_is_attached(self):
        customer = _a_customer()
        if not customer:
            self.skipTest("no customers on this site")
        r = _save(reference_doctype="Customer", reference_name=customer)
        links = frappe.get_all("Dynamic Link",
                               filters={"parenttype": "Call Log", "parent": r["name"]},
                               fields=["link_doctype", "link_name"])
        self.assertIn(("Customer", customer),
                      [(l.link_doctype, l.link_name) for l in links])

    def test_the_most_specific_link_is_reported_as_the_reference(self):
        # Core auto-links calls by phone number, so a call logged against a Customer
        # can come back carrying a Lead link too. The displayed reference must be
        # deterministic rather than whichever row the database returned first.
        rows = C._attach_links([{"name": "x"}])
        self.assertIn("links", rows[0])
        ranked = sorted(["Lead", "Customer", "Contact"], key=C._link_rank)
        self.assertEqual(ranked[0], "Customer")

    def test_link_rank_puts_unknown_doctypes_last(self):
        self.assertGreater(C._link_rank("Something Else"), C._link_rank("Lead"))


class TestFollowUp(CallTestCase):
    def test_a_follow_up_creates_a_linked_task(self):
        customer = _a_customer()
        r = _save(reference_doctype="Customer" if customer else None,
                  reference_name=customer,
                  follow_up={"description": "Send the revised quote"})
        self.assertIn("follow_up", r)
        todo = frappe.get_doc("ToDo", r["follow_up"]["name"])
        self.assertIn("Send the revised quote", todo.description)
        self.assertEqual(todo.status, "Open")
        self.assertEqual(todo.allocated_to, "Administrator")
        if customer:
            self.assertEqual(todo.reference_type, "Customer")
            self.assertEqual(todo.reference_name, customer)

    def test_the_follow_up_uses_the_configured_defaults(self):
        from upande_crm.api.settings import get_settings

        settings = get_settings()
        r = _save(follow_up={"description": "Chase"})
        todo = frappe.get_doc("ToDo", r["follow_up"]["name"])
        self.assertEqual(todo.priority, settings["default_task_priority"])
        expected = frappe.utils.add_days(frappe.utils.nowdate(),
                                         settings["default_task_due_days"])
        self.assertEqual(str(todo.date), str(expected))

    def test_an_explicit_due_date_and_priority_win(self):
        r = _save(follow_up={"description": "Chase", "date": "2026-12-24",
                             "priority": "High"})
        todo = frappe.get_doc("ToDo", r["follow_up"]["name"])
        self.assertEqual(str(todo.date), "2026-12-24")
        self.assertEqual(todo.priority, "High")

    def test_a_follow_up_without_a_description_still_gets_one(self):
        r = _save(follow_up=True)
        todo = frappe.get_doc("ToDo", r["follow_up"]["name"])
        self.assertTrue(todo.description.strip())

    def test_the_follow_up_task_is_visible_to_the_activity_dashboard(self):
        customer = _a_customer()
        if not customer:
            self.skipTest("no customers on this site")
        r = _save(reference_doctype="Customer", reference_name=customer,
                  follow_up={"description": "Visible in Events & Tasks"})
        todos = crm_dashboard_events_tasks(**WIDE)["todos"]
        self.assertIn(r["follow_up"]["name"], [t["name"] for t in todos])

    def test_a_failing_follow_up_leaves_the_call_saved(self):
        # The call is the record of fact; the task is a convenience.
        import upande_crm.api.calls as module

        original = module._create_follow_up

        def boom(*args, **kwargs):
            raise Exception("simulated follow-up failure")

        module._create_follow_up = boom
        try:
            r = _save(follow_up={"description": "will fail"})
        finally:
            module._create_follow_up = original
        self.assertTrue(frappe.db.exists("Call Log", r["name"]))
        self.assertIn("follow_up_error", r)
        self.assertNotIn("follow_up", r)


class TestCallTypes(CallTestCase):
    def test_add_then_list(self):
        if not frappe.db.exists("DocType", "Telephony Call Type"):
            self.skipTest("Telephony Call Type unavailable")
        r = C.crm_call_type_add("Price Query")
        self.assertTrue(r["created"])
        self.assertIn("Price Query", C.crm_call_types())

    def test_adding_an_existing_type_is_idempotent(self):
        if not frappe.db.exists("DocType", "Telephony Call Type"):
            self.skipTest("Telephony Call Type unavailable")
        C.crm_call_type_add("Complaint")
        again = C.crm_call_type_add("Complaint")
        self.assertFalse(again["created"])

    def test_an_empty_type_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            C.crm_call_type_add("   ")

    def test_a_saved_call_can_carry_a_disposition(self):
        if not frappe.db.exists("DocType", "Telephony Call Type"):
            self.skipTest("Telephony Call Type unavailable")
        C.crm_call_type_add("Follow-up")
        r = _save(type_of_call="Follow-up")
        self.assertEqual(frappe.db.get_value("Call Log", r["name"], "type_of_call"),
                         "Follow-up")


class TestDashboard(CallTestCase):
    def test_shape(self):
        d = C.crm_dashboard_calls(**WIDE)
        for key in ("available", "kpis", "direction_mix", "outcome_mix", "type_mix",
                    "trend", "by_user", "rows"):
            self.assertIn(key, d)

    def test_kpis_count_direction_and_outcome(self):
        before = C.crm_dashboard_calls(**WIDE)["kpis"]
        _save(duration=2)
        C.crm_call_save(json.dumps({"type": "Incoming", "from": NUMBER,
                                    "status": "No Answer"}))
        after = C.crm_dashboard_calls(**WIDE)["kpis"]
        self.assertEqual(after["total"], before["total"] + 2)
        self.assertEqual(after["outgoing"], before["outgoing"] + 1)
        self.assertEqual(after["incoming"], before["incoming"] + 1)
        self.assertEqual(after["missed"], before["missed"] + 1)

    def test_talk_time_sums_only_what_was_logged(self):
        before = C.crm_dashboard_calls(**WIDE)["kpis"]["talk_minutes"]
        _save(duration=10)
        after = C.crm_dashboard_calls(**WIDE)["kpis"]["talk_minutes"]
        self.assertAlmostEqual(after, before + 10, places=1)

    def test_connect_rate_is_zero_not_an_error_with_no_calls(self):
        d = C.crm_dashboard_calls(date_from="1990-01-01", date_to="1990-01-31")
        self.assertEqual(d["kpis"]["total"], 0)
        self.assertEqual(d["kpis"]["connect_rate"], 0.0)
        self.assertEqual(d["kpis"]["avg_minutes"], 0.0)

    def test_rows_carry_their_reference(self):
        customer = _a_customer()
        if not customer:
            self.skipTest("no customers on this site")
        r = _save(reference_doctype="Customer", reference_name=customer)
        row = next(x for x in C.crm_dashboard_calls(**WIDE)["rows"] if x["name"] == r["name"])
        self.assertTrue(row["reference_doctype"])
        self.assertIsInstance(row["links"], list)

    def test_customer_filtering_narrows_the_log(self):
        customer = _a_customer()
        if not customer:
            self.skipTest("no customers on this site")
        _save(reference_doctype="Customer", reference_name=customer)
        wide = C.crm_dashboard_calls(**WIDE)["kpis"]["total"]
        narrow = C.crm_dashboard_calls(**WIDE, customer=customer)["kpis"]["total"]
        self.assertLessEqual(narrow, wide)
        self.assertGreaterEqual(narrow, 1)

    def test_an_unrelated_customer_yields_no_calls(self):
        _save()
        d = C.crm_dashboard_calls(**WIDE, customer="no-such-customer-zzz")
        self.assertEqual(d["kpis"]["total"], 0)


class TestPermissions(CallTestCase):
    def test_delete_is_refused_for_a_non_owner_non_manager(self):
        r = _save()
        email = "crm-calls-test@example.com"
        if not frappe.db.exists("User", email):
            frappe.flags.mute_emails = True
            frappe.get_doc({"doctype": "User", "email": email, "first_name": "Calls Test",
                            "send_welcome_email": 0,
                            "roles": [{"role": "Sales User"}]}).insert(ignore_permissions=True)
        frappe.set_user(email)
        with self.assertRaises(frappe.PermissionError):
            C.crm_call_delete(r["name"])

    def test_the_owner_may_delete(self):
        r = _save()
        C.crm_call_delete(r["name"])
        self.assertFalse(frappe.db.exists("Call Log", r["name"]))

    def test_deleting_a_missing_call_is_refused(self):
        with self.assertRaises(frappe.DoesNotExistError):
            C.crm_call_delete("no-such-call-zzz")

    def test_guest_is_refused_everywhere(self):
        frappe.set_user("Guest")
        for call in (
            lambda: C.crm_dashboard_calls(),
            lambda: C.crm_call_types(),
            lambda: C.crm_call_save(json.dumps({"type": "Outgoing", "to": NUMBER})),
            lambda: C.crm_call_type_add("X"),
            lambda: C.crm_call_delete("x"),
        ):
            with self.assertRaises(frappe.PermissionError):
                call()
