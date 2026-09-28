"""Tests for the customer page API (`upande_crm.api.customer`).

Two customers are used: a fresh one with an awkward name and no history at all,
which every tab must answer with empty structures rather than errors, and the
real customer on this site with the most invoices, whose header figures are
checked against direct SQL.
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import customer as C
from upande_crm.api import settings as S

EMPTY_NAME = "_CP Test / O'Brien & Co"


def _clear():
    frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)


def _save(**patch_):
    doc = frappe.get_single(S.SETTINGS_DOCTYPE)
    doc.update(patch_)
    doc.save(ignore_permissions=True)
    _clear()


def _leaf(doctype):
    return frappe.db.get_value(doctype, {"is_group": 0}, "name")


class CustomerPageCase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        existing = frappe.db.get_value("Customer", {"customer_name": EMPTY_NAME}, "name")
        if existing:
            cls.empty = existing
        else:
            # ignore_mandatory: this site makes currency and price list
            # mandatory; the point of this customer is that it has neither.
            doc = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": EMPTY_NAME,
                "customer_type": "Company",
                "customer_group": _leaf("Customer Group"),
                "territory": _leaf("Territory"),
            })
            doc.flags.ignore_mandatory = True
            cls.empty = doc.insert(ignore_permissions=True).name
        row = frappe.db.sql(
            """select customer from `tabSales Invoice` where docstatus=1
               group by customer order by count(*) desc limit 1"""
        )
        cls.busy = row[0][0] if row else None

    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        # The class shares one transaction, so a switched-off module would leak
        # into the next test: put it back.
        frappe.set_user("Administrator")
        _clear()
        if not frappe.db.get_single_value(S.SETTINGS_DOCTYPE, "module_customer_page"):
            _save(module_customer_page=1)


class TestHeader(CustomerPageCase):
    def test_awkward_names_resolve(self):
        h = C.crm_customer_header(self.empty)
        self.assertEqual(h["customer"]["name"], self.empty)

    def test_empty_customer_has_zero_figures(self):
        f = C.crm_customer_header(self.empty)["figures"]
        self.assertEqual(f["order_count"], 0)
        self.assertEqual(f["lifetime_revenue"], 0)
        self.assertIsNone(f["last_order_date"])
        self.assertIsNone(f["days_since_last_order"])

    def test_header_matches_direct_sql(self):
        h = C.crm_customer_header(self.busy)
        total = frappe.db.sql(
            "select coalesce(sum(base_grand_total),0) from `tabSales Invoice` where customer=%s and docstatus=1",
            self.busy,
        )[0][0]
        self.assertAlmostEqual(h["figures"]["lifetime_revenue"], float(total), places=2)
        self.assertEqual(
            h["figures"]["order_count"],
            frappe.db.count("Sales Order", {"customer": self.busy, "docstatus": 1}),
        )

    def test_header_carries_configured_tabs(self):
        _save(custpage_tabs="orders\ntimeline", custpage_default_tab="timeline")
        h = C.crm_customer_header(self.empty)
        self.assertEqual(h["tabs"], ["orders", "timeline"])
        self.assertEqual(h["default_tab"], "timeline")

    def test_unknown_customer_raises(self):
        with self.assertRaises(frappe.DoesNotExistError):
            C.crm_customer_header("__no_such_customer__")


class TestTabs(CustomerPageCase):
    def test_empty_customer_returns_empty_structures(self):
        self.assertEqual(C.crm_customer_orders(self.empty)["rows"], [])
        self.assertEqual(C.crm_customer_orders(self.empty)["total"], 0)
        self.assertEqual(C.crm_customer_contracts(self.empty)["rows"], [])
        ov = C.crm_customer_overview(self.empty)
        self.assertEqual(ov["top_items"], [])
        self.assertEqual(len(ov["trend"]), 12)
        self.assertTrue(all(r["amount"] == 0 for r in ov["trend"]))

    def test_orders_page_and_total(self):
        r = C.crm_customer_orders(self.busy, kind="Sales Invoice", page_len=5)
        self.assertLessEqual(len(r["rows"]), 5)
        self.assertEqual(
            r["total"], frappe.db.count("Sales Invoice", {"customer": self.busy, "docstatus": ["<", 2]})
        )

    def test_orders_second_page_differs(self):
        a = C.crm_customer_orders(self.busy, kind="Sales Invoice", page_len=5)
        b = C.crm_customer_orders(self.busy, kind="Sales Invoice", start=5, page_len=5)
        if a["total"] > 5:
            self.assertFalse({r["name"] for r in a["rows"]} & {r["name"] for r in b["rows"]})

    def test_orders_page_len_is_clamped(self):
        r = C.crm_customer_orders(self.busy, kind="Sales Invoice", page_len=10_000)
        self.assertLessEqual(len(r["rows"]), 100)

    def test_orders_status_filter(self):
        r = C.crm_customer_orders(self.busy, kind="Sales Invoice", status="Paid", page_len=20)
        self.assertTrue(all(row["status"] == "Paid" for row in r["rows"]))

    def test_orders_rejects_unknown_kind(self):
        with self.assertRaises(frappe.ValidationError):
            C.crm_customer_orders(self.busy, kind="User")

    def test_pricing_names_its_source(self):
        p = C.crm_customer_pricing(self.busy)
        self.assertIn(p["source"], ("customer", "customer_group", None))
        if p["price_list"] is None:
            self.assertEqual(p["rows"], [])

    def test_pricing_search_with_underscore_is_literal(self):
        p = C.crm_customer_pricing(self.busy, search="_")
        for r in p["rows"]:
            self.assertTrue("_" in (r["item_code"] or "") or "_" in (r["item_name"] or ""))

    def test_contracts_report_availability(self):
        self.assertIn("available", C.crm_customer_contracts(self.busy))


class TestAccess(CustomerPageCase):
    ENDPOINTS = ("crm_customer_header", "crm_customer_overview", "crm_customer_orders",
                 "crm_customer_pricing", "crm_customer_contracts")

    def test_customer_endpoints_require_customer_read(self):
        # Patch the permission check: building a real user who passes _guard but
        # lacks Customer read depends on site DocPerms this test should not own.
        with patch("upande_crm.api.customer.frappe.has_permission", side_effect=frappe.PermissionError):
            for name in self.ENDPOINTS:
                with self.assertRaises(frappe.PermissionError, msg=name):
                    getattr(C, name)(self.busy)

    def test_module_off_refuses(self):
        _save(module_customer_page=0)
        for name in self.ENDPOINTS:
            with self.assertRaises(frappe.PermissionError, msg=name):
                getattr(C, name)(self.busy)

    def test_guest_is_refused(self):
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            C.crm_customer_header(self.busy)


class TestTimeline(CustomerPageCase):
    def test_note_round_trips_into_the_timeline(self):
        C.crm_customer_add_note(self.empty, "<p>Met at IFTF, wants samples</p>")
        t = C.crm_customer_timeline(self.empty)
        self.assertEqual(t["items"][0]["kind"], "note")
        self.assertIn("samples", t["items"][0]["snippet"])
        self.assertNotIn("<p>", t["items"][0]["snippet"])

    def test_note_is_a_standard_comment(self):
        C.crm_customer_add_note(self.empty, "desk can see this")
        self.assertTrue(frappe.db.exists("Comment", {
            "reference_doctype": "Customer", "reference_name": self.empty,
            "comment_type": "Comment", "content": ["like", "%desk can see this%"]}))

    def test_blank_note_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            C.crm_customer_add_note(self.empty, "<p> </p>")

    def test_timeline_filters_by_kind(self):
        C.crm_customer_add_note(self.empty, "a note")
        self.assertEqual(C.crm_customer_timeline(self.empty, kinds="email")["items"], [])
        notes = C.crm_customer_timeline(self.empty, kinds='["note"]')["items"]
        self.assertTrue(notes)
        self.assertEqual({i["kind"] for i in notes}, {"note"})

    def test_unknown_kind_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            C.crm_customer_timeline(self.busy, kinds="sms")

    def test_timeline_is_newest_first(self):
        whens = [i["when"] for i in C.crm_customer_timeline(self.busy, limit=30)["items"]]
        self.assertEqual(whens, sorted(whens, reverse=True))

    def test_timeline_pages_by_keyset(self):
        t1 = C.crm_customer_timeline(self.busy, limit=5)
        self.assertLessEqual(len(t1["items"]), 5)
        if t1["next_before"]:
            t2 = C.crm_customer_timeline(self.busy, limit=5, before=t1["next_before"])
            cursor_when = t1["next_before"].split("|")[0]
            self.assertTrue(all(i["when"] <= cursor_when for i in t2["items"]))
            first = {(i["kind"], i["ref_name"], i["when"]) for i in t1["items"]}
            self.assertFalse(first & {(i["kind"], i["ref_name"], i["when"]) for i in t2["items"]})

    def test_timeline_limit_is_clamped(self):
        self.assertLessEqual(len(C.crm_customer_timeline(self.busy, limit=5000)["items"]), 100)

    def test_busy_customer_has_email(self):
        # The customer with the most linked emails, whoever that is on this site.
        row = frappe.db.sql(
            """select l.link_name from `tabCommunication Link` l
               join `tabCommunication` c on c.name = l.parent
               where l.link_doctype='Customer' and c.communication_medium='Email'
               group by l.link_name order by count(*) desc limit 1""")
        if not row:
            self.skipTest("no customer on this site has a linked email")
        items = C.crm_customer_timeline(row[0][0], kinds="email", limit=5)["items"]
        self.assertTrue(items)
        self.assertEqual({i["kind"] for i in items}, {"email"})

    def test_items_carry_their_shape(self):
        C.crm_customer_add_note(self.empty, "shape")
        item = C.crm_customer_timeline(self.empty)["items"][0]
        self.assertEqual(set(item), {"kind", "when", "title", "snippet", "who", "ref_doctype", "ref_name"})

    def test_timeline_module_off_refuses(self):
        _save(module_customer_page=0)
        for fn in (C.crm_customer_timeline, C.crm_customer_add_note):
            with self.assertRaises(frappe.PermissionError):
                fn(self.empty, "x") if fn is C.crm_customer_add_note else fn(self.empty)


class TestTimelineTies(CustomerPageCase):
    """Emails carry second-level timestamps, and 98 customer/date groups on this
    site share one. Paging must neither drop nor repeat an item at a boundary."""

    def test_items_sharing_a_timestamp_all_appear_once(self):
        names = []
        for i in range(3):
            names.append(C.crm_customer_add_note(self.empty, f"tie note {i}")["item"])
        same = "2020-01-01 10:00:00"
        for c in frappe.get_all("Comment", filters={"reference_name": self.empty, "content": ["like", "tie note%"]}, pluck="name"):
            frappe.db.set_value("Comment", c, "creation", same, update_modified=False)
        seen, before = [], None
        for _ in range(5):
            page = C.crm_customer_timeline(self.empty, kinds="note", before=before, limit=2)
            seen += [i["snippet"] for i in page["items"] if i["snippet"].startswith("tie note")]
            before = page["next_before"]
            if not before:
                break
        self.assertEqual(sorted(seen), ["tie note 0", "tie note 1", "tie note 2"])


class TestSubDoctypeAccess(CustomerPageCase):
    """Reading a Customer is not reading its invoices, prices or emails: the page
    must show what the caller would see in the desk, not everything."""

    @staticmethod
    def _only_customer(doctype, ptype="read", doc=None, *args, **kwargs):
        return doctype == "Customer"

    def _patched(self):
        return patch("upande_crm.api.customer.frappe.has_permission", side_effect=self._only_customer)

    def test_header_hides_money_it_cannot_read(self):
        with self._patched():
            f = C.crm_customer_header(self.busy)["figures"]
        self.assertIsNone(f["lifetime_revenue"])
        self.assertIsNone(f["order_count"])
        self.assertIsNone(f["open_quotations"])

    def test_orders_say_no_access(self):
        with self._patched():
            r = C.crm_customer_orders(self.busy, kind="Sales Invoice")
        self.assertTrue(r["no_access"])
        self.assertEqual(r["rows"], [])

    def test_pricing_says_no_access(self):
        with self._patched():
            p = C.crm_customer_pricing(self.busy)
        self.assertTrue(p["no_access"])
        self.assertEqual(p["rows"], [])

    def test_overview_hides_invoiced_items(self):
        with self._patched():
            ov = C.crm_customer_overview(self.busy)
        self.assertEqual(ov["top_items"], [])
        self.assertTrue(ov["no_access"]["revenue"])

    def test_timeline_skips_unreadable_sources(self):
        C.crm_customer_add_note(self.busy, "visible to anyone who can read the customer")
        with self._patched():
            kinds = {i["kind"] for i in C.crm_customer_timeline(self.busy, limit=100)["items"]}
        self.assertEqual(kinds, {"note"})

    def test_full_access_is_unchanged(self):
        self.assertFalse(C.crm_customer_orders(self.busy, kind="Sales Invoice")["no_access"])
        self.assertIsNotNone(C.crm_customer_header(self.busy)["figures"]["lifetime_revenue"])


class TestNewTabsAndKinds(CustomerPageCase):
    def test_header_hides_tabs_of_switched_off_modules(self):
        _save(module_claims=0)
        try:
            self.assertNotIn("claims", C.crm_customer_header(self.busy)["tabs"])
        finally:
            _save(module_claims=1)
        self.assertIn("claims", C.crm_customer_header(self.busy)["tabs"])

    def test_header_counts_open_claims(self):
        from upande_crm.api.claims import crm_claim_save

        before = C.crm_customer_header(self.busy)["figures"]["open_claims"]
        crm_claim_save(frappe.as_json({"customer": self.busy, "claim_type": "Quality rejection",
                                       "description": "x"}))
        self.assertEqual(C.crm_customer_header(self.busy)["figures"]["open_claims"], before + 1)

    def test_timeline_carries_claims_and_visits(self):
        from frappe.utils import now_datetime

        from upande_crm.api.claims import crm_claim_save
        from upande_crm.api.visits import crm_visit_save

        crm_claim_save(frappe.as_json({"customer": self.empty, "claim_type": "Short shipment",
                                       "description": "two boxes missing"}))
        crm_visit_save(frappe.as_json({"visit_type": "Customer visit to farm", "party_type": "Customer",
                                       "party": self.empty, "visit_date": str(now_datetime()),
                                       "purpose": "Farm tour"}))
        kinds = {i["kind"] for i in C.crm_customer_timeline(self.empty)["items"]}
        self.assertTrue({"claim", "visit"} <= kinds)
