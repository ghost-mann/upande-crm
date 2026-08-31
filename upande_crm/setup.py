"""Install-time setup for the Upande CRM desk surface.

Two jobs: create the roles the workspaces gate on, and install the navigation
block the parent workspace renders. Both run before `sync_all()` imports the
workspace fixtures that reference them.

`upande_crm.api.crm.CRM_ROLES` has always named CRM Manager and CRM User, but
neither role is shipped by Frappe or ERPNext, so on most sites they simply did
not exist — the role set silently degraded to the three ERPNext sales roles.
The desk workspaces are gated on the same set, so the roles are created here.

Wired to both `after_install` and `before_migrate` so a fresh install and an
upgrade converge on the same state, and so the roles exist before `sync_all()`
imports the workspace fixtures that reference them.

## The two roles carry real permissions

They used to be tags with no DocPerm rows, which made them a trap: holding one
passed `upande_crm.api.crm._guard()` and opened the dashboard, and then every
write was refused and every button hidden, because permission to *create* the
target is checked per hop in `api/advance.py`. A role that gets you in and lets
you do nothing is worse than no role.

`CRM_ROLE_PERMS` below models CRM User on Sales User and CRM Manager on Sales
Manager, with the two gaps in those roles closed, because the dashboard needs
every hop to work:

  * Sales User cannot create a **Prospect** -- so "To prospect" is dead for them.
  * Sales Manager cannot create a **Customer** -- so every customer hop is dead.

`Contact` and `Address` are in the table because they are not incidental: when a
lead becomes a customer, `api/carry_across.py` inserts both under the user's own
permissions, and without them the customer arrives with no email address.

Only ever grants. Nothing here revokes a permission a site has set, so a farm
that has tightened these roles keeps its decision.
"""

import frappe

from upande_crm.api.crm import CRM_ROLES

# The subset of CRM_ROLES this app owns; the rest come from Frappe/ERPNext.
OWNED_ROLES = ("CRM Manager", "CRM User")

# What each owned role may do, per doctype and permission level.
#
# CRM User mirrors Sales User; CRM Manager mirrors Sales Manager, whose only real
# advantage on this site is `export` plus write on Quotation's level-1 fields.
# Neither gets `delete`, matching the sales roles.
#
# Level 1 rows are included where the sales roles have them: without them the
# permlevel-1 fields on Lead, Quotation and Customer are invisible, and a form
# that hides half its fields reads as broken rather than as restricted.
_USER = "read,write,create,report,print,email,share"
_MANAGER = _USER + ",export"

CRM_ROLE_PERMS = {
	"CRM User": {
		("Lead", 0): _USER,
		("Lead", 1): "read,report",
		("Prospect", 0): _USER,
		("Opportunity", 0): _USER,
		# Submit/cancel/amend match Sales User. The dashboard never submits — it
		# raises drafts — but a user holding only this role has to be able to
		# finish the quote in the desk.
		("Quotation", 0): _USER + ",submit,cancel,amend",
		("Quotation", 1): "read,report",
		("Customer", 0): _USER,
		("Customer", 1): "read",
		("Contact", 0): _USER,
		("Address", 0): _USER,
		# Read-only: the variety picker searches items, it never creates one.
		("Item", 0): "read",
	},
	"CRM Manager": {
		("Lead", 0): _MANAGER,
		("Lead", 1): "read,report",
		("Prospect", 0): _MANAGER,
		("Opportunity", 0): _MANAGER,
		("Quotation", 0): _MANAGER + ",submit,cancel,amend",
		("Quotation", 1): "read,write,report",
		("Customer", 0): _MANAGER,
		("Customer", 1): "read",
		("Contact", 0): _MANAGER,
		("Address", 0): _MANAGER,
		("Item", 0): "read",
	},
}


def ensure_crm_roles():
	for role in OWNED_ROLES:
		assert role in CRM_ROLES, f"{role} is no longer in CRM_ROLES"
		if frappe.db.exists("Role", role):
			continue
		frappe.get_doc(
			{"doctype": "Role", "role_name": role, "desk_access": 1}
		).insert(ignore_permissions=True)
	frappe.db.commit()


def ensure_crm_role_permissions():
	"""Grant `CRM_ROLE_PERMS`, additively.

	`add_permission` copies a doctype's standard DocPerms into Custom DocPerm
	before adding to it, so existing roles keep exactly what they had. A doctype
	this site does not have is skipped rather than raising: `Prospect` and
	`Quotation` come from ERPNext, and this app has to install on a site without
	it.
	"""
	from frappe.permissions import add_permission, update_permission_property

	granted = 0
	for role, table in CRM_ROLE_PERMS.items():
		if not frappe.db.exists("Role", role):
			continue
		for (doctype, permlevel), flags in table.items():
			if not frappe.db.exists("DocType", doctype):
				continue
			try:
				add_permission(doctype, role, permlevel)
				for flag in flags.split(","):
					update_permission_property(doctype, role, permlevel, flag, 1)
				granted += 1
			except Exception:
				# One unavailable doctype must not stop the rest of the grant, and
				# must not fail a migrate.
				frappe.log_error(
					"Upande CRM role permissions",
					f"Could not grant {role} on {doctype} (level {permlevel})",
				)
	frappe.db.commit()
	return granted


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
    ensure_crm_role_permissions()
    ensure_nav_block()
    hide_workspaces()
