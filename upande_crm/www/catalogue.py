"""The buyer's catalogue page at /catalogue/<token> (routed in hooks.py).

A shell only: the page reads the catalogue from
upande_crm.api.catalogue_public.catalogue_view and posts back to
catalogue_submit, both guest endpoints that re-check the token on every call.
The title is the one thing rendered server-side, so a shared link previews with
the offer's name; this site's Jinja does not autoescape, so it is escaped here.
"""

import frappe
from frappe.utils import escape_html

no_cache = 1


def get_context(context):
	from upande_crm.api.catalogue_public import resolve_token

	token = (frappe.form_dict.get("token") or "").strip()
	context.token = escape_html(token)
	context.csrf_token = frappe.sessions.get_csrf_token() if frappe.session.user != "Guest" else ""
	try:
		doc, _link = resolve_token(token)
		company = frappe.db.get_value("Company", doc.company, "company_name") or doc.company
		context.page_title = escape_html(f"{doc.title} · {company}") if doc.status != "Draft" else "Offer"
	except frappe.DoesNotExistError:
		context.page_title = "Offer not available"
	context.no_breadcrumbs = 1
