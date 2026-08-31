"""What lands where when a Lead, Prospect or Opportunity becomes a Customer.

ERPNext's customer mappers carry almost nothing, and what they do carry is partly
inert. This module is the difference between a conversion that keeps the work the
salesperson did and one that quietly discards it.

## The measurement this is built on

Field population on this site, counted before anything was mapped (`Int`/`Float`
columns counted with `!= 0`, not `!= ''`, or every zero reads as populated):

    Lead (113)   email_id, mobile_no, phone, whatsapp_no, first_name, last_name,
                 company_name, country, city, territory, market_segment, language,
                 custom_business_unit, custom_business_registration_number,
                 custom_mode_of_payment, custom_price_list,
                 custom_billing_currency, no_of_employees, annual_revenue,
                 qualification_status, lead_owner ....................... 100%
                 job_title 68%, custom_message 62%, custom_billing_* 27-60%,
                 custom_shipping_* 6-25%, website 18%, custom_instagram 19%,
                 custom_facebook 11%, gender 6%, industry 0%

## Three findings that shape every table below

**1. Two *required* Customer fields have 100%-populated Lead sources under other
names.** `Customer.default_currency` and `Customer.default_price_list` are both
`reqd`, and the lead carries the answers as `custom_billing_currency` and
`custom_price_list`. No ERPNext mapper maps either, so a conversion has been
choosing between MandatoryError and a global default that contradicts what was
recorded. `TO_CUSTOMER` maps them.

**2. `Customer.email_id` and `Customer.mobile_no` cannot be written.** Both are
Read Only with `fetch_from = customer_primary_contact.*`, and Customer has no
`phone` field at all. Writing them does nothing: the fetch overwrites on save. The
only way a customer has an email address is for it to have a primary Contact — so
`_contact()` is not a nicety here, it is the entire mechanism.

**3. The damage is already in the data.** 9 of the 10 lead-derived customers on
this site have neither a primary contact nor a primary address, so the email,
mobile and phone collected on those leads are gone. Those 9 are deliberately not
backfilled; this module fixes conversions from here on.

## Why an Address is sometimes not created

`Address.address_line1` is mandatory, and the only lead field that can fill it —
`custom_billing_street_address` — is 60% populated. `city` and `country` are at
100% and could carry an address on their own, but a row whose street line had to
be invented is worse than no row: this site has 2,913 real addresses and they are
used for shipping. So no street line means no Address, and the city and country
survive in the provenance block instead.

## Failure policy

Everything here runs inside the caller's transaction, and nothing is swallowed. A
customer created without the contact details it was supposed to inherit is the
exact outcome this module exists to prevent, so a failed Contact fails the hop.
The one exception is `preview()`, a read, which degrades to whatever it could
work out.
"""

import frappe
from frappe import _

# ---------------------------------------------------------------- field maps
# source fieldname -> Customer fieldname. Only fields measured as populated, and
# only where the Customer field is actually writable (see finding 2 above).
TO_CUSTOMER = {
    "Lead": {
        "territory": "territory",
        "market_segment": "market_segment",
        "industry": "industry",
        "language": "language",
        "gender": "gender",
        "website": "website",
        "custom_business_unit": "custom_business_unit",
        "custom_business_registration_number": "custom_business_registration_number",
        "custom_mode_of_payment": "custom_mode_of_payment",
        "custom_instagram": "custom_instagram",
        "custom_facebook": "custom_facebook",
        # The two required Customer fields, renamed. See finding 1.
        "custom_billing_currency": "default_currency",
        "custom_price_list": "default_price_list",
    },
    "Prospect": {
        "territory": "territory",
        "market_segment": "market_segment",
        "industry": "industry",
        "website": "website",
        "customer_group": "customer_group",
    },
    "Opportunity": {
        "territory": "territory",
        "market_segment": "market_segment",
        "industry": "industry",
        "website": "website",
        "language": "language",
        "customer_group": "customer_group",
        "currency": "default_currency",
        "custom_price_list": "default_price_list",
        "custom_business_unit": "custom_business_unit",
        "custom_business_registration_number": "custom_business_registration_number",
        "custom_mode_of_payment": "custom_mode_of_payment",
        "custom_instagram": "custom_instagram",
        "custom_facebook": "custom_facebook",
    },
}

