"""Fixtures shared by the capture, advance and carry-across tests.

Extracted when conversion moved out of `api/leads.py` into `api/advance.py` and
three test modules needed the same lead.

Nothing here is hardcoded to a site. The install these tests run against has made
eleven Lead fields mandatory, two of them custom, so a fixture that named its
fields would break on the next site. `required_values()` reads the meta instead.
"""

import itertools
import json

import frappe

from upande_crm.api import leads as L

# A Data field's `options` carries its format. Filling one with free text fails
# validation — `email_id` is mandatory here and rejected anything without an @.
FORMATTED = {
    "Email": "probe-test@example.com",
    "Phone": "+254700111222",
    "URL": "https://example.com",
}


def an_item():
    rows = frappe.get_all("Item", filters={"disabled": 0}, pluck="name", limit=1)
    return rows[0] if rows else None


def a_link(doctype):
    rows = frappe.get_all(doctype, pluck="name", limit=1)
    return rows[0] if rows else None


def required_values():
    """Plausible values for whatever this site insists on, so a create can succeed."""
    out = {}
    for f in L._required_lead_fields():
        name, ftype, opts = f["fieldname"], f["fieldtype"], f["options"]
        if f.get("default"):
            out[name] = f["default"]
        elif ftype == "Link":
            rows = frappe.get_all(opts, pluck="name", limit=1) if opts else []
            if rows:
                out[name] = rows[0]
        elif ftype == "Select":
            choices = [o for o in str(opts or "").split("\n") if o]
            if choices:
                out[name] = choices[0]
        elif ftype in ("Int", "Float", "Currency", "Percent"):
            out[name] = 1
        elif opts in FORMATTED:
            out[name] = FORMATTED[opts]
        elif "email" in name:
            out[name] = FORMATTED["Email"]
        elif "mobile" in name or "phone" in name or "whatsapp" in name:
            out[name] = FORMATTED["Phone"]
        else:
            out[name] = f"probe-{name}"
    return out


# Lead enforces a unique email, and Prospect is named by its company, so two
# fixtures built from the same constants collide with each other rather than with
# anything real. Every payload gets its own identity.
_seq = itertools.count()


def lead_payload(**over):
    # Site requirements first, then this module's own identity fields on top, so a
    # generated placeholder never displaces the name the test is asserting on.
    n = next(_seq)
    body = required_values()
    body.update({
        "lead_name": f"Probe Buyer {n}",
        "company_name": f"Probe Florals Test {n} Ltd",
        "email_id": f"probe-test-{n}@example.com",
        "status": "Lead",
    })
    body.update(over)
    return body


def save_lead(**over):
    return L.crm_lead_save(json.dumps(lead_payload(**over)))


def rich_lead(**over):
    """A lead with every field the carry-across reads, where the site allows it.

    Written directly rather than through `crm_lead_save`, because the capture
    allowlist does not accept the custom billing fields — they are entered in the
    desk, and the carry-across still has to move them.

    `over` is applied **last**, after the site-dependent defaults below. Applying
    it earlier let those defaults refill a field a test had deliberately cleared,
    which then tripped this site's address Server Script instead of testing
    anything.
    """
    n = next(_seq)
    body = required_values()
    body.update({
        "lead_name": f"Carry Probe {n}",
        "first_name": "Jane",
        "last_name": f"Muthoni {n}",
        "company_name": f"Carry Probe Florals {n} Ltd",
        "email_id": f"carry-probe-{n}@example.com",
        "mobile_no": "+254700111333",
        "phone": "+254200111444",
        "whatsapp_no": "+254700999888",
        "job_title": "Head of Procurement",
        "status": "Lead",
        "no_of_employees": "11-50",
        "custom_billing_street_address": "12 Rose Road",
        "custom_billing_city": "Naivasha",
        "custom_billing_postal_code": "20117",
    })

    meta = frappe.get_meta("Lead")
    country = a_link("Country")
    if country:
        body["country"] = country
        body["custom_billing_country"] = country
    currency = a_link("Currency")
    if currency:
        body["custom_billing_currency"] = currency
    price_list = frappe.get_all("Price List", filters={"selling": 1}, pluck="name", limit=1)
    if price_list:
        body["custom_price_list"] = price_list[0]

    body.update(over)

    # Only set what this site actually has; the map is written against one schema
    # and the fixture must not invent columns.
    body = {k: v for k, v in body.items() if meta.get_field(k)}

    doc = frappe.get_doc({"doctype": "Lead", **body})
    doc.insert(ignore_permissions=True)
    return doc


def lead_without_address(**over):
    """A rich lead whose billing fields are empty, so no Address can be built.

    All three custom billing fields are cleared, not just the street line. This
    site runs a Server Script, "Shipping and Billing Address Creation", on Lead
    after-insert whose guard is `if not (line1 or city or country)` — leaving the
    city set would send it on to insert an Address with no `address_line1` and
    fail the fixture on a pre-existing site bug rather than on anything under
    test. The lead's own `city` and `country` stay populated (they are mandatory
    here), which is what makes this the case that proves they survive in the
    notes instead.
    """
    return rich_lead(
        custom_billing_street_address="",
        custom_billing_address="",
        custom_billing_city="",
        custom_billing_country="",
        **over,
    )
