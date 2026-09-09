# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

"""Keep the CRM tile on the apps screen honest, on every migrate.

`desktop_icon/upande_crm.json` ships the tile, so a fresh install needs nothing
and a plain `bench migrate` keeps the *icon record* current.

A site where somebody has rearranged their apps screen needs more. From then on
Frappe renders that user's stored `Desktop Layout` snapshot instead of the live
icon list, and a snapshot holds a **copy** of each icon's fields - so editing
the fixture changes nothing on screen. Two things go wrong:

  * the fixture's tile may never have been in the snapshot, so it is invisible;
  * the apps-screen editor can leave a placeholder behind ("Upande CRM" with no
    app, no `link_to` and no logo, under a generated `new-desktop-icon-*` name)
    that has no backing `Desktop Icon` at all. It draws as a dead tile.

This runs from `after_migrate` rather than as a one-shot patch on purpose. A
patch records itself in `Patch Log` and never runs again, which is wrong for a
snapshot that has to be reconciled against the fixture *every* time the logo or
route changes - the next change would need yet another patch. Reconciling here
is idempotent and writes only when something actually differs.

Only this app's own tile is touched. Every other row is passed through byte for
byte, so another app's tiles and the user's arrangement both survive.
"""

import json

import frappe

ICON = "Upande CRM"
APP = "upande_crm"

# The fields a layout row copies from the icon.
FIELDS = [
	"name",
	"label",
	"bg_color",
	"link",
	"link_type",
	"app",
	"icon_type",
	"parent_icon",
	"icon",
	"link_to",
	"idx",
	"standard",
	"logo_url",
	"hidden",
	"restrict_removal",
	"icon_image",
]


def sync_desktop_tile():
	icon = frappe.db.get_value("Desktop Icon", ICON, FIELDS, as_dict=True)
	if not icon:
		# Fixture has not synced yet; the next migrate reconciles.
		return

	entry = {**icon, "child_icons": []}

	for name in frappe.get_all("Desktop Layout", pluck="name"):
		doc = frappe.get_doc("Desktop Layout", name)
		try:
			layout = json.loads(doc.layout or "[]")
		except ValueError:
			continue
		if not isinstance(layout, list):
			continue

		kept, placement = [], None
		for row in layout:
			if not isinstance(row, dict):
				continue
			if not _is_ours(row):
				kept.append(row)
				continue
			# Remember where the user put it, from whichever row matched first,
			# then emit one refreshed entry below. Matching rows are dropped
			# here, so a snapshot holding both the placeholder and the real tile
			# collapses to a single tile.
			if placement is None:
				placement = {"idx": row.get("idx"), "parent_icon": row.get("parent_icon")}

		if placement is None:
			placement = {"idx": entry.get("idx"), "parent_icon": None}
		kept.append({**entry, **placement})

		if kept != layout:
			doc.layout = json.dumps(kept)
			doc.save(ignore_permissions=True)


def _is_ours(row: dict) -> bool:
	"""True for the fixture's tile, and for any placeholder standing in for it.

	The placeholder carries our label but none of our identity, so the label is
	the only handle on it - paired with a check that nothing backs it, to avoid
	catching a tile a user deliberately labelled the same.
	"""
	if row.get("app") == APP or row.get("name") == ICON:
		return True
	return row.get("label") == ICON and not frappe.db.exists("Desktop Icon", row.get("name"))
