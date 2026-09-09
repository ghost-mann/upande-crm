"""Territory map rollups, and the name -> ISO table the map joins on.

The reconciliation test is the important one here. A choropleth silently drops
whatever it cannot paint, so the failure mode this feature has to be protected
against is not an exception — it is a map that looks fine while hiding a third
of the revenue. `test_totals_reconcile` is what makes that loud.
"""

import json
import re
import unittest
from pathlib import Path

import frappe

from upande_crm.api.territory import (
    ZERO,
    crm_territory_detail,
    crm_territory_map,
)

# Wide enough to cover every record on the site, so counts are deterministic
# rather than dependent on when the suite runs.
ALL_TIME = {"date_from": "2000-01-01", "date_to": "2035-12-31"}

FRONTEND_LIB = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib"


def _js_object_keys(source: str, const: str) -> set:
    """Keys of a top-level `export const <const> = { ... }` object literal.

    The ISO table is JavaScript because the map consumes it in the browser, but
    it is data, and Python is where the site's Territory list can be checked
    against it. Parsing beats duplicating the table in both languages.
    """
    start = source.index(f"export const {const} = {{")
    body = source[start : source.index("\n};", start)]
    return set(re.findall(r"^\s{2}'((?:[^'\\]|\\.)*)':", body, re.M))


class TestTerritoryIsoTable(unittest.TestCase):
    """The name -> ISO join is the fragile part; these keep it honest."""

    @classmethod
    def setUpClass(cls):
        src = (FRONTEND_LIB / "territory_iso.js").read_text()
        cls.iso = _js_object_keys(src, "ISO_BY_TERRITORY")
        cls.micro = _js_object_keys(src, "MICRO_CENTROIDS")

    def test_every_leaf_territory_is_mapped(self):
        """A territory added later must fail here, not vanish off the map."""
        leaves = {
            t.name.replace("\\'", "'")
            for t in frappe.get_all(
                "Territory", filters={"is_group": 0}, fields=["name"]
            )
        }
        known = {n.replace("\\'", "'") for n in (self.iso | self.micro)}
        missing = sorted(leaves - known)
        self.assertEqual(
            missing,
            [],
            f"{len(missing)} territories map to neither a polygon nor a centroid: {missing}",
        )

    def test_iso_and_micro_do_not_overlap(self):
        """A territory is drawn as a polygon or a dot, never both."""
        self.assertEqual(sorted(self.iso & self.micro), [])

    def test_iso_codes_are_three_digit_numeric(self):
        src = (FRONTEND_LIB / "territory_iso.js").read_text()
        start = src.index("export const ISO_BY_TERRITORY = {")
        body = src[start : src.index("\n};", start)]
        codes = re.findall(r":\s*'([^']+)'", body)
        self.assertTrue(codes)
        bad = [c for c in codes if not re.fullmatch(r"\d{3}", c)]
        self.assertEqual(bad, [], f"non-numeric ISO ids: {bad}")


class TestTerritoryMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = crm_territory_map(**ALL_TIME)

    def test_payload_shape(self):
        for key in ("currency", "territories", "groups", "totals", "date_from", "date_to"):
            self.assertIn(key, self.data)
        for row in self.data["territories"] + self.data["groups"]:
            self.assertIn("territory", row)
            for metric in ZERO:
                self.assertIn(metric, row, f"{row['territory']} missing {metric}")

    def test_totals_reconcile(self):
        """mapped + regional == all, per metric.

        If this drifts, the map is hiding rows.
        """
        t = self.data["totals"]
        for metric in ZERO:
            self.assertAlmostEqual(
                t["mapped"][metric] + t["regional"][metric],
                t["all"][metric],
                places=4,
                msg=f"{metric} does not reconcile",
            )

    def test_totals_match_direct_counts(self):
        """Rollups agree with a plain count over the same rows."""
        for metric, doctype in (
            ("leads", "Lead"),
            ("prospects", "Prospect"),
            ("customers", "Customer"),
            ("opps", "Opportunity"),
        ):
            if not frappe.db.exists("DocType", doctype):
                continue
            direct = frappe.db.sql(
                f"select count(*) from `tab{doctype}` "
                "where ifnull(territory, '') <> '' and docstatus < 2"
            )[0][0]
            self.assertEqual(
                self.data["totals"]["all"][metric],
                direct,
                f"{metric} rollup disagrees with a direct count",
            )

    def test_groups_are_group_territories_only(self):
        """Nothing paintable ends up in the ledger, and no group escapes into it."""
        for row in self.data["groups"]:
            self.assertTrue(
                frappe.db.get_value("Territory", row["territory"], "is_group"),
                f"{row['territory']} is a leaf but was put in the regional ledger",
            )
        for row in self.data["territories"]:
            self.assertFalse(
                frappe.db.get_value("Territory", row["territory"], "is_group"),
                f"{row['territory']} is a group but was placed on the map",
            )

    def test_group_tagged_data_is_not_silently_dropped(self):
        """The reason the ledger exists: real volume lives on group territories."""
        tagged = frappe.db.sql(
            """select count(*) from `tabCustomer` c
               join `tabTerritory` t on t.name = c.territory
               where t.is_group = 1"""
        )[0][0]
        if not tagged:
            self.skipTest("no group-tagged customers on this site")
        self.assertEqual(self.data["totals"]["regional"]["customers"], tagged)

    def test_date_range_narrows(self):
        narrow = crm_territory_map(date_from="2000-01-01", date_to="2000-01-02")
        self.assertLessEqual(
            narrow["totals"]["all"]["leads"], self.data["totals"]["all"]["leads"]
        )

    def test_currency_is_company_denominated(self):
        self.assertTrue(self.data["currency"])
        self.assertNotEqual(self.data["currency"], "$")


