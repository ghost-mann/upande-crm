"""Price catalogues shared with buyers by link (CRM side).

See docs/superpowers/specs/2026-10-25-crm-catalogues-design.md. The buyer's
side — the guest page and its submissions — is api/catalogue_public.py; the
Excel import is api/catalogue_import.py.

Reads follow the rest of the CRM and degrade to empty past the role gate. Writes
throw. Any CRM user may build a catalogue; only its owner and CRM managers may
change it afterwards. That rule lives here rather than in DocPerms because the
CRM roles' permissions are granted per site by `setup.ensure_crm_role_permissions`.
"""

import json

import frappe
from frappe import _
from frappe.query_builder.functions import Count
from frappe.utils import cint, get_url

from upande_crm.api.crm import _guard, _has
from upande_crm.modules import requires_module

DOCTYPE = "CRM Catalogue"
LINK = "CRM Catalogue Link"
INTEREST = "CRM Catalogue Interest"
MANAGER_ROLES = {"System Manager", "Sales Manager", "CRM Manager"}
STATUSES = ("Draft", "Live", "Closed")
EDITABLE = {"title", "company", "status", "valid_from", "valid_to", "currencies", "volume_tier_qty", "terms"}
LINE_FIELDS = ("item", "grade", "box_type", "color", "vbn", "pack_qty", "bunch", "weight", "info_url", "prices")
ROW_FIELDS = ["name", "title", "company", "status", "valid_from", "valid_to", "currencies", "owner", "views",
              "public_token", "modified"]


def catalogue_url(token):
    return get_url(f"/catalogue/{token}")


def is_manager(user=None):
    return bool(set(frappe.get_roles(user or frappe.session.user)) & MANAGER_ROLES)


def can_edit(doc):
    return doc.owner == frappe.session.user or is_manager()


def catalogue_has_permission(doc, ptype=None, user=None, debug=False):
    """has_permission hook: anyone with read may read; only the owner and sales
    managers may change a catalogue — through desk and REST too, not only the
    CRM's endpoints."""
    user = user or frappe.session.user
    if ptype in (None, "read", "select", "print", "email", "report", "export", "share"):
        return True
    return doc.owner == user or is_manager(user)


def _check_edit(doc):
    if not can_edit(doc):
        frappe.throw(_("Only the catalogue's owner or a sales manager can change it."), frappe.PermissionError)


def _available():
    return _has(DOCTYPE) and frappe.has_permission(DOCTYPE, "read")


def _counts(doctype, names, where=None):
    """{catalogue: count} for `doctype` rows pointing at `names`."""
    if not names:
        return {}
    t = frappe.qb.DocType(doctype)
    q = (frappe.qb.from_(t).select(t.catalogue, Count("*")).where(t.catalogue.isin(names))
         .groupby(t.catalogue))
    if where is not None:
        q = q.where(where(t))
    return dict(q.run())


def _serialise(doc):
    out = {f: doc.get(f) for f in ROW_FIELDS + ["volume_tier_qty", "terms"]}
    for k in ("valid_from", "valid_to", "modified"):
        out[k] = str(out[k]) if out.get(k) else None
    out["lines"] = []
    for line in doc.lines or []:
        row = {f: line.get(f) for f in LINE_FIELDS}
        row["name"] = line.name
        row["item_name"] = line.item_name
        row["prices"] = json.loads(line.prices) if isinstance(line.prices, str) and line.prices else (line.prices or {})
        out["lines"].append(row)
    out["can_edit"] = can_edit(doc)
    return out


