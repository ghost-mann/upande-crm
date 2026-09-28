"""Switch on Claims, Quotations and Visits where they were placeholders.

Before these were built they were "coming soon" modules, and the module
backfill stored 0 for them on every existing site. That 0 was nobody's choice,
so it is replaced once. Fresh installs get 1 from the backfill directly, and a
site that switches them off afterwards keeps that choice: this runs once.
"""

import frappe

SETTINGS = "Upande CRM Settings"


def execute():
    for field in ("module_claims", "module_quotations", "module_visits"):
        frappe.db.set_single_value(SETTINGS, field, 1)
