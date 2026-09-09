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
#
# The two surfaces carry two logos on purpose. The launcher tile is wide enough for
# the wordmark (`images/logo.png`, 237x213). The desk grid tile is small and square,
# so `desktop_icon/upande_crm.json` points at the square badge instead — the same
# 689x689 `upande-logo.png` the IT Operations tile uses, so the two sit level on the
# apps screen. It is copied in rather than read across from `/assets/upande_core/`
# so the icon does not break on a site that has the CRM without upande_core. Keep
# the two files byte-identical; a smaller copy of the same artwork upscales soft at
# tile size, which is what the earlier 180x180 version got wrong.
add_to_apps_screen = [
	{
		"name": "upande_crm",
		"logo": "/assets/upande_crm/images/logo.png",
		"title": "Upande CRM",
		"route": "/customer-relationship-management",
		"has_permission": "upande_crm.api.permission.has_app_permission",
	}
]

# Creates the two CRM roles the workspaces gate on, and the Custom HTML Block
# the parent workspace renders. `before_migrate` rather than `after_migrate`,
# because sync_all() imports the workspace fixtures that reference both.
after_install = "upande_crm.setup.setup"
before_migrate = "upande_crm.setup.setup"

# Reconciles the desk grid tile against every stored apps-screen arrangement.
# `after_migrate`, because it reads back the `Desktop Icon` that sync_all() has
# just imported. See upande_crm/apps_screen.py for why this is a hook and not a
# one-shot patch.
after_migrate = "upande_crm.apps_screen.sync_desktop_tile"

# The one document hook in this app. `Prospect.make_opportunity` maps four fields
# and Prospect owns no contact field, so an opportunity raised from a prospect used
# to land with nobody to call — 0 of 8 on this site carried a contact. Hooked rather
# than fixed in `api/leads.py` so the desk's own convert button gets it too. See
# upande_crm/handover.py for why this one is allowed to swallow its exceptions.
doc_events = {
	"Opportunity": {
		"before_insert": "upande_crm.handover.before_insert",
	},
}
