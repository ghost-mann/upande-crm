"""Tests for the CRM Event/Task write layer.

These are the first tests in this app. They target the logic that can silently
cause harm — doctype allowlists, the completion rule, assignment side effects,
and the CRM scoping of the task list — rather than restating what core already
guarantees.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import activity


class TestActivityHelpers(FrappeTestCase):
    def test_allowlists_cover_crm_doctypes(self):
        for dt in (
            "Lead",
            "Opportunity",
            "Customer",
            "Prospect",
            "Quotation",
            "Contact",
            "Sales Order",
            "Event",
        ):
            self.assertIn(dt, activity.TASK_REF_DOCTYPES)
        # Participants may additionally be people.
        self.assertIn("Employee", activity.PARTICIPANT_DOCTYPES)
        self.assertIn("User", activity.PARTICIPANT_DOCTYPES)

    def test_check_ref_rejects_off_allowlist(self):
        with self.assertRaises(frappe.PermissionError):
            activity._check_ref("Sales Invoice", activity.TASK_REF_DOCTYPES)
        with self.assertRaises(frappe.PermissionError):
            activity._check_ref("Animal Event", activity.TASK_REF_DOCTYPES)

    def test_check_ref_allows_allowlisted(self):
        activity._check_ref("Lead", activity.TASK_REF_DOCTYPES)  # must not raise

    def test_check_ref_ignores_empty(self):
        activity._check_ref(None, activity.TASK_REF_DOCTYPES)  # must not raise
        activity._check_ref("", activity.TASK_REF_DOCTYPES)

    def test_assignable_users_returns_crm_role_holders(self):
        users = activity.crm_assignable_users()
        self.assertTrue(all("name" in u and "full_name" in u for u in users))
        # Administrator holds System Manager, which is in CRM_ROLES.
        self.assertIn("Administrator", [u["name"] for u in users])

    def test_my_calendars_only_returns_authorized(self):
        for cal in activity.crm_my_calendars():
            row = frappe.db.get_value(
                "Google Calendar",
                cal["name"],
                ["refresh_token", "google_calendar_id"],
                as_dict=True,
            )
            self.assertTrue(row.refresh_token)
            self.assertTrue(row.google_calendar_id)


class TestEventSave(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_create_event_minimal(self):
        r = activity.crm_event_save(
            {
                "subject": "Test CRM meeting",
                "starts_on": "2026-08-01 10:00:00",
                "ends_on": "2026-08-01 11:00:00",
            }
        )
        self.assertTrue(r["name"])
        doc = frappe.get_doc("Event", r["name"])
        self.assertEqual(doc.subject, "Test CRM meeting")
        self.assertEqual(doc.event_type, "Private")  # defaulted

    def test_ends_before_starts_is_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            activity.crm_event_save(
                {
                    "subject": "Backwards",
                    "starts_on": "2026-08-01 11:00:00",
                    "ends_on": "2026-08-01 10:00:00",
                }
            )

    def test_subject_required(self):
        with self.assertRaises(frappe.ValidationError):
            activity.crm_event_save({"starts_on": "2026-08-01 10:00:00"})

    def test_starts_on_required(self):
        with self.assertRaises(frappe.ValidationError):
            activity.crm_event_save({"subject": "No start"})

    def test_unwritable_fields_are_dropped(self):
        r = activity.crm_event_save(
            {
                "subject": "Field filter",
                "starts_on": "2026-08-01 10:00:00",
                "owner": "Guest",
                "docstatus": 2,
            }
        )
        doc = frappe.get_doc("Event", r["name"])
        self.assertNotEqual(doc.owner, "Guest")
        self.assertEqual(doc.docstatus, 0)

    def test_participant_doctype_allowlisted(self):
        with self.assertRaises(frappe.PermissionError):
            activity.crm_event_save(
                {
                    "subject": "Bad participant",
                    "starts_on": "2026-08-01 10:00:00",
                    "participants": [
                        {"reference_doctype": "Animal Event", "reference_docname": "x"}
                    ],
                }
            )

    def test_update_event_replaces_participants(self):
        cust = frappe.get_all("Customer", limit=1)
        if not cust:
            self.skipTest("no Customer on site")
        r = activity.crm_event_save(
            {
                "subject": "With participant",
                "starts_on": "2026-08-01 10:00:00",
                "participants": [
                    {"reference_doctype": "Customer", "reference_docname": cust[0].name}
                ],
            }
        )
        doc = frappe.get_doc("Event", r["name"])
        self.assertEqual(len(doc.event_participants), 1)
        # Saving again with an empty list clears them.
        activity.crm_event_save(
            {
                "name": r["name"],
                "subject": "With participant",
                "starts_on": "2026-08-01 10:00:00",
                "participants": [],
            }
        )
        doc.reload()
        self.assertEqual(len(doc.event_participants), 0)

    def test_sync_dropped_when_no_authorized_calendar(self):
        if activity.crm_my_calendars():
            self.skipTest("current user has an authorized calendar")
        r = activity.crm_event_save(
            {
                "subject": "No sync for me",
                "starts_on": "2026-08-01 10:00:00",
                "sync_with_google_calendar": 1,
                "google_calendar": "Nonexistent Calendar",
            }
        )
        doc = frappe.get_doc("Event", r["name"])
        self.assertFalse(doc.sync_with_google_calendar)
        self.assertFalse(doc.google_calendar)

    def test_event_status_change(self):
        r = activity.crm_event_save(
            {"subject": "To close", "starts_on": "2026-08-01 10:00:00"}
        )
        activity.crm_event_status(r["name"], "Completed")
        self.assertEqual(frappe.db.get_value("Event", r["name"], "status"), "Completed")

    def test_event_status_rejects_unknown(self):
        r = activity.crm_event_save(
            {"subject": "Bad status", "starts_on": "2026-08-01 10:00:00"}
        )
        with self.assertRaises(frappe.ValidationError):
            activity.crm_event_status(r["name"], "Nonsense")

    def test_accepts_json_string_payload(self):
        import json as _json

        r = activity.crm_event_save(
            _json.dumps({"subject": "From JSON", "starts_on": "2026-08-01 10:00:00"})
        )
        self.assertEqual(frappe.db.get_value("Event", r["name"], "subject"), "From JSON")


class TestTaskSave(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_create_bare_task(self):
        r = activity.crm_task_save({"description": "Call the client", "priority": "High"})
        doc = frappe.get_doc("ToDo", r["name"])
        self.assertEqual(doc.priority, "High")
        self.assertEqual(doc.status, "Open")
        self.assertEqual(doc.assigned_by, frappe.session.user)

    def test_description_required(self):
        with self.assertRaises(frappe.ValidationError):
            activity.crm_task_save({"priority": "High"})

    def test_html_only_description_is_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            activity.crm_task_save({"description": "<div><br></div>"})

    def test_reference_type_allowlisted(self):
        with self.assertRaises(frappe.PermissionError):
            activity.crm_task_save(
                {"description": "x", "reference_type": "Animal Event", "reference_name": "y"}
            )

    def test_reference_type_without_name_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            activity.crm_task_save({"description": "x", "reference_type": "Lead"})

    def test_assignee_can_close_own_task(self):
        r = activity.crm_task_save(
            {"description": "Mine to close", "allocated_to": frappe.session.user}
        )
        activity.crm_task_status(r["name"], "Closed")
        self.assertEqual(frappe.db.get_value("ToDo", r["name"], "status"), "Closed")

    def test_manager_can_close_another_users_task(self):
        # Administrator holds System Manager, which is in MANAGER_ROLES.
        r = activity.crm_task_save(
            {"description": "Someone else's", "allocated_to": "Guest"}
        )
        activity.crm_task_status(r["name"], "Closed")
        self.assertEqual(frappe.db.get_value("ToDo", r["name"], "status"), "Closed")

    def test_non_assignee_non_manager_is_refused(self):
        r = activity.crm_task_save({"description": "Not yours", "allocated_to": "Guest"})
        todo = frappe.get_doc("ToDo", r["name"])
        # Force the "third party" branch: not the assignee, not assigned_by/owner,
        # and no manager role.
        todo.assigned_by = "Guest"
        todo.owner = "Guest"
        original = activity._is_manager
        activity._is_manager = lambda user=None: False
        try:
            with self.assertRaises(frappe.PermissionError):
                activity._assert_may_close(todo)
        finally:
            activity._is_manager = original

    def test_task_status_rejects_unknown(self):
        r = activity.crm_task_save({"description": "Bad status"})
        with self.assertRaises(frappe.ValidationError):
            activity.crm_task_status(r["name"], "Nonsense")

    def test_reopen_task(self):
        r = activity.crm_task_save(
            {"description": "Reopen me", "allocated_to": frappe.session.user}
        )
        activity.crm_task_status(r["name"], "Closed")
        activity.crm_task_status(r["name"], "Open")
        self.assertEqual(frappe.db.get_value("ToDo", r["name"], "status"), "Open")


class TestAssign(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def _a_lead(self):
        rows = frappe.get_all("Lead", limit=1)
        if not rows:
            self.skipTest("no Lead on site")
        return rows[0].name

    def test_assign_creates_todo_and_stamps_assign(self):
        lead = self._a_lead()
        r = activity.crm_assign("Lead", lead, ["Administrator"], description="Follow up")
        self.assertIn("Administrator", r["assignees"])
        todo = frappe.get_all(
            "ToDo",
            filters={
                "reference_type": "Lead",
                "reference_name": lead,
                "allocated_to": "Administrator",
                "status": "Open",
            },
        )
        self.assertTrue(todo)
        self.assertIn("Administrator", frappe.db.get_value("Lead", lead, "_assign") or "")

    def test_unassign_clears_assign(self):
        lead = self._a_lead()
        activity.crm_assign("Lead", lead, ["Administrator"])
        activity.crm_unassign("Lead", lead, "Administrator")
        self.assertNotIn(
            "Administrator", frappe.db.get_value("Lead", lead, "_assign") or ""
        )

    def test_assign_rejects_off_allowlist_doctype(self):
        with self.assertRaises(frappe.PermissionError):
            activity.crm_assign("Sales Invoice", "x", ["Administrator"])

    def test_assign_requires_users(self):
        lead = self._a_lead()
        with self.assertRaises(frappe.ValidationError):
            activity.crm_assign("Lead", lead, [])

    def test_assign_accepts_json_user_list(self):
        lead = self._a_lead()
        r = activity.crm_assign("Lead", lead, '["Administrator"]')
        self.assertIn("Administrator", r["assignees"])

    def test_assign_missing_record_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            activity.crm_assign("Lead", "NOPE-does-not-exist", ["Administrator"])


class TestCalendar(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_returns_event_in_window(self):
        r = activity.crm_event_save(
            {
                "subject": "In window",
                "starts_on": "2026-08-15 09:00:00",
                "ends_on": "2026-08-15 10:00:00",
            }
        )
        rows = activity.crm_calendar("2026-08-01", "2026-08-31")
        self.assertIn(r["name"], [x["name"] for x in rows])

    def test_excludes_event_outside_window(self):
        r = activity.crm_event_save(
            {"subject": "Outside", "starts_on": "2026-12-15 09:00:00"}
        )
        rows = activity.crm_calendar("2026-08-01", "2026-08-31")
        self.assertNotIn(r["name"], [x["name"] for x in rows])

    def test_expands_weekly_recurrence(self):
        # 2026-08-01 is a Saturday; a weekly Saturday event recurs across August.
        activity.crm_event_save(
            {
                "subject": "Weekly standup",
                "starts_on": "2026-08-01 09:00:00",
                "ends_on": "2026-08-01 09:30:00",
                "repeat_this_event": 1,
                "repeat_on": "Weekly",
                "repeat_till": "2026-08-31",
                "saturday": 1,
            }
        )
        rows = [
            x
            for x in activity.crm_calendar("2026-08-01", "2026-08-31")
            if x["subject"] == "Weekly standup"
        ]
        # Core expands one occurrence per matching weekday, not a single row.
        self.assertGreater(len(rows), 1)

    def test_shape_has_required_keys(self):
        activity.crm_event_save({"subject": "Shape", "starts_on": "2026-08-10 09:00:00"})
        rows = activity.crm_calendar("2026-08-01", "2026-08-31")
        self.assertTrue(rows)
        for k in ("name", "subject", "starts_on", "status"):
            self.assertIn(k, rows[0])


class TestEventsTasksReader(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_todos_exclude_non_crm_reference_types(self):
        from upande_crm.api.crm import crm_dashboard_events_tasks

        data = crm_dashboard_events_tasks(date_from="2000-01-01", date_to="2100-01-01")
        seen = {t.get("reference_type") for t in data["todos"]}
        self.assertNotIn("Issue", seen)
        self.assertNotIn("Animal Event", seen)
        self.assertNotIn("Task", seen)

    def test_todos_keep_unlinked_tasks(self):
        from upande_crm.api.crm import crm_dashboard_events_tasks

        r = activity.crm_task_save({"description": "Bare task kept"})
        data = crm_dashboard_events_tasks(date_from="2000-01-01", date_to="2100-01-01")
        self.assertIn(r["name"], [t["name"] for t in data["todos"]])

    def test_events_carry_form_fields(self):
        from upande_crm.api.crm import crm_dashboard_events_tasks

        activity.crm_event_save(
            {
                "subject": "Fields check",
                "starts_on": "2026-08-05 09:00:00",
                "ends_on": "2026-08-05 10:00:00",
                "location": "Nairobi",
            }
        )
        data = crm_dashboard_events_tasks(date_from="2026-08-01", date_to="2026-08-31")
        row = next(e for e in data["events"] if e["subject"] == "Fields check")
        for k in ("ends_on", "all_day", "location", "description", "participants"):
            self.assertIn(k, row)
