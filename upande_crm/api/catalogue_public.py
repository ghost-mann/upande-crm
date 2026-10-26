"""The buyer's side of catalogues: guest endpoints behind a link's token.

See docs/superpowers/specs/2026-10-25-crm-catalogues-design.md. A token is
either a catalogue's `public_token` or a personal link's `token`; every call
resolves it again and re-checks that the offer is open, so a closed catalogue
stops taking interest the moment it is closed.

What a submission may create is deliberately small: at most a Lead, never a
User, Customer or Contact. Existing Leads and Customers are never edited by what
a buyer typed — only a comment is added to their timeline.

Writes here run as Guest with ignore_permissions; the token is the
authorisation, and nothing outside the token's catalogue is read or written.
"""

import json
from urllib.parse import quote

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, escape_html, flt, now_datetime, strip_html

from upande_crm.api.whatsapp import _suffix

DOCTYPE = "CRM Catalogue"
LINK = "CRM Catalogue Link"
INTEREST = "CRM Catalogue Interest"
UTM_SOURCE = "Catalogue"
MAX_LEN = {"name": 140, "company": 140, "email": 140, "phone": 40, "country": 80, "message": 2000}


def resolve_token(token):
    """(catalogue, link or None) for a token; DoesNotExistError when unknown."""
    token = (token or "").strip()
    if token and len(token) <= 64:
        name = frappe.db.get_value(DOCTYPE, {"public_token": token}, "name")
        if name:
            return frappe.get_doc(DOCTYPE, name), None
        link = frappe.db.get_value(LINK, {"token": token}, "name")
        if link:
            link = frappe.get_doc(LINK, link)
            return frappe.get_doc(DOCTYPE, link.catalogue), link
    raise frappe.DoesNotExistError(_("This offer isn't available."))


def _template(doc):
    from upande_crm.catalogue_templates import DEFAULT_TEMPLATE, TEMPLATE

    return frappe.get_doc(TEMPLATE, doc.template or DEFAULT_TEMPLATE)


def _party_details(party_type, party):
    if party_type == "Lead":
        d = frappe.db.get_value("Lead", party, ["lead_name", "company_name", "email_id", "mobile_no", "country"],
                                as_dict=True) or {}
        return {"name": d.get("lead_name"), "company": d.get("company_name"), "email": d.get("email_id"),
                "phone": d.get("mobile_no"), "country": d.get("country")}
    d = frappe.db.get_value("Customer", party, ["customer_name", "email_id", "mobile_no"], as_dict=True) or {}
    return {"name": "", "company": d.get("customer_name"), "email": d.get("email_id"),
            "phone": d.get("mobile_no"), "country": ""}


def _record_open(doc, link):
    if link:
        now = now_datetime()
        frappe.db.set_value(LINK, link.name, {"open_count": cint(link.open_count) + 1, "last_opened_on": now,
                                              "first_opened_on": link.first_opened_on or now},
                            update_modified=False)
    else:
        frappe.db.sql(f"update `tab{DOCTYPE}` set views = ifnull(views, 0) + 1 where name = %s", doc.name)


# POST only: it records the open, and Frappe does not commit a GET request's writes.
@frappe.whitelist(allow_guest=True, methods=["POST"])
def catalogue_view(token):
    """The magazine payload for a link (api/catalogue_display.build_display),
    plus who the link was sent to. A Draft shows nothing and records nothing."""
    from upande_crm.api.catalogue_display import build_display

    doc, link = resolve_token(token)
    out = build_display(doc, _template(doc))
    out["personal"] = bool(link)
    if doc.status == "Draft":
        out["groups"], out["mixes"] = [], []
    if link:
        details = _party_details(link.party_type, link.party)
        out["prefill"] = {**details, "email": link.contact_email or details.get("email"),
                          "phone": link.contact_phone or details.get("phone")}
    if doc.status != "Draft":
        _record_open(doc, link)
    return out


# ---------------------------------------------------------------- matching
def _clean_email(email):
    return (email or "").strip().lower()