@frappe.whitelist()
@requires_module("cat")
def crm_catalogues():
    """Every catalogue the user can read, with how far each has travelled."""
    _guard()
    if not _available():
        return {"rows": [], "available": False}
    rows = frappe.get_list(DOCTYPE, fields=ROW_FIELDS, order_by="modified desc", limit=500)
    names = [r.name for r in rows]
    links = _counts(LINK, names)
    opened = _counts(LINK, names, lambda t: t.open_count > 0)
    interests = _counts(INTEREST, names)
    lines = {}
    if names:
        ln = frappe.qb.DocType("CRM Catalogue Line")
        lines = dict(frappe.qb.from_(ln).select(ln.parent, Count("*"))
                     .where((ln.parent.isin(names)) & (ln.parenttype == DOCTYPE)).groupby(ln.parent).run())
    me, manager = frappe.session.user, is_manager()
    for r in rows:
        r["links"] = links.get(r.name, 0)
        r["opened"] = opened.get(r.name, 0)
        r["interests"] = interests.get(r.name, 0)
        r["lines"] = lines.get(r.name, 0)
        r["public_url"] = catalogue_url(r.public_token)
        r["can_edit"] = manager or r.owner == me
        for k in ("valid_from", "valid_to", "modified"):
            r[k] = str(r[k]) if r.get(k) else None
    return {"rows": rows, "available": True}


@frappe.whitelist()
@requires_module("cat")
def crm_catalogue_get(name):
    _guard()
    frappe.has_permission(DOCTYPE, "read", name, throw=True)
    doc = frappe.get_doc(DOCTYPE, name)
    return {"catalogue": _serialise(doc), "public_url": catalogue_url(doc.public_token)}


@frappe.whitelist(methods=["POST"])
@requires_module("cat")
def crm_catalogue_save(catalogue=None):
    """Create a catalogue, or update one when `name` is given. `lines`, when
    present, replaces the catalogue's lines wholesale."""
    _guard()
    payload = json.loads(catalogue) if isinstance(catalogue, str) else (catalogue or {})
    if not isinstance(payload, dict):
        frappe.throw(_("Malformed catalogue"))
    name = payload.get("name")
    if name:
        doc = frappe.get_doc(DOCTYPE, name)
        _check_edit(doc)
    else:
        doc = frappe.new_doc(DOCTYPE)
    doc.update({k: v for k, v in payload.items() if k in EDITABLE})
    if "lines" in payload:
        # Rows that come back with their own `name` keep it: a buyer with the
        # page open submits against line names, so re-keying every line on save
        # would make their submission fail. A name from another catalogue is
        # ignored and the row is added as new.
        existing = {l.name: l for l in doc.lines or []} if name else {}
        rows = []
        for line in payload.get("lines") or []:
            values = {k: line.get(k) for k in LINE_FIELDS if k in line}
            if isinstance(values.get("prices"), dict):
                values["prices"] = json.dumps(values["prices"])
            row = existing.pop(line.get("name"), None)
            if row:
                row.update(values)
                rows.append(row)
            else:
                rows.append(values)
        doc.set("lines", rows)
    # Ownership is enforced above; DocPerms for the CRM roles vary by site.
    doc.save(ignore_permissions=True) if name else doc.insert(ignore_permissions=True)
    return {"catalogue": _serialise(doc), "public_url": catalogue_url(doc.public_token)}


@frappe.whitelist(methods=["POST"])
@requires_module("cat")
def crm_catalogue_status(name, status):
    _guard()
    if status not in STATUSES:
        frappe.throw(_("Unknown status {0}").format(status), frappe.ValidationError)
    doc = frappe.get_doc(DOCTYPE, name)
    _check_edit(doc)
    doc.status = status
    doc.save(ignore_permissions=True)
    return {"status": doc.status}


@frappe.whitelist(methods=["POST"])
@requires_module("cat")
def crm_catalogue_preview(name, template=None):
    """The buyer's page payload for any catalogue the user can read, whatever
    its status or dates, optionally with an unsaved template from the editor.
    Records nothing."""
    from upande_crm.api.catalogue_display import build_display
    from upande_crm.catalogue_templates import DEFAULT_TEMPLATE, TEMPLATE

    _guard()
    frappe.has_permission(DOCTYPE, "read", name, throw=True)
    doc = frappe.get_doc(DOCTYPE, name)
    if template:
        data = json.loads(template) if isinstance(template, str) else template
        if not isinstance(data, dict):
            frappe.throw(_("Malformed template"))
        tpl = frappe.get_doc({**{k: v for k, v in data.items() if k not in ("name", "creation", "modified")},
                              "doctype": TEMPLATE})
        tpl.run_method("validate")
    else:
        tpl = frappe.get_doc(TEMPLATE, doc.template or DEFAULT_TEMPLATE)
    return build_display(doc, tpl, preview=True)


