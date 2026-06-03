"""Server-side boot context for the Upande CRM dashboard at /customer-relationship-management.

Requires login + a sales/CRM role. Boot exposes the csrf token + user info; the
React app loads everything else via the upande_crm.api.crm.* whitelisted methods.
"""

import frappe
from frappe import _

no_cache = 1

# Mirrors upande_crm.api.crm.CRM_ROLES — who may see the sales CRM.
CRM_ROLES = {"System Manager", "Sales Manager", "Sales User", "CRM Manager", "CRM User"}


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in to access the CRM."), frappe.PermissionError)

	roles = set(frappe.get_roles(frappe.session.user))
	if not (roles & CRM_ROLES):
		frappe.throw(_("You do not have access to the CRM."), frappe.PermissionError)

	full_name, user_image = frappe.db.get_value(
		"User", frappe.session.user, ["full_name", "user_image"]
	) or (None, None)

	context.boot = {
		"csrf_token":        frappe.sessions.get_csrf_token(),
		"frappe_user":       frappe.session.user,
		"frappe_user_full":  full_name or frappe.session.user,
		"frappe_user_image": user_image or "",
		# In CRM the user is always sales; expose flags so the shared shell can
		# render the right tabs without an extra API round-trip.
		"is_staff":           True,
		"is_crm":             True,
		"is_account_manager": frappe.db.exists("Customer", {"account_manager": frappe.session.user}) and True or False,
	}
	return context
