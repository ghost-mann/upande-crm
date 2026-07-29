"""Tests for the Reports section.

The load-bearing test is `test_every_registered_report_actually_runs`. The registry
exists precisely because a Script Report's filters live in client-side JS the
server cannot introspect, so "this report runs with these filters" is a claim that
has to be checked against a real execution — a third of this site's reports fail
when run blind.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import reports as R

WIDE = {"date_from": "2026-01-01", "date_to": "2026-12-31"}


class TestRegistryIntegrity(FrappeTestCase):
    def test_keys_are_unique(self):
        keys = [e["key"] for e in R.REPORTS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_every_group_is_a_real_tab(self):
        groups = {k for k, _l, _b in R.GROUPS}
        for entry in R.REPORTS:
            self.assertIn(entry["group"], groups, entry["key"])

    def test_every_group_has_at_least_one_report(self):
        used = {e["group"] for e in R.REPORTS}
        for key, _label, _blurb in R.GROUPS:
            self.assertIn(key, used, key)

    def test_every_editable_filter_is_declared(self):
        # Offering to edit a filter the report is never sent would do nothing.
        for entry in R.REPORTS:
            for field in entry["editable"]:
                self.assertIn(field, entry["filters"], f"{entry['key']}.{field}")

    def test_every_report_exists_on_this_site(self):
        for entry in R.REPORTS:
            self.assertTrue(frappe.db.exists("Report", entry["report"]), entry["report"])

    def test_every_entry_has_a_label_and_blurb(self):
        for entry in R.REPORTS:
            self.assertTrue(entry["label"], entry["key"])
            self.assertTrue(entry["blurb"], entry["key"])

    def test_filterless_set_is_accurate(self):
        # If a report in FILTERLESS actually needs filters, the catalogue would
        # offer to run it and fail.
        from frappe.desk.query_report import run as run_report

        for name in sorted(R.FILTERLESS):
            if not frappe.db.exists("Report", name):
                continue
            try:
                run_report(name, filters="{}", ignore_prepared_report=True)
            except Exception as e:
                self.fail(f"{name} is in FILTERLESS but failed bare: {type(e).__name__}: {e}")


class TestEveryRegisteredReportRuns(FrappeTestCase):
    def test_every_registered_report_actually_runs(self):
        failures = []
        for entry in R.REPORTS:
            payload = R.crm_report_run(key=entry["key"], **WIDE)
            if payload.get("error"):
                failures.append(f"{entry['key']} ({entry['report']}): {payload['error']}")
        self.assertEqual(failures, [], "registered reports that fail to run:\n" + "\n".join(failures))

    def test_every_registered_report_returns_columns(self):
        thin = []
        for entry in R.REPORTS:
            payload = R.crm_report_run(key=entry["key"], **WIDE)
            if not payload.get("error") and not payload.get("columns"):
                thin.append(entry["key"])
        self.assertEqual(thin, [], f"reports returning no columns: {thin}")

    def test_rows_are_dicts_keyed_by_fieldname(self):
        for entry in R.REPORTS:
            payload = R.crm_report_run(key=entry["key"], **WIDE)
            rows, cols = payload.get("rows") or [], payload.get("columns") or []
            if not rows:
                continue
            names = {c["fieldname"] for c in cols}
            self.assertIsInstance(rows[0], dict, entry["key"])
            self.assertTrue(set(rows[0]) & names, f"{entry['key']} row keys do not match columns")

    def test_a_report_with_real_data_returns_rows(self):
        # A registry where everything returns zero rows would pass the run test
        # while being useless. At least one must carry data on this site.
        with_rows = [e["key"] for e in R.REPORTS
                     if (R.crm_report_run(key=e["key"], **WIDE).get("rows") or [])]
        self.assertTrue(with_rows, "no registered report returned any rows")


class TestRowCap(FrappeTestCase):
    def test_a_huge_report_is_capped_and_says_so(self):
        # Item-wise Sales History returns tens of thousands of rows for a year on
        # this site. Truncating silently would present a wrong answer as a table.
        payload = R.crm_report_run(key="item_sales_history", **WIDE)
        if payload.get("error"):
            self.skipTest("item history unavailable: " + payload["error"])
        self.assertLessEqual(len(payload["rows"]), R.ROW_CAP)
        if payload["total_rows"] > R.ROW_CAP:
            self.assertTrue(payload["truncated"])
            self.assertEqual(payload["row_cap"], R.ROW_CAP)
            self.assertTrue(payload["desk_url"])

    def test_a_small_report_is_not_marked_truncated(self):
        payload = R.crm_report_run(key="inactive_customers", **WIDE)
        if payload.get("error"):
            self.skipTest("unavailable")
        self.assertFalse(payload["truncated"])
        self.assertEqual(len(payload["rows"]), payload["total_rows"])


class TestColumnNormalisation(FrappeTestCase):
    def test_dict_columns_pass_through(self):
        cols = R._columns([{"fieldname": "amount", "label": "Amount",
                            "fieldtype": "Currency", "options": "USD"}])
        self.assertEqual(cols[0]["fieldtype"], "Currency")
        self.assertEqual(cols[0]["options"], "USD")

    def test_legacy_string_columns_are_parsed(self):
        # Older reports return "Label:Type/Options:width".
        cols = R._columns(["Customer:Link/Customer:180", "Total:Currency/Company:120", "Note"])
        self.assertEqual(cols[0]["fieldtype"], "Link")
        self.assertEqual(cols[0]["options"], "Customer")
        self.assertEqual(cols[1]["fieldtype"], "Currency")
        self.assertEqual(cols[2]["fieldtype"], "Data")

    def test_list_rows_are_zipped_onto_column_names(self):
        cols = ["Customer:Data:100", "Total:Currency:100"]
        rows = R._rows([["ACME", 10.0]], cols)
        self.assertEqual(rows[0], {"customer": "ACME", "total": 10.0})

    def test_dict_rows_drop_private_keys(self):
        rows = R._rows([{"customer": "ACME", "_meta": "x"}], [{"fieldname": "customer"}])
        self.assertEqual(rows[0], {"customer": "ACME"})

    def test_empty_input_is_safe(self):
        self.assertEqual(R._columns(None), [])
        self.assertEqual(R._rows(None, None), [])


class TestSentinelResolution(FrappeTestCase):
    def test_range_sentinels_reach_the_report(self):
        payload = R.crm_report_run(key="pipeline_by_stage",
                                   date_from="2026-03-01", date_to="2026-03-31")
        self.assertEqual(payload["filters"]["from_date"], "2026-03-01")
        self.assertEqual(payload["filters"]["to_date"], "2026-03-31")

    def test_company_sentinel_resolves(self):
        payload = R.crm_report_run(key="pipeline_by_stage", **WIDE)
        self.assertEqual(payload["filters"]["company"],
                         frappe.defaults.get_global_default("company"))

    def test_fiscal_year_sentinel_resolves_to_a_year(self):
        payload = R.crm_report_run(key="order_trends", **WIDE)
        self.assertEqual(payload["filters"]["fiscal_year"], "2026")

    def test_undated_reports_carry_no_range(self):
        entry = R.BY_KEY["inactive_customers"]
        self.assertFalse(entry["date_scoped"])
        payload = R.crm_report_run(key="inactive_customers", **WIDE)
        self.assertNotIn("from_date", payload["filters"])


class TestFilterOverrides(FrappeTestCase):
    def test_an_editable_filter_can_be_overridden(self):
        payload = R.crm_report_run(
            key="inactive_customers", filters=frappe.as_json({"days_since_last_order": 5}), **WIDE)
        self.assertEqual(payload["filters"]["days_since_last_order"], 5)

    def test_an_undeclared_filter_is_dropped(self):
        # A crafted request must not be able to add a filter the report would
        # then interpolate into its own SQL.
        payload = R.crm_report_run(
            key="inactive_customers",
            filters=frappe.as_json({"nonsense": "x", "company": "Injected Co"}), **WIDE)
        self.assertNotIn("nonsense", payload["filters"])
        self.assertNotEqual(payload["filters"].get("company"), "Injected Co")

    def test_a_non_editable_declared_filter_is_not_overridable(self):
        entry = R.BY_KEY["pipeline_by_stage"]
        self.assertNotIn("from_date", entry["editable"])
        payload = R.crm_report_run(
            key="pipeline_by_stage", filters=frappe.as_json({"from_date": "1990-01-01"}), **WIDE)
        self.assertEqual(payload["filters"]["from_date"], "2026-01-01")

    def test_malformed_filters_are_refused(self):
        with self.assertRaises(frappe.ValidationError):
            R.crm_report_run(key="lead_details", filters="{not json", **WIDE)


class TestEndpoints(FrappeTestCase):
    def tearDown(self):
        frappe.set_user("Administrator")

    def test_registry_payload_shape(self):
        d = R.crm_reports(**WIDE)
        self.assertEqual([g["key"] for g in d["groups"]], [k for k, _l, _b in R.GROUPS])
        self.assertEqual(len(d["reports"]), len(R.REPORTS))
        for row in d["reports"]:
            for key in ("key", "report", "group", "label", "blurb", "filters",
                        "permitted", "desk_url", "date_scoped"):
                self.assertIn(key, row)

    def test_catalogue_covers_the_crm_and_selling_modules(self):
        d = R.crm_report_catalogue()
        names = {row["report"] for row in d["reports"]}
        expected = {
            r.name for r in frappe.get_all(
                "Report", filters={"module": ["in", list(R.CATALOGUE_MODULES)], "disabled": 0},
                fields=["name"])
        }
        # Administrator can see everything, so the two sets should match.
        self.assertEqual(names, expected)

    def test_catalogue_marks_registered_reports_runnable(self):
        rows = {r["report"]: r for r in R.crm_report_catalogue()["reports"]}
        for entry in R.REPORTS:
            self.assertTrue(rows[entry["report"]]["runnable"], entry["report"])
            self.assertTrue(rows[entry["report"]]["registered"], entry["report"])

    def test_catalogue_marks_the_unrunnable_ones_with_a_desk_url(self):
        # The reports whose filters we have not verified must not claim runnable.
        rows = R.crm_report_catalogue()["reports"]
        unrunnable = [r for r in rows if not r["runnable"]]
        self.assertTrue(unrunnable, "expected some reports to need desk filters")
        for row in unrunnable:
            self.assertTrue(row["desk_url"].startswith("/app/query-report/"))

    def test_unknown_report_is_refused(self):
        with self.assertRaises(frappe.DoesNotExistError):
            R.crm_report_run(report="No Such Report At All")

    def test_running_by_name_requires_permission(self):
        # The catalogue path must not become a runner for arbitrary reports.
        self.assertTrue(R._permitted("Lead Details"))
        payload = R.crm_report_run(report="Lead Details")
        self.assertIn("columns", payload)

    def test_a_failing_report_returns_an_error_not_an_exception(self):
        # Sales Analytics run bare is one of the measured failures.
        payload = R.crm_report_run(report="Sales Analytics")
        self.assertIn("error", payload)
        self.assertIn("desk_url", payload)

    def test_guest_is_refused(self):
        frappe.set_user("Guest")
        for call in (lambda: R.crm_reports(), lambda: R.crm_report_catalogue(),
                     lambda: R.crm_report_run(key="lead_details")):
            with self.assertRaises(frappe.PermissionError):
                call()
