"""Install-time setup for the Upande CRM desk surface.

Two jobs: create the roles the workspaces gate on, and install the navigation
block the parent workspace renders. Both run before `sync_all()` imports the
workspace fixtures that reference them.

`upande_crm.api.crm.CRM_ROLES` has always named CRM Manager and CRM User, but
neither role is shipped by Frappe or ERPNext, so on most sites they simply did
not exist — the role set silently degraded to the three ERPNext sales roles.
The desk workspaces are gated on the same set, so the roles are created here.

They are tags only: no DocPerm rows are attached, and holding one grants no
access on its own. Wired to both `after_install` and `before_migrate` so a
fresh install and an upgrade converge on the same state, and so the roles exist
before `sync_all()` imports the workspace fixtures that reference them.
"""

import frappe

from upande_crm.api.crm import CRM_ROLES

# The subset of CRM_ROLES this app owns; the rest come from Frappe/ERPNext.
OWNED_ROLES = ("CRM Manager", "CRM User")


def ensure_crm_roles():
	for role in OWNED_ROLES:
		assert role in CRM_ROLES, f"{role} is no longer in CRM_ROLES"
		if frappe.db.exists("Role", role):
			continue
		frappe.get_doc(
			{"doctype": "Role", "role_name": role, "desk_access": 1}
		).insert(ignore_permissions=True)
	frappe.db.commit()


# ---------------------------------------------------------------- nav block
# The workspace body is a Custom HTML Block — a tile grid, matching the
# navigation blocks used elsewhere at Upande. It cannot ship as a module fixture
# folder: `Custom HTML Block` is not in Frappe's IMPORTABLE_DOCTYPES, so
# `sync_all()` would walk straight past it. Hence this upsert, wired to
# `before_migrate` so the block exists by the time the workspace that references
# it is imported.
#
# The markup lives in upande_crm/custom_html_block/ as real .html/.css/.js files
# rather than as strings in here, so it stays diffable and editable.
NAV_BLOCK = "Upande CRM Navigation"
_BLOCK_DIR = "custom_html_block"
_BLOCK_SLUG = "upande_crm_navigation"


def _block_sources():
    import os

    base = os.path.join(os.path.dirname(__file__), _BLOCK_DIR, _BLOCK_SLUG)
    out = {}
    for field, ext in (("html", "html"), ("style", "css"), ("script", "js")):
        with open(f"{base}.{ext}", encoding="utf-8") as fh:
            out[field] = fh.read()
    return out


def ensure_nav_block():
    """Create or refresh the workspace's navigation block from the app's files.

    Overwrites on every migrate, deliberately: the files in the app are the
    source of truth. Anyone editing the block in the UI should expect the next
    migrate to reset it — edit the files instead.
    """
    src = _block_sources()
    if frappe.db.exists("Custom HTML Block", NAV_BLOCK):
        doc = frappe.get_doc("Custom HTML Block", NAV_BLOCK)
    else:
        doc = frappe.new_doc("Custom HTML Block")
        doc.name = NAV_BLOCK
    doc.update(src)
    # Public, and readable by anyone who can reach the workspace. Per-tile role
    # gating happens in the block's own script; putting roles here instead would
    # hide the whole grid rather than the one tile that needs hiding.
    doc.private = 0
    doc.set("roles", [])
    doc.save(ignore_permissions=True)
    frappe.db.commit()


# ---------------------------------------------------------------- hidden pages
# Analytics and Reports are kept out of navigation: no tile on the workspace, no
# section in the desk sidebar, and hidden from any workspace listing. The pages
# and their routes still work, so nothing is lost — /desk/analytics and
# /desk/reports resolve as before.
#
# This cannot live in the workspace fixtures. frappe.modules.import_file declares
# `ignore_values = {"Workspace": ["is_hidden"]}`, so the field is stripped on
# every import and a fixture that sets it is silently ignored. The JSON still
# carries the intended value for readability; this is what actually applies it.
HIDDEN_WORKSPACES = ("Analytics", "Reports")


def hide_workspaces():
    for name in HIDDEN_WORKSPACES:
        if frappe.db.exists("Workspace", name):
            frappe.db.set_value("Workspace", name, "is_hidden", 1, update_modified=False)
    frappe.db.commit()


def setup():
    ensure_crm_roles()
    ensure_nav_block()
    hide_workspaces()
