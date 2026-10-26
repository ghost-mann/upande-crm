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


def _asset_version():
	"""A short hash of the page's script and stylesheet. /assets is cached for
	hours, so without it a browser that opened an earlier version keeps the old
	script after an update, and the old script cannot read the new payload."""
	import hashlib
	import os

	base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public", "catalogue")
	h = hashlib.md5()
	for name in ("catalogue.js", "catalogue.css"):
		with open(os.path.join(base, name), "rb") as fh:
			h.update(fh.read())
	return h.hexdigest()[:10]


def get_context(context):
	from upande_crm.api.catalogue_public import resolve_token

	context.asset_v = _asset_version()

	token = (frappe.form_dict.get("token") or "").strip()
	context.token = escape_html(token)
	context.csrf_token = frappe.sessions.get_csrf_token() if frappe.session.user != "Guest" else ""
	context.preview_name = ""
	try:
		doc, _link = resolve_token(token)
		company = frappe.db.get_value("Company", doc.company, "company_name") or doc.company
		context.page_title = escape_html(f"{doc.title} · {company}") if doc.status != "Draft" else "Offer"
		# Preview mode (the template editor's iframe): CRM users only; the page
		# then reads crm_catalogue_preview, which records nothing.
		if frappe.form_dict.get("preview") and _is_crm_user():
			context.preview_name = escape_html(doc.name)
	except frappe.DoesNotExistError:
		context.page_title = "Offer not available"
	context.no_breadcrumbs = 1


def _is_crm_user():
	from upande_crm.api.crm import CRM_ROLES

	return frappe.session.user != "Guest" and bool(set(frappe.get_roles()) & CRM_ROLES)
