"""The desk grid tile must open the CRM workspace and its sidebar.

Frappe's install creates an "External" App icon from `add_to_apps_screen`
whenever the app has no App icon of its own, and that one jumps straight to the
React dashboard in a new tab — no workspace, no sidebar. `ensure_desktop_icon`
makes the app's own tile a Workspace Sidebar icon so that never happens.
"""

import json
import os

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm import setup


class TestDesktopTile(FrappeTestCase):
    # In developer mode every save of a standard Desktop Icon re-exports
    # desktop_icon/upande_crm.json, rollback or not — a test that hides the tile
    # would ship a hidden tile. in_import suppresses that export.
    def setUp(self):
        frappe.flags.in_import = True

    def tearDown(self):
        frappe.flags.in_import = False

    def test_shipped_tile_is_visible_and_opens_the_sidebar(self):
        path = os.path.join(frappe.get_app_path("upande_crm"), "desktop_icon", "upande_crm.json")
        with open(path, encoding="utf-8") as handle:
            shipped = json.load(handle)
        self.assertEqual(shipped["hidden"], 0)
        self.assertEqual(shipped["icon_type"], "App")
        self.assertEqual(shipped["link_type"], "Workspace Sidebar")
        self.assertEqual(shipped["link_to"], "Upande CRM")
        self.assertEqual(shipped["standard"], 1)
    def test_tile_opens_the_workspace_sidebar(self):
        setup.ensure_desktop_icon()
        icon = frappe.get_doc("Desktop Icon", setup.DESKTOP_ICON)
        self.assertEqual(icon.icon_type, "App")
        self.assertEqual(icon.app, "upande_crm")
        self.assertEqual(icon.link_type, "Workspace Sidebar")
        self.assertEqual(icon.link_to, "Upande CRM")
        self.assertEqual(icon.link, "/desk/upande-crm")
        self.assertEqual(icon.standard, 1)

    def test_replaces_the_external_dashboard_tile(self):
        frappe.db.set_value("Desktop Icon", setup.DESKTOP_ICON,
                            {"link_type": "External", "link": "/customer-relationship-management", "standard": 0})
        setup.ensure_desktop_icon()
        self.assertEqual(frappe.db.get_value("Desktop Icon", setup.DESKTOP_ICON, "link_type"), "Workspace Sidebar")

    def test_a_hidden_tile_stays_hidden(self):
        setup.ensure_desktop_icon()
        frappe.db.set_value("Desktop Icon", setup.DESKTOP_ICON, "hidden", 1)
        setup.ensure_desktop_icon()
        self.assertEqual(frappe.db.get_value("Desktop Icon", setup.DESKTOP_ICON, "hidden"), 1)

    def test_the_workspace_sidebar_exists(self):
        self.assertTrue(frappe.db.exists("Workspace Sidebar", "Upande CRM"))


class TestAnimatedLogo(FrappeTestCase):
    """The desk tile and sidebar header draw the tile's logo as an <img>, so an
    SVG with its own CSS animation plays there. It is served to every desk user,
    so it must carry no script, and it must honour reduced motion."""

    PATH = ("public", "images", "upande-crm-logo.svg")

    def setUp(self):
        frappe.flags.in_import = True

    def tearDown(self):
        frappe.flags.in_import = False

    def _svg(self):
        with open(os.path.join(frappe.get_app_path("upande_crm"), *self.PATH), encoding="utf-8") as handle:
            return handle.read()

    def test_tile_uses_the_animated_logo(self):
        setup.ensure_desktop_icon()
        self.assertEqual(frappe.db.get_value("Desktop Icon", setup.DESKTOP_ICON, "logo_url"),
                         "/assets/upande_crm/images/upande-crm-logo.svg")

    def test_shipped_tile_uses_the_animated_logo(self):
        path = os.path.join(frappe.get_app_path("upande_crm"), "desktop_icon", "upande_crm.json")
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["logo_url"], "/assets/upande_crm/images/upande-crm-logo.svg")

    def test_svg_carries_no_script_or_external_reference(self):
        svg = self._svg().lower()
        for bad in ("<script", "javascript:", "onload", "onclick", "href=\"http", "@import", "url(http"):
            self.assertNotIn(bad, svg, bad)

    def test_svg_honours_reduced_motion(self):
        self.assertIn("prefers-reduced-motion", self._svg())

    def test_svg_plays_once(self):
        svg = self._svg()
        self.assertIn("@keyframes", svg)
        self.assertNotIn("infinite", svg)
