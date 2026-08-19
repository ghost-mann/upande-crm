app_name = "upande_crm"
app_title = "Upande CRM"
app_publisher = "Upande Limited"
app_description = "Custom CRM dashboard for Upande (leads, opportunities, prospects, customers, mail)."
app_email = "dev@upande.com"
app_license = "mit"
# required_apps = []

# The CRM SPA is served at /customer-relationship-management by upande_crm/www/customer-relationship-management.{html,py}. The built
# Vite assets live under upande_crm/public/frontend/ and are served by Frappe
# at /assets/upande_crm/frontend/ (matching the frontend build `base`).

# Desk app icon. Routes straight to the React dashboard rather than the desk
# workspace: the workspace tree is reachable from the desk sidebar anyway, and
# the dashboard is what people open the app for. `has_permission` keeps the tile
# off the launcher for anyone the dashboard would refuse.
add_to_apps_screen = [
	{
		"name": "upande_crm",
		"logo": "/assets/upande_crm/images/logo.png",
		"title": "Upande CRM",
		"route": "/customer-relationship-management",
		"has_permission": "upande_crm.api.permission.has_app_permission",
	}
]

# CRM Manager / CRM User are named in upande_crm.api.crm.CRM_ROLES but shipped
# by nobody, so this app creates them. `before_migrate` (not `after_migrate`)
# because the workspace fixtures that gate on them are imported by sync_all().
after_install = "upande_crm.setup.ensure_crm_roles"
before_migrate = "upande_crm.setup.ensure_crm_roles"
