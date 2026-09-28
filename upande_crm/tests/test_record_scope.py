"""Record-level permissions on the new views.

A Sales User restricted by User Permissions (to their own customers, or a
territory) must see only those records on the claims and visits dashboards and on
the pipeline board — the same records the desk would show them. Checking only
doctype-level read showed everything.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, now_datetime, nowdate

from upande_crm.api import board as B
from upande_crm.api import claims as CL
from upande_crm.api import visits as V

EMAIL = "crm-scope-test@example.com"


def _restricted_user(allow_doctype, value):
    if frappe.db.exists("User", EMAIL):
        frappe.delete_doc("User", EMAIL, force=True, ignore_permissions=True)
    frappe.get_doc({"doctype": "User", "email": EMAIL, "first_name": "Scope Test", "send_welcome_email": 0,
                    "user_type": "System User", "roles": [{"role": "Sales User"}, {"role": "CRM User"}]
                    }).insert(ignore_permissions=True)
    frappe.get_doc({"doctype": "User Permission", "user": EMAIL, "allow": allow_doctype,
                    "for_value": value, "apply_to_all_doctypes": 1}).insert(ignore_permissions=True)
    frappe.clear_cache(user=EMAIL)


class TestRecordScope(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        from upande_crm.setup import ensure_crm_role_permissions

        ensure_crm_role_permissions()
        custs = frappe.get_all("Customer", pluck="name", limit=2)
        cls.mine, cls.theirs = custs[0], custs[1]

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_claims_dashboard_shows_only_permitted_customers(self):
        for c in (self.mine, self.theirs):
            CL.crm_claim_save(frappe.as_json({"customer": c, "claim_type": "Quality rejection", "description": "x"}))
        _restricted_user("Customer", self.mine)
        frappe.set_user(EMAIL)
        rows = CL.crm_dashboard_claims(add_days(nowdate(), -1), nowdate())["rows"]
        self.assertTrue(rows)
        self.assertEqual({r["customer"] for r in rows}, {self.mine})

    def test_visits_dashboard_shows_only_permitted_customers(self):
        for c in (self.mine, self.theirs):
            V.crm_visit_save(frappe.as_json({"visit_type": "Sales visit to customer", "party_type": "Customer",
                                             "party": c, "visit_date": str(now_datetime()), "purpose": "Farm tour"}))
        _restricted_user("Customer", self.mine)
        frappe.set_user(EMAIL)
        rows = V.crm_dashboard_visits(add_days(nowdate(), -1), add_days(nowdate(), 1))["rows"]
        self.assertTrue(all(r["party"] == self.mine for r in rows))

    def test_board_leads_respect_a_territory_restriction(self):
        terr = frappe.db.sql("""select territory from tabLead where ifnull(territory,'')!='' group by territory
                                order by count(*) desc limit 1""")
        if not terr:
            self.skipTest("no leads with a territory")
        _restricted_user("Territory", terr[0][0])
        frappe.set_user(EMAIL)
        leads = next(c for c in B.crm_pipeline_board()["columns"] if c["key"] == "leads")
        names = [c["name"] for c in leads["cards"]]
        frappe.set_user("Administrator")
        other = frappe.get_all("Lead", filters={"name": ["in", names or [""]], "territory": ["not in", [terr[0][0], ""]]},
                               pluck="name")
        self.assertEqual(other, [])