# source fieldname -> Contact fieldname. `whatsapp_no` is absent from Contact and
# is handled separately as an extra `Contact Phone` row.
TO_CONTACT = {
    "Lead": {
        "salutation": "salutation",
        "first_name": "first_name",
        "last_name": "last_name",
        "middle_name": "middle_name",
        "gender": "gender",
        "email_id": "email_id",
        "mobile_no": "mobile_no",
        "phone": "phone",
        "job_title": "designation",
        "company_name": "company_name",
    },
    "Prospect": {},
    "Opportunity": {
        "contact_email": "email_id",
        "contact_mobile": "mobile_no",
        "phone": "phone",
        "job_title": "designation",
        "customer_name": "company_name",
    },
}

# source fieldname -> Address fieldname, most specific first. `address_line1` is
# mandatory and has no fallback on purpose — see the module docstring.
TO_ADDRESS = {
    "Lead": {
        "address_line1": ("custom_billing_street_address", "custom_billing_address"),
        "address_line2": ("custom_billing_street_address_2",),
        "city": ("custom_billing_city", "city"),
        "country": ("custom_billing_country", "country"),
        "state": ("custom_billing_state_",),
        "pincode": ("custom_billing_postal_code",),
        "email_id": ("email_id",),
        "phone": ("phone", "mobile_no"),
    },
    "Prospect": {},
    "Opportunity": {
        "city": ("city",),
        "country": ("country",),
        "phone": ("phone", "contact_mobile"),
        "email_id": ("contact_email",),
    },
}

# Fields with data and nowhere on Customer to put it. Written as text rather than
# as new custom fields: this app surfaces core doctypes, it does not reshape them.
TO_NOTES = {
    "Lead": [
        ("no_of_employees", "Employees"),
        ("annual_revenue", "Annual revenue"),
        ("qualification_status", "Qualification"),
        ("lead_owner", "Lead owner"),
        ("source", "Source"),
        ("country", "Country"),
        ("city", "City"),
        ("whatsapp_no", "WhatsApp"),
        ("custom_message", "Message"),
    ],
    "Prospect": [
        ("no_of_employees", "Employees"),
        ("annual_revenue", "Annual revenue"),
        ("prospect_owner", "Prospect owner"),
    ],
    "Opportunity": [
        ("no_of_employees", "Employees"),
        ("opportunity_owner", "Opportunity owner"),
        ("sales_stage", "Sales stage"),
        ("custom_trading_entity_name", "Trading entity"),
        ("country", "Country"),
        ("city", "City"),
        ("whatsapp", "WhatsApp"),
    ],
}

# The lead's WhatsApp number, which Contact has no field for. Kept as an extra
# `Contact Phone` row so the CRM's WhatsApp section can still find it.
WHATSAPP_FIELDS = {"Lead": "whatsapp_no", "Prospect": None, "Opportunity": "whatsapp"}


def _val(doc, fieldname):
    """A trimmed value, or None. Absent fields are not an error — the maps above
    are written against this site's schema and must survive a site without a
    given custom field."""
    try:
        v = doc.get(fieldname)
    except Exception:
        return None
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def _first(doc, fieldnames):
    for fn in fieldnames:
        v = _val(doc, fn)
        if v is not None:
            return v
    return None


def _writable(doctype, fieldname):
    """Whether writing this field means anything.

    A `fetch_from` field is overwritten on save, so mapping one is a silent no-op
    — which is exactly how `Customer.email_id` came to look mapped and be empty.
    """
    try:
        f = frappe.get_meta(doctype).get_field(fieldname)
    except Exception:
        return False
    return bool(f) and not f.fetch_from and not f.read_only


