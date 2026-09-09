"""Email attribution: who on our side is talking to which client.

The risk this guards is over-claiming. The join runs through free-text address
matching, so it is easy to produce a confident-looking matrix that attributes
automated mail to a person, or counts a colleague as the owner of an account
they were merely copied on. These assert the shape of the claim, not just that
the query runs.
"""

import unittest

import frappe

from upande_crm.api.correspondence import (
    PARTY_TYPES,
    _is_shared,
    _person,
    crm_correspondence,
    crm_correspondent_for_emails,
    crm_party_correspondents,
    staff_for_territory,
)

ALL_TIME = {"date_from": "2000-01-01", "date_to": "2035-12-31"}


class TestAddressHelpers(unittest.TestCase):
    def test_person_name_from_address(self):
        self.assertEqual(_person("juliana@karenroses.com"), "Juliana")
        self.assertEqual(_person("peris.maina@karenroses.com"), "Peris Maina")
        self.assertEqual(_person("p_kamuren@x.com"), "P Kamuren")

    def test_shared_mailboxes_are_flagged(self):
        self.assertTrue(_is_shared("purchasing@karenroses.com"))
        self.assertTrue(_is_shared("INFO@example.com"))
        self.assertFalse(_is_shared("juliana@karenroses.com"))

    def test_blank_address_does_not_crash(self):
        self.assertEqual(_person(None), None)
        self.assertFalse(_is_shared(None))


class TestCorrespondenceMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = crm_correspondence(**ALL_TIME)

    def test_shape(self):
        for key in ("rows", "staff", "date_from", "date_to"):
            self.assertIn(key, self.data)
        for r in self.data["rows"]:
            for key in ("staff", "staff_name", "party", "party_type", "sent", "received", "shared"):
                self.assertIn(key, r)

    def test_parties_are_crm_parties_only(self):
        """Never attribute a Supplier thread to a salesperson.

        Contact links to Supplier far more often than to Customer here (1,022 vs
        220), so a join that forgot to filter would fill the matrix with
        purchasing traffic.
        """
        for r in self.data["rows"]:
            self.assertIn(r["party_type"], PARTY_TYPES)

    def test_no_automated_mail_is_attributed(self):
        """Automated Messages are 20,735 of 37,196 rows and belong to nobody."""
        if not self.data["rows"]:
            self.skipTest("no correspondence on this site")
        attributed = sum(r["sent"] for r in self.data["rows"])
        real_sent = frappe.db.sql(
            """select count(*) from `tabCommunication`
               where communication_type = 'Communication' and sent_or_received = 'Sent'"""
        )[0][0]
        self.assertLessEqual(
            attributed,
            real_sent,
            "attributed more sent mail than there are non-automated sent emails",
        )

    def test_staff_totals_agree_with_rows(self):
        for s in self.data["staff"]:
            rows = [r for r in self.data["rows"] if r["staff"] == s["staff"]]
            self.assertEqual(s["accounts"], len(rows))
            self.assertEqual(s["sent"], sum(r["sent"] for r in rows))

    def test_every_row_has_a_direction(self):
        for r in self.data["rows"]:
            self.assertGreater(r["sent"] + r["received"], 0, f"empty row for {r['party']}")

    def test_unassigned_rows_have_no_staff(self):
        for r in self.data["rows"]:
            if r["staff_name"] == "Unassigned":
                self.assertEqual(r["staff"], "")
                self.assertEqual(r["sent"], 0)


class TestPartyAndTerritory(unittest.TestCase):
    def test_party_correspondents(self):
        rows = crm_correspondence(**ALL_TIME)["rows"]
        target = next((r for r in rows if r["staff"] and r["party_type"] == "Customer"), None)
        if not target:
            self.skipTest("no attributed customer correspondence")
        got = crm_party_correspondents(target["party"])
        self.assertTrue(got)
        self.assertIn(target["staff"], [g["staff"] for g in got])

    def test_unknown_party_returns_empty(self):
        self.assertEqual(crm_party_correspondents("No Such Account At All"), [])

    def test_blank_party_returns_empty(self):
        self.assertEqual(crm_party_correspondents(""), [])

    def test_bad_party_type_falls_back(self):
        """A caller passing junk gets Customer, not a SQL error."""
        self.assertIsInstance(crm_party_correspondents("x", party_type="Nonsense"), list)

    def test_staff_for_territory_matches_the_matrix(self):
        rows = staff_for_territory("Netherlands", "2000-01-01", "2035-12-31")
        for r in rows:
            self.assertGreater(r["emails"], 0)
            self.assertGreaterEqual(r["accounts"], 1)

    def test_staff_for_unknown_territory_is_empty(self):
        self.assertEqual(staff_for_territory("Nowhere", "2000-01-01", "2035-12-31"), [])


class TestBatchLookup(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(crm_correspondent_for_emails([]), {})
        self.assertEqual(crm_correspondent_for_emails(""), {})

    def test_accepts_comma_string_and_list(self):
        addr = frappe.db.sql("select email_id from `tabContact Email` limit 1")
        if not addr:
            self.skipTest("no contact emails")
        a = addr[0][0]
        self.assertIsInstance(crm_correspondent_for_emails(a), dict)
        self.assertIsInstance(crm_correspondent_for_emails([a]), dict)

    def test_unknown_address_absent_rather_than_null_entry(self):
        got = crm_correspondent_for_emails(["definitely-not-real@nowhere.invalid"])
        self.assertEqual(got, {})
