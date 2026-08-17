"""Tests for the cohort funnel.

One property carries this whole module: **the funnel cannot widen.** That is the
bug the shared walk exists to make impossible — the Overview used to draw five
independently counted stages and reported 4 leads beside 1,429 orders. A funnel
built from a real cohort narrows by construction, so if these ever fail the walk
has stopped being a walk.

The rest asserts the two things that construction could still get wrong: counting
a lead twice when it reaches an opportunity by both routes, and losing the
prospect route entirely.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import funnel

WIDE = ("2000-01-01", "2099-12-31")
NARROW = ("2026-05-01", "2026-05-02")
STAGE_KEYS = ("key", "label", "count", "of_previous", "of_first", "dropped", "sample")


def _stages(frm=WIDE[0], to=WIDE[1], scope=None):
    return funnel.cohort(frm, to, scope)["stages"]


class TestShape(FrappeTestCase):
    def test_stages_never_widen(self):
        for frm, to in (WIDE, NARROW):
            stages = _stages(frm, to)
            counts = [s["count"] for s in stages]
            for i in range(len(counts) - 1):
                self.assertGreaterEqual(
                    counts[i], counts[i + 1],
                    f"funnel widened at stage {i + 1} over {frm}..{to}: {counts}",
                )

    def test_three_stages_in_order(self):
        self.assertEqual([s["key"] for s in _stages()],
                         ["leads", "opportunities", "won"])

    def test_every_stage_carries_its_keys(self):
        for s in _stages():
            for key in STAGE_KEYS:
                self.assertIn(key, s)

    def test_an_empty_cohort_is_still_a_funnel(self):
        # A window with no leads must produce three zeroed stages, not an empty
        # list — the card renders the shape either way.
        stages = _stages("1990-01-01", "1990-01-02")
        self.assertEqual(len(stages), 3)
        self.assertTrue(all(s["count"] == 0 for s in stages))
        self.assertTrue(all(s["of_first"] == 0 for s in stages))

    def test_drop_off_equals_the_gap_to_the_next_stage(self):
        stages = _stages()
        for i in range(len(stages) - 1):
            self.assertEqual(stages[i]["dropped"],
                             stages[i]["count"] - stages[i + 1]["count"])

    def test_percentages_are_bounded(self):
        for s in _stages():
            self.assertGreaterEqual(s["of_first"], 0)
            self.assertLessEqual(s["of_first"], 100)
            self.assertLessEqual(s["of_previous"], 100)


class TestRoutes(FrappeTestCase):
    def test_direct_and_via_prospect_partition_the_stage(self):
        walk = funnel.cohort(*WIDE)
        c = walk["counts"]
        self.assertEqual(c["direct"] + c["via_prospect"], c["opportunities"])

    def test_opportunities_are_deduplicated(self):
        names = [o["name"] for o in funnel.cohort(*WIDE)["opportunities"]]
        self.assertEqual(len(names), len(set(names)),
                         "an opportunity reachable by both routes was counted twice")

    def test_every_opportunity_carries_a_route(self):
        for o in funnel.cohort(*WIDE)["opportunities"]:
            self.assertIn(o.get("route"), ("direct", "via_prospect"))

    def test_prospect_is_not_a_stage(self):
        # It is a branch, not a step. 30 leads link to a prospect while 45 reach an
        # opportunity, so a Prospect stage would make the shape bulge back out.
        self.assertNotIn("prospects", [s["key"] for s in _stages()])


class TestAttribution(FrappeTestCase):
    """Lead-level attribution, which the conversion card is keyed on."""

    def test_reached_and_won_are_subsets_of_the_cohort(self):
        walk = funnel.cohort(*WIDE)
        leads = set(walk["leads"])
        self.assertTrue(set(walk["leads_reached_opp"]) <= leads)
        self.assertTrue(set(walk["leads_won"]) <= leads)

    def test_won_leads_are_a_subset_of_leads_that_reached_one(self):
        walk = funnel.cohort(*WIDE)
        self.assertTrue(set(walk["leads_won"]) <= set(walk["leads_reached_opp"]))

    def test_a_lead_is_attributed_once_however_many_opportunities_it_has(self):
        walk = funnel.cohort(*WIDE)
        reached = walk["leads_reached_opp"]
        self.assertEqual(len(reached), len(set(reached)))

    def test_leads_that_reached_one_never_exceed_the_opportunity_count(self):
        # Each lead here has at least one opportunity, so there cannot be more
        # such leads than opportunities.
        walk = funnel.cohort(*WIDE)
        self.assertLessEqual(len(walk["leads_reached_opp"]),
                             walk["counts"]["opportunities"])


class TestSamples(FrappeTestCase):
    def test_samples_are_bounded_and_drawn_from_the_stage(self):
        for s in _stages():
            self.assertLessEqual(len(s["sample"]), funnel.SAMPLE_LIMIT)
            self.assertLessEqual(len(s["sample"]), s["count"])
            for r in s["sample"]:
                self.assertTrue(r["name"])
                self.assertTrue(r["label"])


class TestDegradation(FrappeTestCase):
    def test_a_missing_doctype_yields_empty_rather_than_raising(self):
        # A read module: an install without Prospect Lead must lose the second
        # route, not the funnel.
        real = funnel._has
        try:
            funnel._has = lambda dt: dt != "Prospect Lead"
            walk = funnel.cohort(*WIDE)
            self.assertEqual(walk["counts"]["via_prospect"], 0)
            self.assertEqual(len(walk["stages"]), 3)
        finally:
            funnel._has = real
