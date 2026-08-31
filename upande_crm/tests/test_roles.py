"""Tests for the two roles this app owns.

`CRM Manager` and `CRM User` are created by `setup.py` and are the roles the desk
workspaces and `api/crm._guard()` gate on. They used to carry no DocPerm rows at
all, which made them a trap rather than a role: holding one opened the dashboard
and then refused every write, because each hop in `api/advance.py` checks
`create` on the document it is about to make. Every assertion here exists to stop
that coming back.

The permission checks use a throwaway user holding exactly *one* role. Reading
DocPerm rows would not do: permlevel, `if_owner` and user permissions all sit
between a row and an answer, so the only trustworthy question is the one Frappe
itself asks — `frappe.has_permission(doctype, "create", user=...)`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api.advance import HOPS
from upande_crm.api.crm import CRM_ROLES
from upande_crm.setup import (
    CRM_ROLE_PERMS,
    OWNED_ROLES,
    ensure_crm_role_permissions,
    ensure_crm_roles,
)

# Every doctype a hop creates, plus the two the carry-across writes. Contact and
# Address are not incidental: without them a converted customer has no email
# address, because `Customer.email_id` is fetched from its primary contact.
NEEDED = ["Lead", "Prospect", "Opportunity", "Quotation", "Customer", "Contact", "Address"]


# `ensure_crm_role_permissions` clears the whole permission cache, so calling it
# per test cost ~40s each. It is idempotent, so once per module is enough — the
# idempotence test below calls it again deliberately.
_granted = False


def _grant_once():
    global _granted
    if not _granted:
        ensure_crm_roles()
        ensure_crm_role_permissions()
        _granted = True


def _user_with_role(role):
    email = f"_roletest_{frappe.scrub(role)}@example.com"
    if frappe.db.exists("User", email):
        frappe.delete_doc("User", email, force=True, ignore_permissions=True)
    frappe.get_doc({
        "doctype": "User", "email": email, "first_name": "Role Test",
        "send_welcome_email": 0, "user_type": "System User",
        "roles": [{"role": role}],
    }).insert(ignore_permissions=True)
    return email


class TestTheRolesExist(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _grant_once()

    def test_both_owned_roles_exist(self):
        for role in OWNED_ROLES:
            self.assertTrue(frappe.db.exists("Role", role), f"{role} was not created")

    def test_the_owned_roles_are_in_the_dashboard_gate(self):
        # A role the app creates but `_guard()` does not accept would open nothing.
        for role in OWNED_ROLES:
            self.assertIn(role, CRM_ROLES)

    def test_the_roles_have_desk_access(self):
        for role in OWNED_ROLES:
            self.assertTrue(frappe.db.get_value("Role", role, "desk_access"),
                            f"{role} cannot reach the desk")


class TestTheRolesCanActuallyWork(FrappeTestCase):
    """The property that matters: getting in and being able to do nothing is worse
    than not getting in."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _grant_once()

    def test_each_owned_role_can_create_everything_a_hop_needs(self):
        for role in OWNED_ROLES:
            user = _user_with_role(role)
            for doctype in NEEDED:
                with self.subTest(role=role, doctype=doctype):
                    self.assertTrue(
                        frappe.has_permission(doctype, "create", user=user),
                        f"{role} cannot create {doctype}, so a hop is dead for them",
                    )

    def test_each_owned_role_can_take_every_hop(self):
        for role in OWNED_ROLES:
            user = _user_with_role(role)
            for (source, target) in sorted(HOPS):
                with self.subTest(role=role, hop=f"{source}->{target}"):
                    self.assertTrue(
                        frappe.has_permission(target, "create", user=user),
                        f"{role} cannot take {source} -> {target}",
                    )

    def test_the_roles_can_read_items_for_the_variety_picker(self):
        for role in OWNED_ROLES:
            user = _user_with_role(role)
            self.assertTrue(frappe.has_permission("Item", "read", user=user))

    def test_neither_role_can_delete(self):
        # Modelled on the sales roles, which have no delete on these doctypes.
        for role in OWNED_ROLES:
            user = _user_with_role(role)
            for doctype in ("Lead", "Customer"):
                with self.subTest(role=role, doctype=doctype):
                    self.assertFalse(frappe.has_permission(doctype, "delete", user=user))


class TestTheGrantIsSafe(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _grant_once()

    def test_granting_twice_changes_nothing(self):
        # It runs on every migrate, so it has to be idempotent.
        before = frappe.db.count("Custom DocPerm")
        ensure_crm_role_permissions()
        self.assertEqual(frappe.db.count("Custom DocPerm"), before)

    def test_it_never_revokes_what_another_role_had(self):
        # `add_permission` copies standard perms into Custom DocPerm first; a bug
        # there would silently strip every other role on the doctype.
        for doctype in ("Lead", "Quotation", "Customer"):
            with self.subTest(doctype=doctype):
                self.assertTrue(
                    frappe.db.exists("Custom DocPerm",
                                     {"parent": doctype, "role": "System Manager"}),
                    f"System Manager lost its permissions on {doctype}",
                )

    def test_every_doctype_in_the_table_exists(self):
        # A typo would be granted into the void and never noticed.
        for role, table in CRM_ROLE_PERMS.items():
            for (doctype, _level) in table:
                with self.subTest(role=role, doctype=doctype):
                    self.assertTrue(frappe.db.exists("DocType", doctype))

    def test_every_flag_in_the_table_is_a_real_permission(self):
        valid = set(frappe.permissions.rights)
        for role, table in CRM_ROLE_PERMS.items():
            for key, flags in table.items():
                for flag in flags.split(","):
                    with self.subTest(role=role, doctype=key[0], flag=flag):
                        self.assertIn(flag, valid)
