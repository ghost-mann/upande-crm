"""Install-time setup for the Upande CRM desk surface.

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
