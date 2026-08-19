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

# The /apps launcher tile, which routes straight to the React dashboard —
# distinct from the desk grid tile in upande_crm/desktop_icon/, which opens the
# Workspace Sidebar. Two surfaces, two entries: the desk one has to be
# `link_type: Workspace Sidebar` because sidebar_header.js never draws an
# External icon, so it cannot double as the route to the SPA. The dashboard is
# still one click from the desk, pinned at the bottom of that sidebar.
# `has_permission` keeps this tile off the launcher for anyone the dashboard
# would refuse.
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