@frappe.whitelist(methods=["POST"])
@requires_module("cat")
def crm_catalogue_duplicate(name):
    """A Draft copy with its own link; the copy belongs to whoever made it."""
    _guard()
    frappe.has_permission(DOCTYPE, "read", name, throw=True)
    new = frappe.copy_doc(frappe.get_doc(DOCTYPE, name))
    new.status = "Draft"
    new.title = _("{0} (copy)").format(new.title)
    new.insert(ignore_permissions=True)
    return {"name": new.name}


# ---------------------------------------------------------------- sharing
CHANNELS = ("Email", "WhatsApp", "Copied")


def _party_contact(party_type, party):
    """(email, phone) for a Lead or Customer: its own fields, else its contact's."""
    if party_type == "Lead":
        row = frappe.db.get_value("Lead", party, ["email_id", "mobile_no", "phone"], as_dict=True) or {}
        email, phone = row.get("email_id"), row.get("mobile_no") or row.get("phone")
    else:
        row = frappe.db.get_value("Customer", party, ["email_id", "mobile_no"], as_dict=True) or {}
        email, phone = row.get("email_id"), row.get("mobile_no")
    if not (email and phone):
        contacts = frappe.db.sql(
            """select c.email_id, coalesce(nullif(c.mobile_no, ''), c.phone)
               from `tabContact` c join `tabDynamic Link` dl on dl.parent = c.name and dl.parenttype = 'Contact'
               where dl.link_doctype = %s and dl.link_name = %s
               order by c.is_primary_contact desc, c.modified desc limit 1""", (party_type, party))
        if contacts:
            email, phone = email or contacts[0][0], phone or contacts[0][1]
    return email or None, phone or None


def _party_name(party_type, party):
    field = "lead_name" if party_type == "Lead" else "customer_name"
    return frappe.db.get_value(party_type, party, field) or party


def _options(doc, party_type, party):
    from upande_crm.api import whatsapp as wa
    from upande_crm.api.settings import get_settings
    from upande_crm.modules import is_enabled

    email, phone = _party_contact(party_type, party)
    reason = {}
    can_email = bool(is_enabled("mail") and email)
    if not can_email:
        reason["email"] = _("Mail is switched off in CRM Settings.") if not is_enabled("mail") else \
            _("No email address on record.")
    mode = None
    if not (is_enabled("wa") and wa._available()):
        reason["whatsapp"] = _("WhatsApp is not set up on this site.")
    elif not phone:
        reason["whatsapp"] = _("No phone number on record.")
    elif wa._window_open(wa._last_inbound_at(wa._norm(phone))):
        mode = "text"
    elif get_settings().get("catalogue_whatsapp_template"):
        # The link travels as the template's first body variable; a template
        # without one would arrive without the link and still report "sent".
        if wa.template_body_params(get_settings().get("catalogue_whatsapp_template")) == 1:
            mode = "template"
        else:
            reason["whatsapp"] = _("The catalogue WhatsApp template must have exactly one body variable "
                                   "for the link. Pick another in CRM Settings → Catalogues.")
    else:
        reason["whatsapp"] = _("They haven't messaged in 24 hours, and no catalogue template is set in CRM Settings.")
    return {"email": email, "phone": phone,
            "channels": {"email": can_email, "whatsapp": bool(mode), "whatsapp_mode": mode, "copy": True},
            "reason": reason}


def _check_party(party_type, party):
    if party_type not in ("Lead", "Customer"):
        frappe.throw(_("A catalogue can be sent to a Lead or a Customer."))
    frappe.has_permission(party_type, "read", party, throw=True)


@frappe.whitelist()
@requires_module("cat")
def crm_catalogue_share_options(name, party_type, party):
    """Which channels can reach this party, and why not when one can't."""
    _guard()
    frappe.has_permission(DOCTYPE, "read", name, throw=True)
    _check_party(party_type, party)
    return _options(frappe.get_doc(DOCTYPE, name), party_type, party)


