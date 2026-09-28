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
        self._validate_theme_seeds()
        self._validate_theme_extras()
        self._validate_custpage()

    def _validate_theme_extras(self):
        """Corner sizes, fonts and custom CSS — each refused with a plain reason.

        These values end up inside a <style> or <link> on every CRM page, so
        anything that could close the tag or point at another host is refused
        here rather than filtered at render time.
        """
        from upande_crm.theme import fonts
        from upande_crm.theme.tokens import RADIUS_FIELDS, RADIUS_RE

        for field, _tokens in RADIUS_FIELDS:
            value = str(self.get(field) or "").strip()
            self.set(field, value)
            if value and not RADIUS_RE.match(value):
                frappe.throw(
                    _("{0}: corner sizes need a unit, e.g. 8px or 0.5rem (or 0 for square), not {1!r}.").format(
                        self.meta.get_label(field), value
                    )
                )

        url = str(self.theme_google_fonts_url or "").strip()
        self.theme_google_fonts_url = url
        if url and not fonts.is_allowed_url(url):
            frappe.throw(_("The Google Fonts link must start with https://fonts.googleapis.com."))
        for role, choice_field, name_field, _token in fonts.ROLES:
            if self.get(choice_field) != fonts.CUSTOM:
                continue
            label = self.meta.get_label(choice_field)
            name = str(self.get(name_field) or "").strip()
            self.set(name_field, name)
            if not name:
                frappe.throw(_("{0} is set to Custom: give the font family's name.").format(label))
            if not fonts.NAME_RE.match(name):
                frappe.throw(_("{0}: a font name can only hold letters, numbers, spaces and hyphens.").format(label))
            if not url:
                frappe.throw(_("{0} is set to Custom: add the Google Fonts link that loads it.").format(label))

        if "<" in str(self.theme_custom_css or ""):
            frappe.throw(_("Custom CSS cannot contain '<'."))

    def _validate_custpage(self):
        from upande_crm.modules import CUSTPAGE_TABS

        # Blank means "never filled in" and reads as the default (every tab), as
        # it does for every other field here — a Single saved before these
        # fields existed has them blank.
        tabs = [t.strip() for t in str(self.custpage_tabs or "").replace(",", "\n").splitlines() if t.strip()]
        if not tabs:
            tabs = list(CUSTPAGE_TABS)
        unknown = [t for t in tabs if t not in CUSTPAGE_TABS]
        if unknown:
            frappe.throw(
                _("Unknown customer page tab: {0}. Choose from {1}.").format(
                    ", ".join(unknown), ", ".join(CUSTPAGE_TABS)
                )
            )
        if self.custpage_default_tab and self.custpage_default_tab not in tabs:
            frappe.throw(_("The tab the customer page opens on must be one of its shown tabs."))

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

    def _validate_theme_seeds(self):
        """Each theme colour must be blank or a full '#rrggbb'.

        The token derivation skips an unparseable seed rather than raising, so a
        typo would otherwise silently drop half the palette. Caught here instead,
        where the user can see which field is wrong.
        """
        from upande_crm.theme.color import parse
        from upande_crm.theme.tokens import SEED_FIELDS

        for field in SEED_FIELDS:
            value = (self.get(field) or "").strip()
            self.set(field, value)
            if value and parse(value) is None:
                label = self.meta.get_label(field) if self.meta else field
                frappe.throw(
                    _("{0} must be a colour like #d9a514, not {1!r}.").format(label, value)
                )
