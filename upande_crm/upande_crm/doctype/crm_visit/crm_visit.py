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

    def _description(self, row):
        return _("{0} — follow-up from visit {1} ({2})").format(row.action, self.name, self.party)

    def _sync_todos(self):
        """Keep each follow-up and its ToDo in agreement.

        - a new follow-up gets a ToDo (unless the visit is cancelled);
        - an open ToDo follows its row: owner, due date, wording;
        - a cancelled visit, or a follow-up removed from it, cancels its open
          ToDo — a done one stays as history.
        """
        before = self.get_doc_before_save()
        kept = {row.todo for row in self.actions or [] if row.todo}
        dropped = {row.todo for row in (before.actions if before else []) if row.todo} - kept
        cancelled = self.status == "Cancelled"

        for todo in dropped:
            self._cancel(todo)
        for row in self.actions or []:
            if row.todo and frappe.db.exists("ToDo", row.todo):
                if cancelled:
                    self._cancel(row.todo)
                    continue
                current = frappe.db.get_value("ToDo", row.todo, ["status", "allocated_to", "date", "description"],
                                              as_dict=True)
                if current.status != "Open":
                    continue
                wanted = {"allocated_to": row.assigned_to or current.allocated_to,
                          "date": row.due_date or None, "description": self._description(row)}
                if any(str(current.get(k) or "") != str(v or "") for k, v in wanted.items()):
                    todo = frappe.get_doc("ToDo", row.todo)
                    todo.update(wanted)
                    todo.save(ignore_permissions=True)
                continue
            if cancelled:
                continue
            todo = frappe.get_doc({
                "doctype": "ToDo",
                "description": self._description(row),
                "reference_type": "CRM Visit",
                "reference_name": self.name,
                "allocated_to": row.assigned_to or frappe.session.user,
                "date": row.due_date,
                "priority": "Medium",
                "status": "Open",
            }).insert(ignore_permissions=True)
            row.db_set("todo", todo.name, update_modified=False)

    @staticmethod
    def _cancel(todo):
        if frappe.db.get_value("ToDo", todo, "status") == "Open":
            doc = frappe.get_doc("ToDo", todo)
            doc.status = "Cancelled"
            doc.save(ignore_permissions=True)