def _parties_by_email(email):
    rows = frappe.db.sql(
        """select dl.link_doctype, dl.link_name
           from `tabContact Email` ce
           join `tabDynamic Link` dl on dl.parent = ce.parent and dl.parenttype = 'Contact'
           where lower(trim(ce.email_id)) = %s and dl.link_doctype in ('Customer', 'Lead')""", email)
    rows += frappe.db.sql("select 'Lead', name from tabLead where lower(trim(email_id)) = %s", email)
    rows += frappe.db.sql("select 'Customer', name from tabCustomer where lower(trim(email_id)) = %s", email)
    return rows


def _parties_by_phone(phone):
    """(party_type, party) whose number ends in the same digits. Stored numbers
    are compared with their punctuation stripped — "+254 712 345 678" and
    "0712345678" are the same phone."""
    from upande_crm.api.whatsapp import _suffix

    want = _suffix(phone)
    if len(want) < 7:
        return []
    like = f"%{want}"
    digits = "regexp_replace({0}, '[^0-9]', '')"
    found = list(frappe.db.sql(
        f"""select dl.link_doctype, dl.link_name
            from `tabContact Phone` cp
            join `tabDynamic Link` dl on dl.parent = cp.parent and dl.parenttype = 'Contact'
            where dl.link_doctype in ('Customer', 'Lead') and {digits.format('cp.phone')} like %s""", like))
    for dt, cols in (("Customer", ("mobile_no", "phone")), ("Lead", ("mobile_no", "phone"))):
        for col in cols:
            if not frappe.db.has_column(dt, col):
                continue
            found += [(dt, n) for (n,) in frappe.db.sql(
                f"select name from `tab{dt}` where {digits.format(col)} like %s", like)]
    return found


def find_party(email, phone):
    """(party_type, party) for a buyer, or (None, None). A Customer wins over a
    Lead; email is tried before phone."""
    for rows in (_parties_by_email(_clean_email(email)) if _clean_email(email) else [],
                 _parties_by_phone(phone) if phone else []):
        rows = [(dt, n) for dt, n in rows if n]
        for want in ("Customer", "Lead"):
            hit = next((r for r in rows if r[0] == want), None)
            if hit:
                return hit
    return None, None


def _create_lead(doc, c):
    if not frappe.db.exists("UTM Source", UTM_SOURCE):
        frappe.get_doc({"doctype": "UTM Source", "name": UTM_SOURCE, "utm_source": UTM_SOURCE}
                       ).insert(ignore_permissions=True)
    lead = frappe.get_doc({
        "doctype": "Lead", "first_name": c["name"] or c["email"], "company_name": c["company"],
        "email_id": c["email"] or None, "mobile_no": c["phone"] or None,
        "country": c["country"] if c["country"] and frappe.db.exists("Country", c["country"]) else None,
        "utm_source": UTM_SOURCE, "lead_owner": doc.owner,
    })
    # A buyer cannot fill fields a site has made mandatory on Lead (Kaitet has
    # nine); the lead still has to exist for sales to follow up.
    lead.flags.ignore_mandatory = True
    lead.insert(ignore_permissions=True)
    lead.add_comment("Info", _("Came in through the catalogue {0}.").format(doc.title))
    return lead.name


def _contact(raw):
    c = json.loads(raw) if isinstance(raw, str) else (raw or {})
    if not isinstance(c, dict):
        frappe.throw(_("Malformed contact details"))
    out = {k: (str(c.get(k) or "").strip())[:n] for k, n in MAX_LEN.items()}
    out["email"] = _clean_email(out["email"])
    if out["email"] and not frappe.utils.validate_email_address(out["email"]):
        frappe.throw(_("{0} is not a valid email address.").format(escape_html(out["email"])))
    return out


