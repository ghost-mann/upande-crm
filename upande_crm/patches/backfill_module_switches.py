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


def _meta_fields():
    return frappe.get_meta(SETTINGS_DOCTYPE).fields


def _defaults():
    """{field: default}, from the shipped doctype JSON first, then the live meta,
    plus the module switches.

    The JSON on disk is the authority because setup() runs on before_migrate —
    before model sync — so a field added in this release is not in the meta yet.
    Reading only the meta left new fields unset on the first migrate after an
    upgrade, and a bounded Int among them made every settings save fail.

    Module switches default to whether the module is built, which is what the
    registry says.
    """
    import json
    import os

    skip = ("Section Break", "Column Break", "Tab Break", "HTML")
    out = {}
    try:
        path = os.path.join(frappe.get_app_path("upande_crm"), "upande_crm", "doctype",
                            "upande_crm_settings", "upande_crm_settings.json")
        with open(path, encoding="utf-8") as handle:
            for f in json.load(handle).get("fields", []):
                if f.get("default") not in (None, "") and f.get("fieldtype") not in skip:
                    out[f["fieldname"]] = f["default"]
    except Exception:
        pass
    try:
        for f in _meta_fields():
            if f.default not in (None, "") and f.fieldtype not in skip:
                out.setdefault(f.fieldname, f.default)
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