class TestClaimsAndConsignees(unittest.TestCase):
    """The two joins that do not go through a `territory` column.

    Claims reach a country only by matching free text to a Customer name, and
    consignees only by translating an ISO country string. Both lose rows, and
    both must say how many.
    """

    @classmethod
    def setUpClass(cls):
        cls.data = crm_territory_map(**ALL_TIME)

    def test_orphan_counts_are_reported(self):
        self.assertIn("orphaned", self.data)
        for key in ("claims", "consignees"):
            self.assertIn(key, self.data["orphaned"])
            self.assertGreaterEqual(self.data["orphaned"][key], 0)

    def test_claims_reconcile_with_the_source(self):
        """mapped + regional + orphaned == every claim in range."""
        if not frappe.db.exists("DocType", "Customer Feedback"):
            self.skipTest("no Customer Feedback on this site")
        total = frappe.db.sql(
            "select count(*) from `tabCustomer Feedback` where feedback_date between %s and %s",
            (ALL_TIME["date_from"], ALL_TIME["date_to"]),
        )[0][0]
        accounted = self.data["totals"]["all"]["claims"] + self.data["orphaned"]["claims"]
        self.assertEqual(
            accounted, total, "claims are being dropped rather than counted as orphaned"
        )

    def test_consignees_reconcile_with_the_source(self):
        if not frappe.db.exists("DocType", "Consignee"):
            self.skipTest("no Consignee on this site")
        total = frappe.db.sql(
            "select count(*) from `tabConsignee` where ifnull(country,'') <> ''"
        )[0][0]
        accounted = self.data["totals"]["all"]["consignees"] + self.data["orphaned"]["consignees"]
        self.assertEqual(accounted, total, "consignees are being dropped silently")

    def test_claim_cost_is_never_negative(self):
        for r in self.data["territories"]:
            self.assertGreaterEqual(r["claim_cost"], 0)
            self.assertGreaterEqual(r["claim_stems"], 0)


class TestTerritoryDetail(unittest.TestCase):
    def test_detail_shape(self):
        target = next(
            (
                r["territory"]
                for r in crm_territory_map(**ALL_TIME)["territories"]
                if r["revenue"]
            ),
            None,
        )
        if not target:
            self.skipTest("no territory with revenue on this site")
        d = crm_territory_detail(target, **ALL_TIME)
        self.assertEqual(d["territory"], target)
        for key in ("top_accounts", "stages", "recent", "trend"):
            self.assertIsInstance(d[key], list)

    def test_detail_carries_the_new_panels(self):
        d = crm_territory_detail("Netherlands", **ALL_TIME)
        for key in ("flowers", "claim_types", "claim_reasons", "staff", "consignees"):
            self.assertIn(key, d)
        self.assertIn("rows", d["flowers"])
        self.assertIn("unattributed", d["flowers"])

    def test_flowers_exclude_uncoded_lines_and_say_so(self):
        """The un-coded lines outweigh every named variety here."""
        d = crm_territory_detail("Netherlands", **ALL_TIME)
        for row in d["flowers"]["rows"]:
            self.assertTrue(row["label"], "a variety row with no item code leaked in")
        self.assertGreaterEqual(d["flowers"]["unattributed"], 0)

    def test_claim_reason_coverage_is_stated(self):
        """Coverage matters more than the rows: the field is ~0% filled."""
        d = crm_territory_detail("Netherlands", **ALL_TIME)
        r = d["claim_reasons"]
        self.assertLessEqual(r["covered"], r["total"])

    def test_fulfilment_only_charts_joined_stages(self):
        """Harvest joins to nothing and Dispatch Form is 1% linked.

        Both must be named as gaps rather than drawn as empty funnel stages —
        a stage reading zero would look like no work happened, not like no data.
        """
        d = crm_territory_detail("Netherlands", **ALL_TIME)
        f = d["fulfilment"]
        labels = [s["label"] for s in f["stages"]]
        self.assertNotIn("Harvested", labels)
        self.assertNotIn("Dispatched", labels)
        if frappe.db.exists("DocType", "Harvest"):
            self.assertTrue(
                any("Harvest" in g for g in f["gaps"]),
                "the harvest gap must be stated, not omitted silently",
            )

    def test_fulfilment_stages_do_not_exceed_orders(self):
        """You cannot pick more orders than exist."""
        d = crm_territory_detail("Netherlands", **ALL_TIME)
        stages = {s["label"]: s["orders"] for s in d["fulfilment"]["stages"]}
        if "Ordered" in stages:
            for label, n in stages.items():
                self.assertLessEqual(n, stages["Ordered"], f"{label} exceeds Ordered")

    def test_blank_territory_returns_empty(self):
        self.assertEqual(crm_territory_detail("", **ALL_TIME), {})

    def test_unknown_territory_does_not_raise(self):
        d = crm_territory_detail("Nowhere At All", **ALL_TIME)
        self.assertEqual(d["top_accounts"], [])
        self.assertEqual(d["recent"], [])


class TestDegradation(unittest.TestCase):
    def test_missing_doctype_degrades(self):
        """A site without Sales Invoice renders an empty metric, not an error."""
        import upande_crm.api.territory as mod

        real = mod._has
        mod._has = lambda dt: False if dt in ("Sales Invoice", "Sales Order") else real(dt)
        try:
            data = crm_territory_map(**ALL_TIME)
            self.assertEqual(data["totals"]["all"]["revenue"], 0)
            # Counts from surviving doctypes still come through.
            self.assertGreaterEqual(data["totals"]["all"]["leads"], 0)
        finally:
            mod._has = real
