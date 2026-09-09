"""Delivery points at the Nairobi hub.

The thing worth protecting here is the honesty of the schematic. These handlers
have no coordinates, and the view arranges them in a ring — so the payload must
keep saying that the arrangement is not geography, and must keep reporting the
orders it leaves out.
"""

import unittest

import frappe

from upande_crm.api.logistics import (
    FIELD,
    JKIA,
    crm_delivery_point_detail,
    crm_delivery_points,
)

ALL_TIME = {"date_from": "2000-01-01", "date_to": "2035-12-31"}


class TestDeliveryPoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = crm_delivery_points(**ALL_TIME)

    def test_shape(self):
        for key in ("hub", "points", "unrouted"):
            self.assertIn(key, self.data)
        for p in self.data["points"]:
            for key in ("label", "orders", "customers", "value"):
                self.assertIn(key, p)

    def test_hub_is_jkia(self):
        self.assertEqual(self.data["hub"]["code"], "NBO")
        self.assertEqual(self.data["hub"]["territory"], "Kenya")
        lon, lat = self.data["hub"]["lonlat"]
        # Sanity-check the airport is where Kenya is, not transposed.
        self.assertTrue(36 < lon < 37, f"JKIA longitude {lon} is not in Kenya")
        self.assertTrue(-2 < lat < -1, f"JKIA latitude {lat} is not in Kenya")

    def test_schematic_flag_is_present(self):
        """The UI draws a ring; the payload must keep saying it is not a map."""
        if self.data["points"]:
            self.assertTrue(self.data["positions_are_schematic"])

    def test_no_point_carries_coordinates(self):
        """If this ever fails, real positions exist and the ring should go."""
        for p in self.data["points"]:
            self.assertNotIn("lonlat", p)
            self.assertNotIn("latitude", p)

    def test_points_are_ordered_by_volume(self):
        orders = [p["orders"] for p in self.data["points"]]
        self.assertEqual(orders, sorted(orders, reverse=True))

    def test_unrouted_is_reported_not_hidden(self):
        if not frappe.db.has_column("Sales Order", FIELD):
            self.skipTest("no delivery point field on this site")
        expected = frappe.db.sql(
            f"""select count(*) from `tabSales Order`
                where ifnull(`{FIELD}`, '') = '' and docstatus = 1"""
        )[0][0]
        self.assertEqual(self.data["unrouted"], expected)

    def test_totals_agree_with_a_direct_count(self):
        if not self.data["points"]:
            self.skipTest("no delivery points")
        rolled = sum(p["orders"] for p in self.data["points"])
        direct = frappe.db.sql(
            f"""select count(*) from `tabSales Order`
                where ifnull(`{FIELD}`, '') <> '' and docstatus = 1"""
        )[0][0]
        # The endpoint caps at `limit` points, so it may be a subset — never more.
        self.assertLessEqual(rolled, direct)


class TestDeliveryPointDetail(unittest.TestCase):
    def test_detail_of_the_busiest_point(self):
        points = crm_delivery_points(**ALL_TIME)["points"]
        if not points:
            self.skipTest("no delivery points")
        d = crm_delivery_point_detail(points[0]["label"], **ALL_TIME)
        self.assertEqual(d["point"], points[0]["label"])
        self.assertIsInstance(d["customers"], list)
        self.assertIsInstance(d["destinations"], list)

    def test_destinations_reconnect_to_territories(self):
        """The one join tying origin logistics back to the world map."""
        points = crm_delivery_points(**ALL_TIME)["points"]
        if not points:
            self.skipTest("no delivery points")
        d = crm_delivery_point_detail(points[0]["label"], **ALL_TIME)
        labels = [x["label"] for x in d["destinations"]]
        if not labels:
            self.skipTest("no destinations recorded")
        known = {t.name for t in frappe.get_all("Territory", fields=["name"])}
        for label in labels:
            self.assertTrue(
                label == "Untagged" or label in known,
                f"destination {label!r} is neither a Territory nor marked Untagged",
            )

    def test_blank_point_returns_empty(self):
        self.assertEqual(crm_delivery_point_detail("", **ALL_TIME), {})

    def test_unknown_point_does_not_raise(self):
        d = crm_delivery_point_detail("NO SUCH HANDLER", **ALL_TIME)
        self.assertEqual(d["customers"], [])
