"""A customer complaint or quality claim, tracked to resolution.

The controller owns the facts the reports are built on: the type must be one
the organisation configured, the order or delivery must be the customer's own,
a closed claim must say how it was closed, and `resolved_on` — what "days to
resolve" is measured from — is set here, not by whoever filled in the form.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate

CLOSED = ("Resolved", "Rejected")


class CRMClaim(Document):
    def validate(self):
        self._validate_type()
        self._validate_reference()
        self._validate_amounts()
        self._validate_closure()

    def _validate_type(self):
        from upande_crm.api.settings import DEFAULTS, get_settings, parse_lines

        allowed = parse_lines(get_settings().get("claim_types")) or parse_lines(DEFAULTS["claim_types"])
        if self.claim_type not in allowed:
            frappe.throw(
                _("{0} is not a claim type. Choose from: {1}.").format(self.claim_type, ", ".join(allowed))
            )

    def _validate_reference(self):
        if not self.reference_name:
            self.reference_doctype = self.reference_doctype or None
            return
        if not self.reference_doctype:
            frappe.throw(_("Say whether the claim is against an invoice, a delivery or an order."))
        owner = frappe.db.get_value(self.reference_doctype, self.reference_name, "customer")
        if owner is None:
            frappe.throw(_("{0} {1} not found.").format(self.reference_doctype, self.reference_name))
        if owner != self.customer:
            frappe.throw(
                _("{0} {1} belongs to {2}, not {3}.").format(
                    self.reference_doctype, self.reference_name, owner, self.customer
                )
            )

    def _validate_amounts(self):
        for field in ("amount_claimed", "amount_credited", "qty_affected"):
            if flt(self.get(field)) < 0:
                frappe.throw(_("{0} cannot be negative.").format(self.meta.get_label(field)))

    def _validate_closure(self):
        if self.status in CLOSED:
            if not (self.resolution or "").strip():
                frappe.throw(_("Say how the claim was {0}: fill in the Resolution.").format(self.status.lower()))
            if not self.resolved_on:
                self.resolved_on = nowdate()
        else:
            self.resolved_on = None
