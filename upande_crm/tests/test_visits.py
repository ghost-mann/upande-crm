"""Tests for visits (CRM Visit + api/visits.py).

A visit is only useful if it leaves something behind: a completed visit must
record its outcome, and every follow-up action must become a real ToDo, so it
shows in Events & Tasks and cannot be forgotten on the visit record.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, now_datetime, nowdate

from upande_crm.api import settings as S
from upande_crm.api import visits as V


def _clear():
    frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)


class VisitCase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.customer = frappe.db.get_value("Customer", {}, "name")
        cls.lead = frappe.db.get_value("Lead", {}, "name")

    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        _clear()

    def _visit(self, **kw):
        data = {"visit_type": "Sales visit to customer", "party_type": "Customer", "party": self.customer,
                "visit_date": str(now_datetime()), "purpose": "Relationship check-in", **kw}
        return V.crm_visit_save(frappe.as_json(data))["visit"]


class TestVisitRecord(VisitCase):
    def test_a_visit_is_planned_by_default(self):
        v = self._visit()
        self.assertEqual(v["status"], "Planned")
        self.assertTrue(v["name"].startswith("VIS-"))

    def test_purpose_must_be_configured(self):
        with self.assertRaises(frappe.ValidationError):
            self._visit(purpose="Golf")

    def test_completed_needs_an_outcome(self):
        with self.assertRaises(frappe.ValidationError):
            self._visit(status="Completed")
        self.assertEqual(self._visit(status="Completed", outcome="Agreed a trial of 2 varieties")["status"], "Completed")

    def test_visit_type_is_fixed(self):
        with self.assertRaises(frappe.ValidationError):
            self._visit(visit_type="Zoom call")

    def test_a_lead_can_be_visited(self):
        if not self.lead:
            self.skipTest("no lead on this site")
        self.assertEqual(self._visit(party_type="Lead", party=self.lead)["party_type"], "Lead")

    def test_actions_become_todos(self):
        v = self._visit(actions=[{"action": "Send sample box", "assigned_to": "Administrator",
                                  "due_date": add_days(nowdate(), 3)}])
        todo = v["actions"][0]["todo"]
        self.assertTrue(todo)
        t = frappe.get_doc("ToDo", todo)
        self.assertEqual((t.reference_type, t.reference_name), ("CRM Visit", v["name"]))
        self.assertEqual(t.allocated_to, "Administrator")
        self.assertIn("Send sample box", t.description)

    def test_saving_again_does_not_duplicate_todos(self):
        v = self._visit(actions=[{"action": "Call back", "assigned_to": "Administrator"}])
        again = V.crm_visit_save(frappe.as_json({"name": v["name"], "outcome": "x", "actions": v["actions"]}))["visit"]
        self.assertEqual(again["actions"][0]["todo"], v["actions"][0]["todo"])
        self.assertEqual(frappe.db.count("ToDo", {"reference_type": "CRM Visit", "reference_name": v["name"]}), 1)

    def test_action_needs_text(self):
        with self.assertRaises(frappe.ValidationError):
            self._visit(actions=[{"action": "  ", "assigned_to": "Administrator"}])


class TestVisitViews(VisitCase):
    def test_dashboard_shape(self):
        self._visit()
        d = V.crm_dashboard_visits(add_days(nowdate(), -30), add_days(nowdate(), 30))
        for k in ("kpis", "by_type", "by_purpose", "rows", "upcoming", "purposes", "types"):
            self.assertIn(k, d)
        self.assertGreaterEqual(d["kpis"]["planned"], 1)

    def test_customer_visits(self):
        v = self._visit()
        self.assertIn(v["name"], {r["name"] for r in V.crm_customer_visits(self.customer)["rows"]})

    def test_module_off_refuses(self):
        doc = frappe.get_single(S.SETTINGS_DOCTYPE)
        doc.module_visits = 0
        doc.save(ignore_permissions=True)
        _clear()
        try:
            with self.assertRaises(frappe.PermissionError):
                V.crm_dashboard_visits()
        finally:
            doc = frappe.get_single(S.SETTINGS_DOCTYPE)
            doc.module_visits = 1
            doc.save(ignore_permissions=True)


class TestEditFromTheList(VisitCase):
    def test_saving_a_visit_as_listed_keeps_its_tasks(self):
        v = self._visit(actions=[{"action": "Quote new reds", "assigned_to": "Administrator"}])
        listed = next(r for r in V.crm_customer_visits(self.customer)["rows"] if r["name"] == v["name"])
        V.crm_visit_save(frappe.as_json({"name": v["name"], "actions": listed["actions"]}))
        self.assertEqual(frappe.db.count("ToDo", {"reference_type": "CRM Visit", "reference_name": v["name"]}), 1)


class TestDeletingAVisit(VisitCase):
    def test_deleting_a_visit_leaves_no_open_task(self):
        # Frappe removes ToDos that reference a deleted document; this pins that
        # a deleted visit cannot leave follow-ups in someone's task list.
        v = self._visit(actions=[{"action": "Chase samples", "assigned_to": "Administrator"}])
        todo = v["actions"][0]["todo"]
        frappe.delete_doc("CRM Visit", v["name"])
        self.assertNotEqual(frappe.db.get_value("ToDo", todo, "status"), "Open")


class TestTasksFollowTheVisit(VisitCase):
    """A follow-up and its ToDo must agree: whoever the visit says owns it is who
    has the task, due when the visit says, and a cancelled visit or a dropped
    follow-up leaves no open task behind."""

    def _other_user(self):
        u = frappe.db.get_value("User", {"name": ["not in", ["Administrator", "Guest"]], "enabled": 1}, "name")
        if not u:
            self.skipTest("no second user")
        return u

    def _todo(self, v):
        return frappe.get_doc("ToDo", v["actions"][0]["todo"])

    def test_reassigning_moves_the_task(self):
        v = self._visit(actions=[{"action": "Send samples", "assigned_to": "Administrator"}])
        other = self._other_user()
        acts = [{**v["actions"][0], "assigned_to": other}]
        V.crm_visit_save(frappe.as_json({"name": v["name"], "actions": acts}))
        self.assertEqual(self._todo(v).allocated_to, other)

    def test_new_due_date_reaches_the_task(self):
        v = self._visit(actions=[{"action": "Send samples", "assigned_to": "Administrator"}])
        due = add_days(nowdate(), 5)
        V.crm_visit_save(frappe.as_json({"name": v["name"], "actions": [{**v["actions"][0], "due_date": due}]}))
        self.assertEqual(str(self._todo(v).date), due)

    def test_cancelling_the_visit_cancels_open_tasks(self):
        v = self._visit(actions=[{"action": "Send samples", "assigned_to": "Administrator"}])
        V.crm_visit_save(frappe.as_json({"name": v["name"], "status": "Cancelled"}))
        self.assertEqual(self._todo(v).status, "Cancelled")

    def test_dropping_a_follow_up_cancels_its_task(self):
        v = self._visit(actions=[{"action": "A", "assigned_to": "Administrator"},
                                 {"action": "B", "assigned_to": "Administrator"}])
        dropped = v["actions"][1]["todo"]
        V.crm_visit_save(frappe.as_json({"name": v["name"], "actions": [v["actions"][0]]}))
        self.assertEqual(frappe.db.get_value("ToDo", dropped, "status"), "Cancelled")
        self.assertEqual(self._todo(v).status, "Open")
