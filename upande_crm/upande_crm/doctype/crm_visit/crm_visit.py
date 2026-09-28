"""A farm visit by a customer, or a sales visit to one: why, what came of it,
and what has to happen next.

Follow-ups become real ToDos on save — referenced to the visit, allocated to
their owner — so they show in Events & Tasks and in the owner's own task list,
instead of living only on a record nobody reopens. Child rows get no controller
hook on a parent save (see frappe-migration-gotchas), so they are validated
here.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import strip_html


class CRMVisit(Document):
    def validate(self):
        self._validate_purpose()
        self._validate_outcome()
        self._validate_actions()

    def on_update(self):
        self._sync_todos()

    def _validate_purpose(self):
        from upande_crm.api.settings import DEFAULTS, get_settings, parse_lines

        allowed = parse_lines(get_settings().get("visit_purposes")) or parse_lines(DEFAULTS["visit_purposes"])
        if self.purpose not in allowed:
            frappe.throw(_("{0} is not a visit purpose. Choose from: {1}.").format(self.purpose, ", ".join(allowed)))

    def _validate_outcome(self):
        if self.status == "Completed" and not strip_html(self.outcome or "").strip():
            frappe.throw(_("Record what came of the visit before marking it completed."))

    def _validate_actions(self):
        for row in self.actions or []:
            row.action = (row.action or "").strip()
            if not row.action:
                frappe.throw(_("Follow-up {0} needs a description.").format(row.idx))

    def _sync_todos(self):
        for row in self.actions or []:
            if row.todo and frappe.db.exists("ToDo", row.todo):
                continue
            todo = frappe.get_doc({
                "doctype": "ToDo",
                "description": _("{0} — follow-up from visit {1} ({2})").format(row.action, self.name, self.party),
                "reference_type": "CRM Visit",
                "reference_name": self.name,
                "allocated_to": row.assigned_to or frappe.session.user,
                "date": row.due_date,
                "priority": "Medium",
                "status": "Open",
            }).insert(ignore_permissions=True)
            row.db_set("todo", todo.name, update_modified=False)
