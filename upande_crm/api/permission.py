"""Who may see the Upande CRM app icon on /apps.

`add_to_apps_screen` calls this with no arguments; a falsy return simply drops
the tile from the launcher. The role set is not redeclared here — it is read
from `upande_crm.api.crm.CRM_ROLES`, which is also what the whitelisted
endpoints and the SPA's page controller gate on, so the icon can never be
offered to someone the dashboard would then refuse.
"""

import frappe

from upande_crm.api.crm import CRM_ROLES


def has_app_permission() -> bool:
	if frappe.session.user == "Guest":
		return False
	return bool(set(frappe.get_roles(frappe.session.user)) & CRM_ROLES)