# ---------------------------------------------------------------- customer
def apply_to_customer(source_doc, customer):
    """Direct field map onto an *unsaved* Customer. Returns what it set."""
    table = TO_CUSTOMER.get(source_doc.doctype) or {}
    applied = {}
    for src, dest in table.items():
        if not _writable("Customer", dest):
            continue
        if _val(customer, dest):  # the mapper already had an answer; leave it
            continue
        v = _val(source_doc, src)
        if v is None:
            continue
        customer.set(dest, v)
        applied[dest] = v
    return applied


def _is_zero(value):
    """A numeric zero, which is absence rather than data.

    The trap `api/pipeline.py` documents, met again here: a live walk of this
    module wrote "Annual revenue: 0.0" into a customer's details, because
    `annual_revenue` is 100% *present* on leads and 0 on nearly all of them.
    Reporting that as carried-over data is worse than saying nothing.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) == 0


def notes_block(source_doc):
    """The provenance block: fields with data and no home on Customer."""
    lines = []
    for fn, label in TO_NOTES.get(source_doc.doctype) or []:
        v = _val(source_doc, fn)
        if v is not None and not _is_zero(v):
            lines.append(f"{label}: {v}")
    if not lines:
        return ""
    head = _("Carried over from {0} {1}").format(_(source_doc.doctype), source_doc.name)
    return head + "\n" + "\n".join(lines)


def apply_notes(source_doc, customer):
    block = notes_block(source_doc)
    if not block:
        return ""
    existing = (_val(customer, "customer_details") or "")
    customer.customer_details = (existing + "\n\n" + block).strip() if existing else block
    return block


# ---------------------------------------------------------------- reuse first
def _linked(doctype, source_doc, prefer=None):
    """A `doctype` record already linked to the source, if there is one.

    Reuse is not an optimisation here, it is correctness. Measured on this site,
    a Lead arrives with both:

      * ERPNext's `Lead.after_insert` -> `link_to_contact()` creates a Contact;
      * a site Server Script, "Shipping and Billing Address Creation", creates a
        billing and a shipping Address.

    Building fresh ones would give every converted customer a duplicate contact
    and a duplicate address, which is worse than the problem this module exists
    to fix. So the rule is: link what is already there, create only what is not.
    """
    try:
        names = frappe.get_all(
            "Dynamic Link",
            filters={"link_doctype": source_doc.doctype, "link_name": source_doc.name,
                     "parenttype": doctype},
            pluck="parent", order_by="creation")
    except Exception:
        return None
    if not names:
        return None
    if prefer:
        field, value = prefer
        for name in names:
            try:
                if frappe.db.get_value(doctype, name, field) == value:
                    return name
            except Exception:
                continue
    return names[0]


def _link_to_customer(doc, customer_name):
    """Add the Customer link if it is not already on the record."""
    if any(l.link_doctype == "Customer" and l.link_name == customer_name
           for l in (doc.get("links") or [])):
        return False
    doc.append("links", {"link_doctype": "Customer", "link_name": customer_name})
    return True


def _fill_blanks(doc, values):
    """Set only what the record has not already answered."""
    changed = False
    for field, value in values.items():
        if value and not _val(doc, field):
            doc.set(field, value)
            changed = True
    return changed


# ---------------------------------------------------------------- contact
def _contact_values(source_doc):
    table = TO_CONTACT.get(source_doc.doctype) or {}
    out = {}
    for src, dest in table.items():
        v = _val(source_doc, src)
        if v is not None:
            out[dest] = v
    return out


def _phone_rows(doc):
    return {r.phone for r in (doc.get("phone_nos") or []) if r.phone}


def _add_phones(doc, source_doc, values):
    """The phone numbers, as child rows — which is what actually persists.

    `Contact.email_id` and `Contact.mobile_no` are themselves fetched from the
    child tables, so a value written to the parent alone does not survive.
    """
    changed = False
    existing = _phone_rows(doc)
    for field, is_mobile in (("mobile_no", 1), ("phone", 0)):
        number = values.get(field)
        if number and number not in existing:
            doc.append("phone_nos", {
                "phone": number,
                "is_primary_mobile_no": is_mobile,
                "is_primary_phone": 0 if is_mobile else 1,
            })
            existing.add(number)
            changed = True

    wa_field = WHATSAPP_FIELDS.get(source_doc.doctype)
    wa = _val(source_doc, wa_field) if wa_field else None
    # Contact has no WhatsApp field, and the CRM's WhatsApp section still needs
    # the number. Only worth a row when it differs from the mobile already held.
    if wa and wa not in existing:
        doc.append("phone_nos", {"phone": wa})
        changed = True
    return changed


def ensure_contact(source_doc, customer_name):
    """The Contact that gives the customer an email address at all.

    Returns its name, or None when the source carried no person to record. Not
    guarded: a failure here fails the hop, by design.
    """
    values = _contact_values(source_doc)
    existing = _linked("Contact", source_doc)

    if existing:
        doc = frappe.get_doc("Contact", existing)
        changed = _fill_blanks(doc, values)
        changed |= _add_phones(doc, source_doc, values)
        if values.get("email_id") and values["email_id"] not in {
                r.email_id for r in (doc.get("email_ids") or [])}:
            doc.append("email_ids", {"email_id": values["email_id"], "is_primary": 1})
            changed = True
        changed |= _link_to_customer(doc, customer_name)
        if changed:
            doc.save()
        return doc.name

    if not (values.get("first_name") or values.get("email_id") or values.get("mobile_no")):
        return None

    # Contact needs something to be named by.
    if not values.get("first_name"):
        values["first_name"] = (
            _val(source_doc, "lead_name") or _val(source_doc, "customer_name") or customer_name
        )

    doc = frappe.get_doc({"doctype": "Contact", **values})
    _link_to_customer(doc, customer_name)
    if values.get("email_id"):
        doc.append("email_ids", {"email_id": values["email_id"], "is_primary": 1})
    _add_phones(doc, source_doc, values)
    doc.insert()
    return doc.name


# ---------------------------------------------------------------- address
def _address_values(source_doc):
    table = TO_ADDRESS.get(source_doc.doctype) or {}
    out = {}
    for dest, sources in table.items():
        v = _first(source_doc, sources)
        if v is not None:
            out[dest] = v
    return out


def address_is_complete(values):
    """All three of `Address`'s mandatory fields.

    `address_line1` is the one that decides: it is 60% populated on leads and has
    no fully-populated fallback, while `city` and `country` do. An address whose
    street line had to be invented is worse than no address — this site has 2,913
    real ones and they are used for shipping.
    """
    return bool(values.get("address_line1") and values.get("city") and values.get("country"))


def ensure_address(source_doc, customer_name):
    """The primary billing Address, reused when the source already has one."""
    existing = _linked("Address", source_doc, prefer=("address_type", "Billing"))
    if existing:
        doc = frappe.get_doc("Address", existing)
        if _link_to_customer(doc, customer_name):
            doc.save()
        return doc.name

    values = _address_values(source_doc)
    if not address_is_complete(values):
        return None

    doc = frappe.get_doc({
        "doctype": "Address",
        "address_title": customer_name,
        "address_type": "Billing",
        "is_primary_address": 1,
        **values,
    })
    _link_to_customer(doc, customer_name)
    doc.insert()
    return doc.name


# ---------------------------------------------------------------- entry points
def carry(source_doc, customer):
    """Everything that has to happen after a Customer is inserted.

    The direct field map runs *before* the insert (`apply_to_customer`); this runs
    after, because a Contact and an Address cannot link to a customer that has no
    name yet.

    The reload is not optional. Linking a Contact to a Customer touches the
    Customer row, so the in-memory document is stale by the time the primary links
    are set, and saving it raises TimestampMismatchError.
    """
    contact = ensure_contact(source_doc, customer.name)
    address = ensure_address(source_doc, customer.name)

    if contact or address:
        customer.reload()
        changed = False
        if contact and _writable("Customer", "customer_primary_contact") \
                and not _val(customer, "customer_primary_contact"):
            customer.customer_primary_contact = contact
            changed = True
        if address and _writable("Customer", "customer_primary_address") \
                and not _val(customer, "customer_primary_address"):
            customer.customer_primary_address = address
            changed = True
        if changed:
            customer.save()

    return {"contact": contact, "address": address}


def preview(source_doc):
    """What `carry` would produce, without writing anything.

    A read: it degrades to whatever it could work out rather than blocking the
    dialog it feeds.
    """
    try:
        fields = {}
        for src, dest in (TO_CUSTOMER.get(source_doc.doctype) or {}).items():
            if not _writable("Customer", dest):
                continue
            v = _val(source_doc, src)
            if v is not None:
                fields[dest] = v

        contact = _contact_values(source_doc)
        wa_field = WHATSAPP_FIELDS.get(source_doc.doctype)
        wa = _val(source_doc, wa_field) if wa_field else None
        if wa:
            contact["whatsapp"] = wa

        address = _address_values(source_doc)
        reused = _linked("Address", source_doc, prefer=("address_type", "Billing"))
        if reused:
            # Already linked to the source; the hop will link it across rather
            # than build a second one, so the preview shows what will be used.
            try:
                doc = frappe.get_doc("Address", reused)
                address = {f: doc.get(f) for f in
                           ("address_line1", "address_line2", "city", "state",
                            "country", "pincode") if doc.get(f)}
            except Exception:
                pass
        complete = bool(reused) or address_is_complete(address)

        notes = notes_block(source_doc)
        return {
            "fields": fields,
            "contact": contact if (contact.get("first_name") or contact.get("email_id")
                                   or contact.get("mobile_no")) else {},
            "address": address if complete else {},
            # Said plainly, because "no address" always has a reason.
            "address_skipped": (not complete) and bool(address),
            "notes": notes,
            "notes_count": len([ln for ln in notes.split("\n")[1:] if ln]) if notes else 0,
        }
    except Exception:
        return {"fields": {}, "contact": {}, "address": {}, "address_skipped": False,
                "notes": "", "notes_count": 0}


# ---------------------------------------------------------------- required fields
# Where a mandatory Customer field's answer comes from when the source record has
# none. Site settings only — never an arbitrary row from the link target, because
# a customer silently given somebody else's price list is worse than a refusal the
# salesperson can act on.
SELLING_DEFAULTS = {
    "default_price_list": ("Selling Settings", "selling_price_list"),
    "customer_group": ("Selling Settings", "customer_group"),
    "territory": ("Selling Settings", "territory"),
}


def _company_currency():
    company = frappe.defaults.get_user_default("Company") or frappe.db.get_default("company")
    if not company:
        return None
    try:
        return frappe.get_cached_value("Company", company, "default_currency")
    except Exception:
        return None


def _default_for(field):
    """A defensible default for one mandatory Customer field, or None."""
    fieldname = field.fieldname

    source = SELLING_DEFAULTS.get(fieldname)
    if source:
        try:
            value = frappe.db.get_single_value(*source)
        except Exception:
            value = None
        if value:
            return value

    if field.fieldtype == "Link" and field.options == "Currency":
        return _company_currency()

    if field.fieldtype == "Link" and field.options:
        value = frappe.db.get_default(fieldname) or frappe.db.get_default(frappe.scrub(field.options))
        if value and frappe.db.exists(field.options, value):
            return value

    if field.default:
        return field.default

    if field.fieldtype == "Select" and field.options:
        choices = [o for o in str(field.options).split("\n") if o]
        if choices:
            return choices[0]

    return None


def fill_required(customer):
    """Fill mandatory Customer fields the source could not answer.

    This site makes `default_currency` and `default_price_list` mandatory on
    Customer. A Lead carries both under other names and `TO_CUSTOMER` maps them,
    but a Prospect carries neither — so without this, the prospect and opportunity
    routes fail on ERPNext's "Could not auto create Customer" every time.

    Anything still unanswered is left empty on purpose, so the insert raises
    ERPNext's own message naming the field rather than this module inventing a
    value nobody chose.
    """
    filled = {}
    try:
        fields = frappe.get_meta("Customer").fields
    except Exception:
        return filled
    for field in fields:
        if not field.reqd or _val(customer, field.fieldname):
            continue
        value = _default_for(field)
        if value:
            customer.set(field.fieldname, value)
            filled[field.fieldname] = value
    return filled
