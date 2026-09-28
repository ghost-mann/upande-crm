"""Give new settings fields their default on sites whose settings predate them.

A field added to an already-saved Single has no row in `tabSingles`, and reads
back as 0 or blank — not as its JSON default. For a module switch that means
"off"; for a bounded Int (claim_sla_days) it means every later settings save is
refused by the range check. A missing row means "never chosen", so only missing
rows are filled, from the doctype's own defaults; a saved value is somebody's
decision and stays.

Called from `upande_crm.setup.setup` (after_install and before_migrate) rather
than patches.txt: install-app does not run patches, and this must hold on a
fresh install too. It is idempotent, so running on every migrate is harmless.
"""

import frappe

from upande_crm.modules import MODULES

SETTINGS_DOCTYPE = "Upande CRM Settings"


def _defaults():
    """{field: default} from the doctype JSON, plus the module switches.

    Module switches default to whether the module is built, which is what the
    registry says — the JSON default and the registry are kept in step by
    test_modules, but the registry is the authority.
    """
    out = {}
    try:
        meta = frappe.get_meta(SETTINGS_DOCTYPE)
        for f in meta.fields:
            if f.default not in (None, "") and f.fieldtype not in ("Section Break", "Column Break", "Tab Break"):
                out[f.fieldname] = f.default
    except Exception:
        pass
    for m in MODULES:
        out[m.field] = int(m.available)
    return out


def execute():
    present = {
        r[0]
        for r in frappe.db.sql("select field from `tabSingles` where doctype=%s", SETTINGS_DOCTYPE)
    }
    if not present:
        # Never saved: Frappe applies the JSON defaults to a new Single itself.
        # Writing a few rows here would stop it doing that for the rest.
        return
    for field, default in _defaults().items():
        if field not in present:
            frappe.db.set_single_value(SETTINGS_DOCTYPE, field, default)
