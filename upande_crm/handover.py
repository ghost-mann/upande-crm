"""What one pipeline stage owes the next.

ERPNext carries most of this already, and the measured list of what it carries is
in `tests/test_handover.py` rather than repeated here. One hop does not:
**Prospect -> Opportunity.**

`Prospect.make_opportunity` maps four fields, and Prospect holds no email, mobile
or contact field of its own — its people live in linked Contact documents and in
its `Prospect Lead` rows. So the mapper has nothing to copy, and the opportunity
lands with no one to call. Measured on this site before this module existed: of
the 8 opportunities raised from a prospect, **0 carried a contact person and 0 a
contact email** — while across the 44 prospects there were 76 Contact and 43 Address
documents linked and reachable, which is what makes the loss avoidable.

Lead -> Opportunity has never had this problem because `lead.make_opportunity`
calls `_set_missing_values`, which walks the Dynamic Links for exactly these two
fields. This module does for a prospect what ERPNext already does for a lead.

## Why this is a document hook and not a change to `api/leads.py`

The same gap exists whichever button is pressed — this app's convert dialog, the
desk's own **Create > Opportunity** on a Prospect, an import, the REST API. Fixing
it in our endpoint would fix one caller and leave the rest, and the desk is where
most conversions still happen. So it hangs off `before_insert`: one implementation,
every caller, and it runs before mandatory-field validation so a site that has made
`contact_email` mandatory on Opportunity stops failing rather than starts.

## The one deliberate bare except in this app

`api/leads.py` opens with a rule: never wrap a write in a bare `except`, because a
lead the user believes they saved and which was silently dropped is the worst
outcome that module can produce. This module breaks that rule knowingly, and the
reasoning inverts cleanly: we are a guest in someone else's insert path. Every
Opportunity on the site now passes through here, including ones no CRM user asked
for. A carry-over that fails must cost a contact detail, never the document. The
failure goes to the Error Log so it is still visible.

Two guards keep the footprint honest: nothing happens unless the document names a
Prospect as its source, and nothing is ever overwritten — `set_if_empty` yields to
whatever the mapper, the dialog or the user already put there.
"""

import frappe

# The Contact fields worth carrying, and where they land on an Opportunity.
# `email_id` and `mobile_no` on a Contact are maintained by its own controller from
# the primary rows of its email and phone tables, so reading them here gets the
# primary address and number without re-deriving which row is primary.
CONTACT_MAP = (("email_id", "contact_email"), ("mobile_no", "contact_mobile"))


def set_if_empty(doc, fieldname, value):
    """Fill a field only if the target has it and nothing has claimed it yet.

    Three refusals, in order of how often they matter: an empty value carries
    nothing; a value already present was put there by the mapper, the convert
    dialog or the user, and outranks anything derived here; and a field this site's
    schema does not have cannot be set at all.
    """
    if value in (None, ""):
        return
    if doc.get(fieldname):
        return
    if not doc.meta.get_field(fieldname):
        return
    doc.set(fieldname, value)


def _linked(parenttype, doctype, name, primary_field):
    """The `parenttype` document linked to `doctype`/`name`, preferring the primary.

    Contacts and Addresses attach to a party through Dynamic Links, so a prospect
    with three contacts has three rows and no ordering worth trusting. The one
    flagged primary wins; failing that, the oldest, so repeated conversions of the
    same prospect agree with each other.
    """
    names = frappe.get_all(
        "Dynamic Link",
        filters={"link_doctype": doctype, "link_name": name, "parenttype": parenttype},
        pluck="parent",
    )
    if not names:
        return None
    if len(names) > 1:
        primary = frappe.get_all(parenttype, filters={"name": ["in", names], primary_field: 1},
                                 pluck="name", order_by="creation asc", limit=1)
        if primary:
            return primary[0]
    return sorted(names)[0]


def _from_prospect(doc):
    """Give the opportunity the prospect's contact person and billing address."""
    prospect = doc.party_name

    contact = _linked("Contact", "Prospect", prospect, "is_primary_contact")
    if contact:
        row = frappe.db.get_value(
            "Contact", contact, ["first_name", "last_name", "email_id", "mobile_no"],
            as_dict=True) or {}
        set_if_empty(doc, "contact_person", contact)
        set_if_empty(doc, "contact_display",
                     " ".join(filter(None, [row.get("first_name"), row.get("last_name")])))
        for source, target in CONTACT_MAP:
            set_if_empty(doc, target, row.get(source))

    set_if_empty(doc, "customer_address",
                 _linked("Address", "Prospect", prospect, "is_primary_address"))


def before_insert(doc, method=None):
    """Hooked on Opportunity. Does nothing unless a Prospect is the source."""
    if doc.doctype != "Opportunity":
        return
    if doc.get("opportunity_from") != "Prospect" or not doc.get("party_name"):
        return
    try:
        _from_prospect(doc)
    except Exception:
        # See the module docstring: a failed carry-over must never cost the document.
        frappe.log_error(frappe.get_traceback(), f"CRM handover: Prospect {doc.party_name}")
