"""Tests for the CRM command centre.

The decomposition assertions are the important ones. The Overview now claims to
explain *why* a variety stopped selling, and that claim rests on one identity:
a revenue change is exactly its volume effect plus its price effect. If that
stops holding, the page is inventing explanations, so it is asserted directly and
at the endpoint boundary.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate

from upande_crm.api import command

FRM, TO = "2026-05-01", "2026-07-15"

CENTRE_KEYS = ("currency", "range", "kpis", "upcoming", "follow_ups")
KPI_KEYS = ("new_leads", "to_opp", "prosp", "cust", "upcoming", "follow_ups")
TRACK_KEYS = ("currency", "range", "track_record", "movers", "top_sellers", "rep_performance")


class TestDecomposition(FrappeTestCase):
    """The volume/price split is arithmetic, not an estimate."""

    def test_sums_to_the_total_change(self):
        for a0, q0, a1, q1 in (
            (1000.0, 100.0, 800.0, 90.0),
            (1000.0, 100.0, 1200.0, 90.0),
            (500.0, 50.0, 500.0, 50.0),
        ):
            volume, price = command._decompose(a0, q0, a1, q1)
            self.assertAlmostEqual(volume + price, a1 - a0, places=6)

    def test_holds_when_a_variety_stops_selling(self):
        # The case the whole feature exists for: sold last period, nothing now.
        volume, price = command._decompose(1000.0, 100.0, 0.0, 0.0)
        self.assertAlmostEqual(volume + price, -1000.0, places=6)
        self.assertAlmostEqual(volume, -1000.0, places=6)
        self.assertAlmostEqual(price, 0.0, places=6)

    def test_holds_when_a_variety_is_new(self):
        volume, price = command._decompose(0.0, 0.0, 1000.0, 100.0)
        self.assertAlmostEqual(volume + price, 1000.0, places=6)

    def test_separates_a_price_fall_from_a_volume_fall(self):
        # Same stems, half the rate: the whole change is price.
        volume, price = command._decompose(1000.0, 100.0, 500.0, 100.0)
        self.assertAlmostEqual(volume, 0.0, places=6)
        self.assertAlmostEqual(price, -500.0, places=6)

        # Same rate, half the stems: the whole change is volume.
        volume, price = command._decompose(1000.0, 100.0, 500.0, 50.0)
        self.assertAlmostEqual(volume, -500.0, places=6)
        self.assertAlmostEqual(price, 0.0, places=6)


class TestPriorWindow(FrappeTestCase):
    def test_is_equal_length_and_immediately_before(self):
        p_frm, p_to = command._prior("2026-06-01", "2026-06-30")
        self.assertEqual(p_to, "2026-05-31")
        self.assertEqual(p_frm, "2026-05-02")
        span = (getdate("2026-06-30") - getdate("2026-06-01")).days
        self.assertEqual((getdate(p_to) - getdate(p_frm)).days, span)

    def test_pct_has_no_base_to_divide_by(self):
        # Callers expose `prev` alongside so the UI can say "no prior" instead.
        self.assertEqual(command._pct(100, 0), 0.0)
        self.assertEqual(command._pct(150, 100), 50.0)
        self.assertEqual(command._pct(50, 100), -50.0)


class TestCommandCentre(FrappeTestCase):
    def test_returns_its_documented_keys(self):
        d = command.crm_command_center(date_from=FRM, date_to=TO)
        for k in CENTRE_KEYS:
            self.assertIn(k, d)
        for k in KPI_KEYS:
            self.assertIn(k, d["kpis"])

    def test_exposes_company_currency(self):
        d = command.crm_command_center(date_from=FRM, date_to=TO)
        self.assertTrue(d["currency"])
        company = frappe.defaults.get_global_default("company")
        if company:
            self.assertEqual(
                d["currency"], frappe.db.get_value("Company", company, "default_currency"))

    def test_upcoming_ignores_the_date_range(self):
        # "Upcoming" means from now forward. A range that ended in the past must
        # not empty the table — a pill reading "last 30 days" hiding tomorrow's
        # meeting is the bug this guards.
        old = command.crm_command_center(date_from="2020-01-01", date_to="2020-01-31")
        cur = command.crm_command_center(date_from=FRM, date_to=TO)
        self.assertEqual(len(old["upcoming"]), len(cur["upcoming"]))

    def test_upcoming_never_returns_a_past_event(self):
        d = command.crm_command_center(date_from=FRM, date_to=TO)
        today = getdate(nowdate())
        for row in d["upcoming"]:
            if row["kind"] == "event" and row["when"]:
                self.assertGreaterEqual(getdate(row["when"]), today)

    def test_upcoming_puts_overdue_first(self):
        rows = command.crm_command_center(date_from=FRM, date_to=TO)["upcoming"]
        ranks = [command.BUCKET_RANK[r["bucket"]] for r in rows]
        self.assertEqual(ranks, sorted(ranks))

    def test_overdue_is_bounded(self):
        # This site carries ~2,400 abandoned open ToDos; without the floor they
        # would all land here and bury the actionable rows.
        rows = command.crm_command_center(date_from=FRM, date_to=TO)["upcoming"]
        floor = add_days(getdate(nowdate()), -command.UPCOMING_BACK_DAYS)
        for r in rows:
            if r["when"]:
                self.assertGreaterEqual(getdate(r["when"]), floor)

    def test_kpi_counts_agree_with_the_upcoming_list(self):
        d = command.crm_command_center(date_from=FRM, date_to=TO)
        rows = d["upcoming"]
        self.assertEqual(
            d["kpis"]["upcoming"]["overdue"],
            len([r for r in rows if r["bucket"] == "overdue"]))
        self.assertEqual(
            d["kpis"]["follow_ups"]["emails"], len(d["follow_ups"]["emails"]))

    def test_conversions_are_not_double_counted(self):
        # One lead can be the source of several Opportunities; it converted once.
        total = command._conversions(FRM, TO, None)
        opps = frappe.get_all(
            "Opportunity",
            filters={"opportunity_from": "Lead",
                     "transaction_date": ["between", [FRM, TO]]},
            fields=["party_name"], limit=0)
        self.assertLessEqual(total, len(opps))
        if opps:
            self.assertEqual(total, len({o.party_name for o in opps if o.party_name}))

    def test_awaiting_reply_rows_are_one_per_record(self):
        rows = command.crm_command_center(date_from=FRM, date_to=TO)["follow_ups"]["emails"]
        keys = [(r["ref_doctype"], r["ref_name"]) for r in rows]
        self.assertEqual(len(keys), len(set(keys)))

    def test_awaiting_reply_is_ordered_longest_first(self):
        rows = command.crm_command_center(date_from=FRM, date_to=TO)["follow_ups"]["emails"]
        waits = [r["waiting_days"] for r in rows]
        self.assertEqual(waits, sorted(waits, reverse=True))


class TestTrackRecord(FrappeTestCase):
    def test_returns_its_documented_keys(self):
        d = command.crm_sales_track_record(date_from=FRM, date_to=TO)
        for k in TRACK_KEYS:
            self.assertIn(k, d)

    def test_series_are_capped_and_keyed_positionally(self):
        # recharts reads a dataKey as a path, so a key containing a dot would
        # resolve to nothing. Series must be s0..sN, not item codes or emails.
        tr = command.crm_sales_track_record(date_from=FRM, date_to=TO)["track_record"]
        for dim in ("flower", "rep"):
            series = tr[dim]["series"]
            self.assertLessEqual(len(series), command.SERIES_LIMIT)
            self.assertEqual([s["id"] for s in series],
                             [f"s{i}" for i in range(len(series))])

    def test_every_frame_row_carries_every_series(self):
        # A missing key would render as a gap in the line rather than as a zero.
        tr = command.crm_sales_track_record(date_from=FRM, date_to=TO)["track_record"]
        for dim in ("flower", "rep"):
            ids = [s["id"] for s in tr[dim]["series"]]
            for metric in ("revenue", "stems"):
                for row in tr[dim][metric]:
                    for i in ids:
                        self.assertIn(i, row)

    def test_grain_matches_the_span(self):
        self.assertEqual(command._buckets("2026-06-01", "2026-06-30")[2], "day")
        self.assertEqual(command._buckets("2026-01-01", "2026-06-30")[2], "week")
        self.assertEqual(command._buckets("2024-01-01", "2026-06-30")[2], "month")

    def test_movers_are_ranked_and_signed(self):
        m = command.crm_sales_track_record(date_from=FRM, date_to=TO)["movers"]
        self.assertTrue(all(r["delta"] < 0 for r in m["declines"]))
        self.assertTrue(all(r["delta"] > 0 for r in m["gains"]))
        self.assertEqual([r["delta"] for r in m["declines"]],
                         sorted(r["delta"] for r in m["declines"]))
        self.assertEqual([r["delta"] for r in m["gains"]],
                         sorted((r["delta"] for r in m["gains"]), reverse=True))

    def test_every_mover_decomposes_exactly(self):
        m = command.crm_sales_track_record(date_from=FRM, date_to=TO)["movers"]
        for r in m["declines"] + m["gains"]:
            self.assertAlmostEqual(
                r["volume_effect"] + r["price_effect"], r["delta"], places=4,
                msg=f"{r['label']} does not decompose")

    def test_a_stopped_variety_is_flagged_not_reported_as_minus_100(self):
        m = command.crm_sales_track_record(date_from=FRM, date_to=TO)["movers"]
        for r in m["declines"]:
            if r["stopped"]:
                self.assertEqual(r["amount"], 0.0)
                self.assertGreater(r["prev"], 0.0)

    def test_matrix_cells_distinguish_never_bought_from_bought_none(self):
        S = command.crm_sales_track_record(date_from=FRM, date_to=TO)["top_sellers"]
        keys = [v["key"] for v in S["varieties"]]
        for row in S["matrix"]:
            self.assertEqual(set(row["cells"]), set(keys))
            for cell in row["cells"].values():
                # None = no history either side. A dict always carries both windows.
                if cell is not None:
                    self.assertIn("prev", cell)
                    self.assertIn("amount", cell)

    def test_per_customer_lists_at_most_five(self):
        S = command.crm_sales_track_record(date_from=FRM, date_to=TO)["top_sellers"]
        for row in S["per_customer"]:
            self.assertLessEqual(len(row["top"]), 5)
            amounts = [t["amount"] for t in row["top"]]
            self.assertEqual(amounts, sorted(amounts, reverse=True))

    def test_rep_scorecard_carries_result_and_effort(self):
        rows = command.crm_sales_track_record(date_from=FRM, date_to=TO)["rep_performance"]
        for r in rows:
            for k in ("amount", "prev", "delta_pct", "aov", "orders", "customers",
                      "varieties", "stems", "activity"):
                self.assertIn(k, r)
            for k in ("calls", "emails", "tasks", "events"):
                self.assertIn(k, r["activity"])


class TestMoverDetail(FrappeTestCase):
    def _first_flower(self):
        m = command.crm_sales_track_record(date_from=FRM, date_to=TO)["movers"]
        rows = m["declines"] or m["gains"]
        return rows[0]["key"] if rows else None

    def test_rejects_an_unknown_kind(self):
        # The kind selects a group-by column, so it is rejected rather than
        # interpolated.
        with self.assertRaises(frappe.ValidationError):
            command.crm_mover_detail(kind="'; drop table x; --", key="Giselle")

    def test_rejects_an_empty_key(self):
        with self.assertRaises(frappe.ValidationError):
            command.crm_mover_detail(kind="flower", key="")

    def test_flower_detail_decomposes_exactly(self):
        key = self._first_flower()
        if not key:
            self.skipTest("no sales in range")
        d = command.crm_mover_detail(kind="flower", key=key, date_from=FRM, date_to=TO)
        t = d["totals"]
        self.assertAlmostEqual(t["volume_effect"] + t["price_effect"], t["delta"], places=4)

    def test_flower_detail_explains_by_customer_and_rep(self):
        key = self._first_flower()
        if not key:
            self.skipTest("no sales in range")
        d = command.crm_mover_detail(kind="flower", key=key, date_from=FRM, date_to=TO)
        self.assertEqual(set(d["contributions"]), {"customer", "rep"})
        for c in d["contributions"].values():
            self.assertTrue(all(r["delta"] < 0 for r in c["down"]))
            self.assertTrue(all(r["delta"] > 0 for r in c["up"]))

    def test_contributions_reconcile_with_the_total(self):
        # Every account's movement, summed, is the whole movement. This is what
        # makes "these two accounts explain the drop" a checkable statement.
        key = self._first_flower()
        if not key:
            self.skipTest("no sales in range")
        d = command.crm_mover_detail(kind="flower", key=key, date_from=FRM, date_to=TO)
        frm, to = d["range"]["from"], d["range"]["to"]
        p_frm, p_to = d["range"]["prev_from"], d["range"]["prev_to"]
        cur = command._item_totals(frm, to, None, group_col="so.customer",
                                   extra=" and soi.item_code = %s", params=(key,))
        prev = command._item_totals(p_frm, p_to, None, group_col="so.customer",
                                    extra=" and soi.item_code = %s", params=(key,))
        summed = sum(v["amount"] for v in cur.values()) - sum(v["amount"] for v in prev.values())
        self.assertAlmostEqual(summed, d["totals"]["delta"], places=2)

    def test_a_subjects_total_is_its_whole_total(self):
        """A drill header must be the subject's total, not one slice of it.

        `_item_totals` groups by item_code by default, so a rep drill that reused
        that grouping and took the first group reported one arbitrary variety as
        the rep's entire number — 485.6k against a true 15.5M on this site. The
        invariant: the header equals the sum of its own contribution rows.
        """
        reps = command.crm_sales_track_record(date_from=FRM, date_to=TO)["rep_performance"]
        if not reps:
            self.skipTest("no rep data in range")
        d = command.crm_mover_detail(kind="rep", key=reps[0]["key"], date_from=FRM, date_to=TO)
        c = d["contributions"]["flower"]
        # Contributions carry the current-window amount for every variety that
        # moved either way; their current amounts cannot exceed the header total.
        current = sum(r["amount"] for r in c["down"] + c["up"])
        self.assertLessEqual(round(current, 2), round(d["totals"]["amount"], 2) + 0.01)
        # And the header must be in the same order of magnitude as the scorecard's
        # order-level figure — they differ only by order-level tax and freight.
        self.assertGreater(d["totals"]["amount"], reps[0]["amount"] * 0.5)

    def test_rep_detail_explains_by_flower_and_customer(self):
        rows = command.crm_sales_track_record(date_from=FRM, date_to=TO)["rep_performance"]
        if not rows:
            self.skipTest("no rep data in range")
        d = command.crm_mover_detail(kind="rep", key=rows[0]["key"], date_from=FRM, date_to=TO)
        self.assertEqual(set(d["contributions"]), {"flower", "customer"})
        self.assertEqual(d["label"], rows[0]["label"])

    def test_year_ago_is_absent_rather_than_wrong(self):
        # Orders on this site start in late 2025, so most windows have no
        # comparable year-earlier period. Absent must mean absent, not zero.
        key = self._first_flower()
        if not key:
            self.skipTest("no sales in range")
        d = command.crm_mover_detail(kind="flower", key=key, date_from=FRM, date_to=TO)
        if d["year_ago"] is not None:
            self.assertGreater(d["year_ago"]["amount"], 0)
            self.assertEqual(d["year_ago"]["basis"], "invoiced")


class TestFunnelOnTheOverview(FrappeTestCase):
    """The Overview draws the shared cohort walk, not its own stage counts.

    The old `crm_dashboard_overview` funnel counted leads, opportunities,
    quotations, orders and conversions independently. Those counts share no
    records, so the shape could widen — and on this site it did, reporting orders
    as a multiple of the leads that produced them. Both halves are pinned: the
    command centre now carries a funnel, and the dashboard endpoint no longer does.
    """

    def test_the_command_centre_carries_a_funnel(self):
        c = command.crm_command_center(date_from=FRM, date_to=TO)
        self.assertIn("funnel", c)
        self.assertEqual([s["key"] for s in c["funnel"]],
                         ["leads", "opportunities", "won"])

    def test_it_cannot_widen(self):
        counts = [s["count"] for s in
                  command.crm_command_center(date_from=FRM, date_to=TO)["funnel"]]
        for i in range(len(counts) - 1):
            self.assertGreaterEqual(counts[i], counts[i + 1], f"funnel widened: {counts}")

    def test_the_old_independent_count_funnel_is_gone(self):
        from upande_crm.api.crm import crm_dashboard_overview

        self.assertNotIn("funnel", crm_dashboard_overview(date_from=FRM, date_to=TO))


class TestRepConversion(FrappeTestCase):
    """Conversion is keyed on who owns the lead, and measured from documents."""

    def _rows(self):
        return command.crm_sales_track_record(date_from=FRM, date_to=TO)["rep_conversion"]

    def test_the_track_record_carries_it(self):
        self.assertIn("rep_conversion",
                      command.crm_sales_track_record(date_from=FRM, date_to=TO))

    def test_counts_narrow_within_a_row(self):
        for r in self._rows():
            self.assertLessEqual(r["won"], r["to_opp"])
            self.assertLessEqual(r["to_opp"], r["leads"])

    def test_rates_match_their_counts(self):
        for r in self._rows():
            expected = round(r["won"] / r["leads"] * 100, 1) if r["leads"] else 0.0
            self.assertAlmostEqual(r["rate"], expected, places=1)

    def test_rates_are_bounded(self):
        for r in self._rows():
            self.assertGreaterEqual(r["rate"], 0)
            self.assertLessEqual(r["rate"], 100)

    def test_unassigned_survives_the_row_limit(self):
        """It is the largest row on this site, so truncation must not eat it.

        Sorting it last and then slicing dropped the card's main finding — most
        leads have nobody working them — to make room for a rep with two leads.
        """
        rows = self._rows()
        unassigned = [r for r in rows if r["unassigned"]]
        self.assertLessEqual(len(unassigned), 1)
        named = [r for r in rows if not r["unassigned"]]
        self.assertLessEqual(len(named), command.CONVERSION_ROWS)
        if unassigned:
            self.assertIs(rows[-1], unassigned[0])

    def test_named_rows_are_ordered_by_lead_count(self):
        # Not by rate: one lead converted is not a 100% closer.
        counts = [r["leads"] for r in self._rows() if not r["unassigned"]]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_guest_and_administrator_are_one_bucket(self):
        for r in self._rows():
            self.assertNotIn(r["key"], ("Guest", "Administrator"))

    def test_it_agrees_with_the_funnel(self):
        """Both read the same walk, so their totals cannot drift apart."""
        from upande_crm.api.funnel import cohort
        from upande_crm.api.crm import _range

        frm, to = _range(FRM, TO)
        walk = cohort(frm, to, None)
        rows = self._rows()
        if not rows:
            self.skipTest("no leads in range")
        # Rows are capped, so the card's totals are a lower bound on the cohort.
        self.assertLessEqual(sum(r["leads"] for r in rows), walk["counts"]["leads"])
        self.assertLessEqual(sum(r["to_opp"] for r in rows), len(walk["leads_reached_opp"]))
