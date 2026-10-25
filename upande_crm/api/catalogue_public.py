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

DOCTYPE = "CRM Catalogue"
LINK = "CRM Catalogue Link"
INTEREST = "CRM Catalogue Interest"
FREQUENCIES = ("One-off", "Weekly")
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


def _lines_payload(doc):
    """Lines grouped by Item, in line order, with what the page shows."""
    items = {i.name: i for i in frappe.get_all(
        "Item", filters={"name": ["in", list({l.item for l in doc.lines}) or [""]]},
        fields=["name", "item_name", "image", "description"])}
    groups, order = {}, []
    for line in doc.lines:
        if line.item not in groups:
            it = items.get(line.item) or frappe._dict(item_name=line.item_name or line.item)
            groups[line.item] = {"item": line.item, "item_name": it.item_name, "image": it.image,
                                 "description": strip_html(it.description or "")
                                 if (it.description or "") != (it.item_name or "") else "", "lines": []}
            order.append(line.item)
        groups[line.item]["lines"].append({
            "line": line.name, "grade": line.grade, "box_type": line.box_type, "color": line.color,
            "pack_qty": line.pack_qty, "bunch": line.bunch, "weight": line.weight, "info_url": line.info_url,
            "prices": {c: dict(zip(("price", "tier"), doc.price_for(line, c))) for c in doc.currency_list()},
        })
    return [groups[i] for i in order]


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
    doc, link = resolve_token(token)
    company = frappe.db.get_value("Company", doc.company, ["company_name", "company_logo"], as_dict=True) or {}
    out = {
        "title": doc.title, "company": company.get("company_name") or doc.company,
        "logo": company.get("company_logo"), "terms": doc.terms or "", "currencies": doc.currency_list(),
        "tier_qty": cint(doc.volume_tier_qty) or None, "open": doc.is_open(),
        "valid_to": str(doc.valid_to) if doc.valid_to else None, "personal": bool(link),
        "groups": _lines_payload(doc) if doc.status != "Draft" else [],
    }
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
    from upande_crm.api.whatsapp import _suffix

    want = _suffix(phone)
    if len(want) < 7:
        return []
    tail = want[-4:]
    found = []
    for dt, name, number in frappe.db.sql(
        """select dl.link_doctype, dl.link_name, cp.phone
           from `tabContact Phone` cp
           join `tabDynamic Link` dl on dl.parent = cp.parent and dl.parenttype = 'Contact'
           where dl.link_doctype in ('Customer', 'Lead') and cp.phone like %s""", f"%{tail}"):
        if _suffix(number) == want:
            found.append((dt, name))
    for col in ("mobile_no", "phone"):
        for name, number in frappe.db.sql(f"select name, {col} from tabLead where {col} like %s", f"%{tail}"):
            if _suffix(number) == want:
                found.append(("Lead", name))
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
    by_name = {l.name: l for l in doc.lines}
    rows = []
    for p in picks if isinstance(picks, list) else []:
        line = by_name.get(p.get("line"))
        if not line:
            frappe.throw(_("That line is not in this catalogue."))
        qty = flt(p.get("qty"))
        if qty <= 0:
            continue
        price, tier = doc.price_for(line, currency)
        rows.append({"line_ref": line.name, "item": line.item, "item_name": line.item_name, "grade": line.grade,
                     "box_type": line.box_type, "pack_qty": line.pack_qty, "qty": qty,
                     "frequency": p.get("frequency") if p.get("frequency") in FREQUENCIES else "One-off",
                     "price": price or 0, "tier_price": tier or 0, "priced": 1 if price is not None else 0})
    if not rows:
        frappe.throw(_("Pick at least one line."))
    return rows


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
        known = {_clean_email(link.contact_email), _clean_email(_party_details(link.party_type, link.party)["email"])}
        if not c["email"] or c["email"] in known:
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