def _fill(template, **values):
    for k, v in values.items():
        template = template.replace("{" + k + "}", str(v or ""))
    return template


@frappe.whitelist(methods=["POST"])
@requires_module("cat")
def crm_catalogue_share(name, party_type, party, channel, subject=None, body=None):
    """Make (or reuse) the party's personal link and send it by `channel`."""
    from upande_crm.api import whatsapp as wa
    from upande_crm.api.crm import crm_send_email
    from upande_crm.api.settings import get_settings

    _guard()
    if channel not in CHANNELS:
        frappe.throw(_("Unknown channel {0}").format(channel))
    frappe.has_permission(DOCTYPE, "read", name, throw=True)
    _check_party(party_type, party)
    doc = frappe.get_doc(DOCTYPE, name)
    if doc.status != "Live":
        frappe.throw(_("Put the catalogue live before sending it."))
    opts = _options(doc, party_type, party)
    if channel == "Email" and not opts["channels"]["email"]:
        exc = frappe.PermissionError if "switched off" in opts["reason"].get("email", "") else frappe.ValidationError
        frappe.throw(opts["reason"]["email"], exc)
    if channel == "WhatsApp" and not opts["channels"]["whatsapp"]:
        frappe.throw(opts["reason"]["whatsapp"])

    existing = frappe.db.get_value(LINK, {"catalogue": name, "party_type": party_type, "party": party,
                                          "sent_via": channel}, "name")
    link = frappe.get_doc(LINK, existing) if existing else frappe.get_doc({
        "doctype": LINK, "catalogue": name, "party_type": party_type, "party": party, "sent_via": channel})
    link.update({"contact_email": opts["email"], "contact_phone": opts["phone"],
                 "sent_by": frappe.session.user, "sent_on": frappe.utils.now_datetime()})
    link.save(ignore_permissions=True) if existing else link.insert(ignore_permissions=True)
    url = catalogue_url(link.token)

    s = get_settings()
    values = {"link": url, "name": _party_name(party_type, party), "catalogue": doc.title}
    sent = False
    if channel == "Email":
        subject = _fill(subject or s.get("catalogue_email_subject") or "{catalogue}", **values)
        text = _fill(body or s.get("catalogue_email_body") or "{link}", **values)
        if url not in text:
            text += "\n\n" + url
        html = "".join(f"<p>{frappe.utils.escape_html(p).replace(chr(10), '<br>')}</p>" for p in text.split("\n\n"))
        html = html.replace(frappe.utils.escape_html(url), f'<a href="{url}">{url}</a>')
        crm_send_email(opts["email"], subject=subject, content=html, reference_doctype=party_type,
                       reference_name=party)
        sent = True
    elif channel == "WhatsApp":
        if opts["channels"]["whatsapp_mode"] == "text":
            text = _fill(body or s.get("catalogue_email_body") or "{link}", **values)
            wa.crm_whatsapp_send(to=opts["phone"], message=text if url in text else f"{text}\n{url}",
                                 reference_doctype=party_type, reference_name=party)
        else:
            wa.crm_whatsapp_send_template(to=opts["phone"], template=s.get("catalogue_whatsapp_template"),
                                          reference_doctype=party_type, reference_name=party,
                                          body_params=json.dumps([url]))
        sent = True
    return {"link": link.name, "url": url, "sent": sent}


@frappe.whitelist()
@requires_module("cat")
def crm_catalogue_links(name):
    """Personal links sent for a catalogue, with who opened them."""
    from upande_crm.api.visits import readable_parties

    _guard()
    frappe.has_permission(DOCTYPE, "read", name, throw=True)
    rows = frappe.get_all(LINK, filters={"catalogue": name},
                          fields=["name", "party_type", "party", "contact_email", "contact_phone", "sent_via",
                                  "sent_by", "sent_on", "first_opened_on", "last_opened_on", "open_count"],
                          order_by="sent_on desc", limit=500)
    rows = readable_parties(rows)
    for r in rows:
        r["party_name"] = _party_name(r.party_type, r.party)
        for k in ("sent_on", "first_opened_on", "last_opened_on"):
            r[k] = str(r[k]) if r.get(k) else None
    return {"rows": rows}


