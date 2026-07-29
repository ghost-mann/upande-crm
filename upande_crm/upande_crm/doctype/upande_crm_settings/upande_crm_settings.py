"""Controller for the CRM's organisation-wide settings.

Validation throws rather than clamping. A silently corrected value leaves the
user believing they configured something they did not — and these values drive
dashboard numbers, so a wrong one is a wrong report.

Field defaults live in the doctype JSON; `upande_crm.api.settings.DEFAULTS`
mirrors them for sites where this doctype is not (yet) installed. Keep the two
in step.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

# (fieldname, label, minimum, maximum) for every bounded numeric.
BOUNDS = (
    ("refresh_interval_sec", "Refresh interval", 15, 3600),
    ("top_n", "Top-N chart rows", 3, 20),
    ("default_task_due_days", "Default task due in (days)", 0, 365),
    ("default_event_duration_mins", "Default event duration (minutes)", 5, 1440),
    ("whatsapp_fail_rate_alert", "WhatsApp failure rate alert", 0, 100),
)

TARGET_FIELDS = (
    ("revenue_target_monthly", "Monthly revenue target"),
    ("revenue_target_annual", "Annual revenue target"),
)

STATUS_FIELDS = (
    ("lead_open_statuses", "Open lead statuses"),
    ("opportunity_open_statuses", "Open opportunity statuses"),
)


def parse_list(text):
    """Comma-separated text -> a list of trimmed, non-empty values.

    Statuses are multi-word on this site ("Sent/Received Email", "In Process"),
    so only commas separate — never whitespace.
    """
    return [p.strip() for p in str(text or "").split(",") if p.strip()]


class UpandeCRMSettings(Document):
    def validate(self):
        self._validate_bounds()
        self._validate_targets()
        self._validate_statuses()
        self._validate_whatsapp_template()

    def _validate_bounds(self):
        for field, label, low, high in BOUNDS:
            value = flt(self.get(field))
            if value < low or value > high:
                frappe.throw(
                    _("{0} must be between {1} and {2}.").format(label, low, high),
                    title=_("Out of range"),
                )

    def _validate_targets(self):
        for field, label in TARGET_FIELDS:
            if flt(self.get(field)) < 0:
                frappe.throw(_("{0} cannot be negative.").format(label))

    def _validate_statuses(self):
        for field, label in STATUS_FIELDS:
            if not parse_list(self.get(field)):
                frappe.throw(
                    _("{0} needs at least one status, comma-separated.").format(label)
                )

    def _validate_whatsapp_template(self):
        """A default template must exist and be sendable.

        Guarded on the doctype's presence: `frappe_whatsapp` is optional, and
        this setting must not become unsaveable on a site without it.
        """
        template = (self.default_whatsapp_template or "").strip()
        self.default_whatsapp_template = template
        if not template:
            return
        try:
            available = frappe.db.exists("DocType", "WhatsApp Templates")
        except Exception:
            available = False
        if not available:
            frappe.throw(_("WhatsApp is not installed on this site, so no template can be set."))
        if not frappe.db.exists("WhatsApp Templates", template):
            frappe.throw(_("WhatsApp template {0} does not exist.").format(template))
        if frappe.db.get_value("WhatsApp Templates", template, "status") != "APPROVED":
            frappe.throw(_("WhatsApp template {0} is not APPROVED, so it cannot be sent.").format(template))