def _wanted_lines(doc, raw, currency):
    picks = json.loads(raw) if isinstance(raw, str) else (raw or [])
    frequencies = _template(doc).frequency_labels()
    by_name = {l.name: l for l in doc.lines}
    # A page opened before the catalogue was re-saved may carry line names that
    # no longer exist; the same item, grade and box type is the same line.
    by_key = {(l.item, l.grade or "", l.box_type or ""): l for l in doc.lines}
    rows = []
    for p in picks if isinstance(picks, list) else []:
        if not isinstance(p, dict):
            frappe.throw(_("Malformed line"))
        line = by_name.get(p.get("line")) or by_key.get((p.get("item"), p.get("grade") or "", p.get("box_type") or ""))
        if not line:
            frappe.throw(_("That line is not in this catalogue."))
        qty = flt(p.get("qty"))
        if qty <= 0:
            continue
        price, tier = doc.price_for(line, currency)
        rows.append({"line_ref": line.name, "item": line.item, "item_name": line.item_name, "grade": line.grade,
                     "box_type": line.box_type, "pack_qty": line.pack_qty, "qty": qty,
                     "frequency": _frequency(p.get("frequency"), frequencies),
                     "price": price or 0, "tier_price": tier or 0, "priced": 1 if price is not None else 0})
    if not rows:
        frappe.throw(_("Pick at least one line."))
    return rows


def _frequency(value, allowed):
    """The template's frequencies decide; none given means the first."""
    if not value:
        return allowed[0]
    if value not in allowed:
        frappe.throw(_("Unknown frequency {0}.").format(escape_html(str(value))))
    return value


def _notify(doc, interest, who):
    subject = _("New interest from {0} — {1}").format(who, doc.title)
    url = frappe.utils.get_url("/customer-relationship-management#cat/" + quote(f"interest:{interest.name}"))
    boxes = sum(flt(i.qty) for i in interest.items)
    body = _("{0} sent interest in {1} line(s), {2} box(es), from {3}.").format(
        escape_html(who), len(interest.items), frappe.utils.fmt_money(boxes, precision=0), escape_html(doc.title))
    frappe.sendmail(recipients=[doc.owner], subject=subject,
                    message=f"<p>{body}</p><p><a href='{url}'>{_('Open it in the CRM')}</a></p>",
                    reference_doctype=INTEREST, reference_name=interest.name)
    frappe.get_doc({"doctype": "Notification Log", "subject": subject, "for_user": doc.owner, "type": "Alert",
                    "document_type": INTEREST, "document_name": interest.name, "from_user": "Administrator"}
                   ).insert(ignore_permissions=True)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=20, seconds=60 * 60)
def catalogue_submit(token, contact, lines, currency=None, website=""):
    doc, link = resolve_token(token)
    if (website or "").strip():
        return {"ok": True}  # honeypot: a person never sees this field
    if not doc.is_open():
        frappe.throw(_("This offer has closed."))
    currency = (currency or "").upper()
    if currency not in doc.currency_list():
        currency = doc.currency_list()[0]
    c = _contact(contact)
    rows = _wanted_lines(doc, lines, currency)

    party_type = party = None
    if link:
        details = _party_details(link.party_type, link.party)
        known = {_clean_email(link.contact_email), _clean_email(details["email"])} - {""}
        phones = {_suffix(link.contact_phone), _suffix(details.get("phone"))} - {""}
        # The link's own buyer: no email typed, the email on record, or — for a
        # party we only know by phone — the same phone number.
        if not c["email"] or c["email"] in known or (c["phone"] and _suffix(c["phone"]) in phones):
            party_type, party = link.party_type, link.party
    if not party:
        if not c["email"]:
            frappe.throw(_("Please give your email address."))
        party_type, party = find_party(c["email"], c["phone"])
    if not party:
        party_type, party = "Lead", _create_lead(doc, c)

    interest = frappe.get_doc({
        "doctype": INTEREST, "catalogue": doc.name, "via_link": link.name if link else None,
        "party_type": party_type, "party": party, "contact_name": c["name"], "company_name": c["company"],
        "email": c["email"], "phone": c["phone"], "country": c["country"], "message": c["message"],
        "currency": currency, "items": rows,
    }).insert(ignore_permissions=True)
    who = c["name"] or c["company"] or c["email"]
    frappe.get_doc(party_type, party).add_comment(
        "Info", _("Sent interest through the catalogue {0}: {1}.").format(doc.title, interest.name))
    _notify(doc, interest, who)
    return {"ok": True}
