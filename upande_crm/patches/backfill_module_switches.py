"""Give module switches their default on sites whose settings predate them.

A Check field added to an already-saved Single has no row in `tabSingles`, and
reads back as 0 — not as its JSON default. Left alone, every module on an
existing site would read as switched off. A missing row means "never chosen",
so only missing rows are filled; a saved 0 is somebody's decision and stays.

Called from `upande_crm.setup.setup` (after_install and before_migrate) rather
than patches.txt: install-app does not run patches, and this must hold on a
fresh install too. It is idempotent, so running on every migrate is harmless.
"""

import frappe

from upande_crm.modules import MODULES

SETTINGS_DOCTYPE = "Upande CRM Settings"


def execute():
    present = {
        r[0]
        for r in frappe.db.sql("select field from `tabSingles` where doctype=%s", SETTINGS_DOCTYPE)
    }
    for m in MODULES:
        if m.field not in present:
            frappe.db.set_single_value(SETTINGS_DOCTYPE, m.field, int(m.available))
