"""A magazine template: the look, wording and grouping a catalogue is shown
with. Values reach a guest page, so the checks here are what keep that page
safe and readable: colours are strict hex, spec keys are slugs, and there is
always at least one frequency to order at."""

import re

import frappe
from frappe import _
from frappe.model.document import Document

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
SLUG = re.compile(r"^[a-z][a-z0-9_]{0,30}$")
COLOURS = ("brand", "brand_ink", "paper", "ink", "accent", "accent_ink")


class CRMCatalogueTemplate(Document):
    def validate(self):
        for field in COLOURS:
            self._hex(self.get(field), self.meta.get_label(field))
        for row in self.colour_groups or []:
            self._hex(row.swatch, _("swatch of {0}").format(row.label), blank_ok=True)
            self._hex(row.swatch_ink, _("swatch text of {0}").format(row.label), blank_ok=True)
        for row in self.badges or []:
            self._hex(row.background, _("badge {0}").format(row.label), blank_ok=True)
            self._hex(row.ink, _("badge {0} text").format(row.label), blank_ok=True)
        self._unique([r.label for r in self.colour_groups or []], _("colour group"))
        self._unique([r.label for r in self.badges or []], _("badge"))
        keys = [r.key for r in self.spec_columns or []]
        bad = [k for k in keys if not SLUG.match(k or "")]
        if bad:
            frappe.throw(_("Spec keys must be lower-case words joined by underscores, like cup_score: {0}").format(
                ", ".join(map(str, bad))))
        self._unique(keys, _("spec key"))
        if not self.frequencies:
            frappe.throw(_("Add at least one frequency buyers can order at, e.g. One-off."))
        self._unique([r.label for r in self.frequencies], _("frequency"))

    def on_trash(self):
        from upande_crm.catalogue_templates import DEFAULT_TEMPLATE

        if self.name == DEFAULT_TEMPLATE:
            frappe.throw(_("{0} is the template new catalogues start with, so it cannot be deleted. "
                           "Edit it, or copy it and change the copy.").format(self.name))
        n = frappe.db.count("CRM Catalogue", {"template": self.name})
        if n:
            frappe.throw(_("{0} catalogue(s) use the template {1}. Move them to another template first.").format(
                n, self.name))

    def frequency_labels(self):
        return [r.label for r in self.frequencies or []]

    @staticmethod
    def _hex(value, label, blank_ok=False):
        if (value or "") == "" and blank_ok:
            return
        if not HEX.match(value or ""):
            frappe.throw(_("{0} must be a colour like #1E4D3A, not {1}.").format(label, frappe.bold(value or "blank")))

    @staticmethod
    def _unique(values, what):
        seen = set()
        for v in values:
            if v in seen:
                frappe.throw(_("The {0} {1} appears twice.").format(what, frappe.bold(v)))
            seen.add(v)