# ---------------------------------------------------------------- interests
INTEREST_STATUSES = ("New", "Contacted", "Converted", "Dropped")
INTEREST_FIELDS = ["name", "catalogue", "via_link", "party_type", "party", "status", "opportunity", "contact_name",
                   "company_name", "email", "phone", "country", "currency", "creation"]


def _owners(catalogues):
    return dict(frappe.get_all(DOCTYPE, filters={"name": ["in", list(catalogues) or [""]]},
                               fields=["name", "owner"], as_list=True))


def _visible(rows):
    """Interests the user may see: whoever can read the party, plus the
    catalogue's owner and sales managers (spec: user's decision)."""
    from upande_crm.api.visits import readable_parties

    if is_manager():
        return rows
    owners = _owners({r["catalogue"] for r in rows})
    me = frappe.session.user
    readable = {r["name"] for r in readable_parties(rows)}
    return [r for r in rows if r["name"] in readable or owners.get(r["catalogue"]) == me]


def _readable_by(row, user):
    if is_manager(user):
        return True
    if frappe.db.get_value(DOCTYPE, row.get("catalogue"), "owner") == user:
        return True
    pt, party = row.get("party_type"), row.get("party")
    return bool(pt and party and frappe.has_permission(pt, "read", party, user=user))


def interest_has_permission(doc, ptype=None, user=None, debug=False):
    """has_permission hook for CRM Catalogue Interest and CRM Catalogue Link:
    the same rule as the CRM list (spec: user's decision)."""
    return _readable_by(doc, user or frappe.session.user)


def interest_query_conditions(user=None, doctype=INTEREST):
    """permission_query_conditions for interests and links. User Permissions
    skip Dynamic Links, so a restricted user's readable parties are listed
    explicitly; an unrestricted user is limited only by their own reads."""
    user = user or frappe.session.user
    if user == "Administrator" or is_manager(user):
        return ""
    table = f"`tab{doctype}`"
    esc = frappe.db.escape
    parts = [f"{table}.catalogue in (select name from `tab{DOCTYPE}` where owner = {esc(user)})"]
    restricted = bool(frappe.permissions.get_user_permissions(user))
    for pt in ("Customer", "Lead"):
        if not frappe.has_permission(pt, "read", user=user):
            continue
        if not restricted:
            parts.append(f"{table}.party_type = {esc(pt)}")
            continue
        names = frappe.get_list(pt, pluck="name", limit=0, user=user)
        if names:
            parts.append(f"({table}.party_type = {esc(pt)} and {table}.party in ({', '.join(esc(n) for n in names)}))")
    return "(" + " or ".join(parts) + ")"


def link_query_conditions(user=None):
    return interest_query_conditions(user, LINK)


def _interest_doc(name):
    doc = frappe.get_doc(INTEREST, name)
    if not _visible([{"name": doc.name, "catalogue": doc.catalogue, "party_type": doc.party_type,
                      "party": doc.party}]):
        frappe.throw(_("Not permitted to see this interest."), frappe.PermissionError)
    return doc


@frappe.whitelist()
@requires_module("cat")
def crm_catalogue_interests(catalogue=None, status=None, party_type=None, party=None):
    _guard()
    if not _has(INTEREST):
        return {"rows": []}
    filters = {k: v for k, v in {"catalogue": catalogue, "status": status, "party_type": party_type,
                                 "party": party}.items() if v}
    rows = _visible(frappe.get_all(INTEREST, filters=filters, fields=INTEREST_FIELDS, order_by="creation desc",
                                   limit=1000))
    if not rows:
        return {"rows": []}
    it = frappe.qb.DocType("CRM Catalogue Interest Item")
    from frappe.query_builder.functions import Max, Sum

    totals = {r[0]: r[1:] for r in (
        frappe.qb.from_(it).select(it.parent, Count("*"), Sum(it.qty),
                                   Max((it.frequency == "Weekly")))
        .where(it.parent.isin([r["name"] for r in rows]) & (it.parenttype == INTEREST))
        .groupby(it.parent).run())}
    titles = dict(frappe.get_all(DOCTYPE, filters={"name": ["in", list({r["catalogue"] for r in rows})]},
                                 fields=["name", "title"], as_list=True))
    for r in rows:
        n, boxes, weekly = totals.get(r["name"], (0, 0, 0))
        r.update({"lines": n, "boxes": boxes or 0, "weekly": bool(weekly), "catalogue_title": titles.get(r["catalogue"]),
                  "creation": str(r["creation"])})
        r["party_name"] = _party_name(r["party_type"], r["party"]) if r.get("party") else None
    return {"rows": rows}


@frappe.whitelist()
@requires_module("cat")
def crm_catalogue_interest_get(name):
    _guard()
    doc = _interest_doc(name)
    out = {f: doc.get(f) for f in INTEREST_FIELDS + ["message"]}
    out["creation"] = str(doc.creation)
    out["catalogue_title"] = frappe.db.get_value(DOCTYPE, doc.catalogue, "title")
    out["party_name"] = _party_name(doc.party_type, doc.party) if doc.party else None
    out["items"] = [{f: i.get(f) for f in ("item", "item_name", "grade", "box_type", "pack_qty", "qty", "frequency",
                                           "price", "tier_price", "priced")} for i in doc.items]
    return {"interest": out}


@frappe.whitelist(methods=["POST"])
@requires_module("cat")
def crm_catalogue_interest_status(name, status):
    _guard()
    if status not in INTEREST_STATUSES:
        frappe.throw(_("Unknown status {0}").format(status), frappe.ValidationError)
    doc = _interest_doc(name)
    doc.status = status
    doc.save(ignore_permissions=True)
    return {"status": doc.status}


def _rate(item, tier_qty):
    """The tier price when this line's boxes exceed the catalogue's threshold
    (judged per line: user's decision), else the standard price."""
    if not item.priced:
        return 0
    if tier_qty and item.qty > tier_qty and item.tier_price:
        return item.tier_price
    return item.price


@frappe.whitelist(methods=["POST"])
@requires_module("cat")
def crm_catalogue_make_opportunity(name):
    """An Opportunity for the interest's party with its lines. Weekly lines go
    across as per-week quantities, marked Weekly, for sales to adjust."""
    _guard()
    doc = _interest_doc(name)
    if doc.opportunity and frappe.db.exists("Opportunity", doc.opportunity):
        return {"opportunity": doc.opportunity}
    if not doc.party:
        frappe.throw(_("This interest has no lead or customer to make an opportunity for."))
    cat = frappe.get_doc(DOCTYPE, doc.catalogue)
    tier_qty = frappe.utils.cint(cat.volume_tier_qty)
    from upande_crm.catalogue_templates import DEFAULT_TEMPLATE, TEMPLATE

    tpl = frappe.get_cached_doc(TEMPLATE, cat.template or DEFAULT_TEMPLATE)
    recurring = {f.label for f in tpl.frequencies or [] if cint(f.recurring)}
    items = []
    for i in doc.items:
        units = i.qty * i.pack_qty if i.pack_qty else i.qty
        items.append({"item_code": i.item, "qty": units, "rate": _rate(i, tier_qty),
                      "description": f"{i.item_name or i.item} — {i.grade or ''} · {i.box_type or ''} · "
                                     f"{frappe.utils.fmt_money(i.qty, precision=0)} {tpl.pack_label_plural or 'boxes'} {i.frequency}"
                                     + (" — recurring" if i.frequency in recurring else "")})
    opp = frappe.get_doc({"doctype": "Opportunity", "opportunity_from": doc.party_type, "party_name": doc.party,
                          "company": cat.company, "currency": doc.currency, "items": items,
                          "contact_email": doc.email or None})
    opp.flags.ignore_mandatory = True
    opp.insert()
    opp.add_comment("Info", _("Made from catalogue interest {0} ({1}).").format(doc.name, cat.title))
    doc.db_set({"opportunity": opp.name, "status": "Converted"})
    return {"opportunity": opp.name}
