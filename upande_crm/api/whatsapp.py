"""CRM surface over the `frappe_whatsapp` app.

This is a *surface*, not an integration: `frappe_whatsapp` owns the Meta Cloud API
credentials, the inbound webhook, and dispatch. Creating a `WhatsApp Message` with
`type="Outgoing"` triggers its `before_insert` hook, which performs the actual
send — so `.insert()` IS the send. We never call the Graph API here.

Permissions, deliberately: `WhatsApp Message` has exactly one DocPerm, System
Manager. Enforcing document permissions would make this feature useless for the
Sales Users it exists for, so every endpoint role-gates through `_guard()` (CRM
roles) and then reads/writes with `ignore_permissions=True`. This mirrors what
`crm_send_email` already does for Communication. The widening is intentional and
bounded: CRM references are validated against `WA_REF_DOCTYPES`, so a caller
cannot attach a message to an arbitrary record.

Reads degrade to empty. Sends throw — a send that looks successful but never left
the building is the worst outcome this module can produce.
"""

import ast
import json
import re

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime

from upande_crm.api.crm import _guard, _has, _hascol, _range

# What a WhatsApp message may be linked to.
WA_REF_DOCTYPES = {
    "Lead", "Opportunity", "Prospect", "Customer", "Quotation", "Contact", "Sales Order",
}

READ_STATUS = "marked as read"

# Meta only permits free-form text within 24h of the contact's last inbound
# message; outside it, approved templates are the only deliverable option.
WINDOW_HOURS = 24

# Compare the last N digits when matching a phone number to a CRM record. Nine is
# the significant subscriber length for Kenyan numbers (254 7XX XXX XXX), so this
# is robust to country codes, leading zeros, and punctuation without being short
# enough for unrelated numbers to collide.
SUFFIX = 9


def _norm(number):
    """Digits only. `frappe_whatsapp.format_number` only strips a leading '+',
    which is not enough: WhatsApp Profiles on this site holds '254-727273549'."""
    return re.sub(r"\D", "", str(number or ""))


def _suffix(number):
    n = _norm(number)
    return n[-SUFFIX:] if len(n) >= SUFFIX else n


def _available():
    return _has("WhatsApp Message")


# ---------------------------------------------------------------- CRM matching
def _candidate_index():
    """Map phone-suffix -> CRM record, built in a bounded number of queries.

    Resolving each conversation with its own lookups would mean hundreds of
    queries for a 60-row list. Cheapest/most-specific sources are inserted last
    so they win on collision (Lead.whatsapp_no beats a generic Customer number).
    """
    idx = {}

    def add(rows, doctype, label_key, *phone_keys):
        for r in rows:
            for pk in phone_keys:
                s = _suffix(r.get(pk))
                if s:
                    idx[s] = {
                        "doctype": doctype,
                        "name": r.get("name"),
                        "label": r.get(label_key) or r.get("name"),
                    }

    try:
        if _has("Customer") and _hascol("Customer", "mobile_no"):
            add(frappe.get_all("Customer", fields=["name", "customer_name", "mobile_no"],
                               filters={"mobile_no": ["!=", ""]}, limit=0),
                "Customer", "customer_name", "mobile_no")
    except Exception:
        pass

    try:
        if _has("Contact"):
            cfields = ["name", "first_name"]
            for f in ("mobile_no", "phone"):
                if _hascol("Contact", f):
                    cfields.append(f)
            contacts = frappe.get_all("Contact", fields=cfields, limit=0)
            add(contacts, "Contact", "first_name", "mobile_no", "phone")

            # Contact Phone child rows, mapped up to their parent Contact.
            if _has("Contact Phone"):
                names = {c["name"]: c for c in contacts}
                for row in frappe.get_all("Contact Phone",
                                          fields=["parent", "phone"], limit=0):
                    s = _suffix(row.phone)
                    if s and row.parent in names:
                        idx[s] = {
                            "doctype": "Contact",
                            "name": row.parent,
                            "label": names[row.parent].get("first_name") or row.parent,
                        }
    except Exception:
        pass

    # Leads last: most specific, since Lead carries a dedicated whatsapp_no here.
    try:
        if _has("Lead"):
            lfields = ["name", "lead_name"]
            for f in ("whatsapp_no", "mobile_no", "phone"):
                if _hascol("Lead", f):
                    lfields.append(f)
            add(frappe.get_all("Lead", fields=lfields, limit=0),
                "Lead", "lead_name", "phone", "mobile_no", "whatsapp_no")
    except Exception:
        pass

    return idx


def _profile_names():
    if not _has("WhatsApp Profiles"):
        return {}
    try:
        return {
            _suffix(r.number): r.profile_name
            for r in frappe.get_all("WhatsApp Profiles",
                                    fields=["number", "profile_name"], limit=0)
            if r.profile_name
        }
    except Exception:
        return {}


@frappe.whitelist()
def crm_whatsapp_match(party):
    """Resolve one phone number to a CRM record, or None."""
    _guard()
    return _candidate_index().get(_suffix(party))


# ---------------------------------------------------------------- conversations
def _window_open(last_inbound_at):
    if not last_inbound_at:
        return False
    try:
        return get_datetime(last_inbound_at) >= add_to_date(now_datetime(), hours=-WINDOW_HOURS)
    except Exception:
        return False


@frappe.whitelist()
def crm_whatsapp_conversations(search="", limit=60):
    """One row per counterparty, newest activity first."""
    _guard()
    if not _available():
        return {"rows": [], "unread_total": 0, "available": False}

    limit = max(1, min(int(limit or 60), 200))
    conds, params = ["coalesce(nullif(`to`, ''), `from`) is not null"], {}
    if search:
        conds.append("(coalesce(nullif(`to`,''),`from`) like %(q)s or profile_name like %(q)s"
                     " or message like %(q)s)")
        params["q"] = f"%{search}%"
    where = " and ".join(conds)

    try:
        rows = frappe.db.sql(
            f"""select coalesce(nullif(`to`, ''), `from`) party,
                       count(*) total,
                       max(creation) last_at,
                       sum(case when type='Incoming' and coalesce(status,'') <> %(read)s
                                then 1 else 0 end) unread,
                       max(case when type='Incoming' then creation else null end) last_inbound_at
                from `tabWhatsApp Message`
                where {where}
                group by party
                order by last_at desc
                limit {limit}""",
            {**params, "read": READ_STATUS},
            as_dict=True,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "crm_whatsapp_conversations failed")
        return {"rows": [], "unread_total": 0, "available": True}

    # Latest message per party, fetched in one query rather than per row.
    parties = [r.party for r in rows if r.party]
    latest = {}
    if parties:
        try:
            for m in frappe.db.sql(
                """select coalesce(nullif(`to`, ''), `from`) party, message, type,
                          status, creation, profile_name, message_type, template,
                          template_parameters
                   from `tabWhatsApp Message`
                   where coalesce(nullif(`to`, ''), `from`) in %(p)s
                   order by creation asc""",
                {"p": parties}, as_dict=True,
            ):
                latest[m.party] = m
        except Exception:
            latest = {}

    idx = _candidate_index()
    profiles = _profile_names()
    out = []
    for r in rows:
        m = latest.get(r.party) or {}
        s = _suffix(r.party)
        out.append({
            "party": r.party,
            "display_name": (m.get("profile_name") or profiles.get(s)
                             or (idx.get(s) or {}).get("label") or r.party),
            "last_message": _plain(_message_text(m) if m else None),
            "last_at": r.last_at,
            "last_direction": m.get("type") or "Incoming",
            "last_status": m.get("status"),
            "total": int(r.total or 0),
            "unread": int(r.unread or 0),
            "window_open": _window_open(r.last_inbound_at),
            "link": idx.get(s),
        })

    return {
        "rows": out,
        "unread_total": sum(x["unread"] for x in out),
        "available": True,
    }


def _plain(html, limit=140):
    t = re.sub(r"<[^>]+>", " ", str(html or ""))
    t = (t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
          .replace("&nbsp;", " "))
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limit]


# ---------------------------------------------------------------- template text
# For template sends, `frappe_whatsapp` does not store what was said — it stores
# the Meta request payload as a *Python repr*:
#
#   whatsapp_notification.py:  "message": str(data['template'])
#
# So `message` reads `{'name': 'visitor_host_alert_v2', 'components': [...]}`, which
# is what a thread renders if taken at face value. The readable text is recoverable:
# `WhatsApp Templates.template` holds the body with `{{1}}` placeholders and the row
# carries the substitutions in `template_parameters` (with the payload itself as a
# fallback when that column is empty). We rebuild here rather than patching
# `frappe_whatsapp` — it owns that data, and its historic rows would stay broken.

PLACEHOLDER = re.compile(r"\{\{\s*(\d+)\s*\}\}")


def _looks_like_payload(text):
    t = str(text or "").strip()
    return t.startswith("{") and ("'components'" in t or '"components"' in t)


def _payload_params(text):
    """Body-component parameter texts, in order. Never raises.

    Only the `body` component: the button component carries a URL suffix
    (`APMT-Gilbert%20kiprop-2265780`), which is routing, not conversation.
    """
    t = str(text or "").strip()
    if not t.startswith("{"):
        return []
    data = None
    for parse in (ast.literal_eval, json.loads):
        try:
            data = parse(t)
            break
        except Exception:
            continue
    if not isinstance(data, dict):
        return []
    for comp in data.get("components") or []:
        if isinstance(comp, dict) and comp.get("type") == "body":
            return [str(p.get("text", "")) for p in (comp.get("parameters") or [])
                    if isinstance(p, dict)]
    return []


def _fill(body, params):
    """Substitute `{{1}}`-style placeholders. Unmatched ones are dropped rather
    than shown — `{{2}}` on a customer's screen is worse than a short sentence."""
    def sub(m):
        i = int(m.group(1)) - 1
        return str(params[i]) if 0 <= i < len(params) else ""
    return re.sub(r"\s+", " ", PLACEHOLDER.sub(sub, str(body or ""))).strip()


def _template_bodies():
    """name -> (body, header) for every template, fetched once per request.

    Cached on `frappe.local`: a 200-message thread would otherwise re-read the
    template table once per bubble.
    """
    cached = getattr(frappe.local, "upande_crm_wa_templates", None)
    if cached is not None:
        return cached
    out = {}
    if _has("WhatsApp Templates"):
        try:
            for r in frappe.get_all("WhatsApp Templates",
                                    fields=["name", "template", "header"],
                                    limit=0, ignore_permissions=True):
                out[r.name] = (r.template or "", r.header or "")
        except Exception:
            out = {}
    frappe.local.upande_crm_wa_templates = out
    return out


def _message_text(row):
    """Readable text for one message row, whatever `frappe_whatsapp` stored."""
    raw = row.get("message")
    is_template = (row.get("message_type") == "Template"
                   or bool(row.get("template"))
                   or _looks_like_payload(raw))
    if not is_template:
        return raw

    params = []
    try:
        params = frappe.parse_json(row.get("template_parameters") or "[]") or []
    except Exception:
        params = []
    if not isinstance(params, list) or not params:
        params = _payload_params(raw)

    body, header = _template_bodies().get(row.get("template") or "", ("", ""))
    text = _fill(body, params) if body else ""
    if not text:
        # No template body on record (deleted, or a foreign template): the
        # parameters alone still say more than the payload does.
        text = " · ".join(str(p) for p in params if str(p).strip())
    if not text:
        return _("[template message]")
    return f"{header}\n{text}" if header else text


@frappe.whitelist()
def crm_whatsapp_thread(party, limit=200):
    """Every message exchanged with `party`, oldest first."""
    _guard()
    if not _available():
        return {"party": party, "messages": [], "available": False}
    limit = max(1, min(int(limit or 200), 500))

    fields = ["name", "type", "status", "message", "content_type", "creation",
              "profile_name", "message_id", "reference_doctype", "reference_name",
              "message_type", "template", "template_parameters"]
    fields = [f for f in fields if f == "name" or _hascol("WhatsApp Message", f)]
    try:
        rows = frappe.get_all(
            "WhatsApp Message",
            fields=fields,
            or_filters=[["to", "=", party], ["from", "=", party]],
            order_by="creation asc",
            limit=limit,
            ignore_permissions=True,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "crm_whatsapp_thread failed")
        rows = []

    # Replace the stored payload with what was actually said. `template_name` lets
    # the bubble label itself, since a template read differently from free text.
    for r in rows:
        r["template_name"] = r.get("template") or None
        r["is_template"] = 1 if (r.get("message_type") == "Template"
                                 or r.get("template")
                                 or _looks_like_payload(r.get("message"))) else 0
        r["message"] = _message_text(r)

    last_inbound = None
    for r in rows:
        if r.get("type") == "Incoming":
            last_inbound = r.get("creation")

    s = _suffix(party)
    idx = _candidate_index()
    return {
        "party": party,
        "display_name": (next((r.get("profile_name") for r in reversed(rows)
                               if r.get("profile_name")), None)
                         or _profile_names().get(s)
                         or (idx.get(s) or {}).get("label") or party),
        "window_open": _window_open(last_inbound),
        "last_inbound_at": last_inbound,
        "link": idx.get(s),
        "messages": rows,
        "available": True,
    }


@frappe.whitelist()
def crm_whatsapp_mark_read(party):
    """Mark this party's inbound messages read, as the desk chat UI does."""
    _guard()
    if not _available():
        return {"party": party, "updated": 0}
    try:
        names = [r.name for r in frappe.get_all(
            "WhatsApp Message",
            filters={"from": party, "type": "Incoming"},
            fields=["name", "status"], limit=0, ignore_permissions=True,
        ) if (r.status or "") != READ_STATUS]
        for n in names:
            frappe.db.set_value("WhatsApp Message", n, "status", READ_STATUS,
                                update_modified=False)
        return {"party": party, "updated": len(names)}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "crm_whatsapp_mark_read failed")
        return {"party": party, "updated": 0}


# ---------------------------------------------------------------- templates
@frappe.whitelist()
def crm_whatsapp_templates():
    """APPROVED templates only — anything else cannot be delivered."""
    _guard()
    if not _has("WhatsApp Templates"):
        return []
    try:
        rows = frappe.get_all(
            "WhatsApp Templates",
            filters={"status": "APPROVED"},
            fields=["name", "actual_name", "language_code", "template", "header"],
            order_by="actual_name asc", limit=0, ignore_permissions=True,
        )
    except Exception:
        return []
    return [{
        "name": r.name,
        "actual_name": r.actual_name or r.name,
        "language_code": r.language_code or "",
        "preview": _plain(r.template, 220),
        "header": r.header or "",
    } for r in rows]


# ---------------------------------------------------------------- sending
def _check_ref(doctype):
    if not doctype:
        return
    if doctype not in WA_REF_DOCTYPES:
        frappe.throw(_("Cannot link a WhatsApp message to {0}").format(doctype),
                     frappe.PermissionError)


def _validate_ref(doctype, name):
    _check_ref(doctype)
    if doctype:
        if not (name and frappe.db.exists(doctype, name)):
            frappe.throw(_("Linked {0} not found").format(doctype))


def _last_inbound_at(party):
    try:
        return frappe.db.sql(
            """select max(creation) from `tabWhatsApp Message`
               where `from`=%s and type='Incoming'""", (party,))[0][0]
    except Exception:
        return None


def _free_text_warning(party):
    """Why this free-text send may not land — or None if the window is open.

    A warning, not a refusal. Outside Meta's 24-hour window free text is usually
    rejected, but not always (the window reopens on any inbound message, and this
    site's data is not the only source of truth for that). Refusing outright meant
    a chat could not be sent at all on a thread whose last inbound was old, so the
    call is now attempted and Meta's own verdict is what decides.
    """
    if _window_open(_last_inbound_at(party)):
        return None
    return _(
        "This contact has not messaged in the last 24 hours, so WhatsApp may reject "
        "free text. Send an approved template if it does not arrive."
    )


@frappe.whitelist()
def crm_whatsapp_send(to, message, reference_doctype=None, reference_name=None, reply_to=None):
    """Send free-form text.

    Attempted regardless of Meta's 24-hour window: a closed window is reported
    back as a `warning` rather than blocking the send, so a chat can always be
    sent on a thread that has only ever carried templates. A rejection by Meta
    propagates from the insert below — it is never reported as a success.
    """
    _guard()
    if not _available():
        frappe.throw(_("WhatsApp is not configured on this site"))

    number = _norm(to)
    if not number:
        frappe.throw(_("A recipient WhatsApp number is required"))
    if not _plain(message):
        frappe.throw(_("Message cannot be empty"))
    _validate_ref(reference_doctype, reference_name)

    warning = _free_text_warning(number)

    doc = frappe.get_doc({
        "doctype": "WhatsApp Message",
        "type": "Outgoing",
        "message_type": "Manual",
        "content_type": "text",
        "to": number,
        "message": message,
        "reference_doctype": reference_doctype or None,
        "reference_name": reference_name or None,
        "is_reply": 1 if reply_to else 0,
        "reply_to_message_id": reply_to or None,
    })
    # ignore_permissions: WhatsApp Message is System-Manager-only, and this
    # endpoint is already CRM-role gated with its reference validated above.
    # The insert itself performs the Meta dispatch (frappe_whatsapp
    # before_insert), so a failure here must propagate rather than be swallowed.
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status or "sent", "warning": warning}


@frappe.whitelist()
def crm_whatsapp_send_template(to, template, reference_doctype=None, reference_name=None):
    """Send an approved template. Valid regardless of the 24-hour window."""
    _guard()
    if not _available():
        frappe.throw(_("WhatsApp is not configured on this site"))

    number = _norm(to)
    if not number:
        frappe.throw(_("A recipient WhatsApp number is required"))
    if not template:
        frappe.throw(_("Select a template"))
    if not frappe.db.exists("WhatsApp Templates", template):
        frappe.throw(_("Template not found"))
    if frappe.db.get_value("WhatsApp Templates", template, "status") != "APPROVED":
        frappe.throw(_("Only APPROVED templates can be sent"))
    _validate_ref(reference_doctype, reference_name)

    doc = frappe.get_doc({
        "doctype": "WhatsApp Message",
        "type": "Outgoing",
        "message_type": "Template",
        "content_type": "text",
        "to": number,
        "template": template,
        "reference_doctype": reference_doctype or None,
        "reference_name": reference_name or None,
    })
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status or "sent"}


# ---------------------------------------------------------------- analytics
@frappe.whitelist()
def crm_whatsapp_analytics(date_from=None, date_to=None):
    _guard()
    frm, to = _range(date_from, date_to)
    if not _available():
        return {"available": False, "kpis": {}, "status_mix": [], "trend": [], "top": []}

    def one(sql, params=()):
        try:
            return frappe.db.sql(sql, params)[0][0] or 0
        except Exception:
            return 0

    rng = ("`creation` between %s and %s", (frm, str(to) + " 23:59:59"))
    sent = one(f"select count(*) from `tabWhatsApp Message` where type='Outgoing' and {rng[0]}", rng[1])
    recv = one(f"select count(*) from `tabWhatsApp Message` where type='Incoming' and {rng[0]}", rng[1])
    failed = one(
        f"select count(*) from `tabWhatsApp Message` where type='Outgoing' and status='failed' and {rng[0]}",
        rng[1])
    convos = one(
        f"""select count(distinct coalesce(nullif(`to`,''),`from`)) from `tabWhatsApp Message`
            where {rng[0]}""", rng[1])
    unread = one(
        f"""select count(*) from `tabWhatsApp Message`
            where type='Incoming' and coalesce(status,'') <> '{READ_STATUS}'""")

    def rows(sql, params=()):
        try:
            return frappe.db.sql(sql, params, as_dict=True)
        except Exception:
            return []

    status_mix = [
        {"label": r.status or "pending", "count": r.n}
        for r in rows(
            f"""select coalesce(nullif(status,''),'pending') status, count(*) n
                from `tabWhatsApp Message` where type='Outgoing' and {rng[0]}
                group by status order by n desc""", rng[1])
    ]
    trend = [
        {"label": str(r.d)[5:], "sent": int(r.sent or 0), "received": int(r.recv or 0)}
        for r in rows(
            f"""select date(creation) d,
                       sum(type='Outgoing') sent, sum(type='Incoming') recv
                from `tabWhatsApp Message` where {rng[0]}
                group by d order by d""", rng[1])
    ]
    profiles = _profile_names()
    idx = _candidate_index()
    top = []
    for r in rows(
        f"""select coalesce(nullif(`to`,''),`from`) party, count(*) n
            from `tabWhatsApp Message` where {rng[0]}
            group by party order by n desc limit 8""", rng[1]):
        s = _suffix(r.party)
        top.append({
            "label": profiles.get(s) or (idx.get(s) or {}).get("label") or r.party,
            "count": int(r.n or 0),
        })

    return {
        "available": True,
        "kpis": {
            "sent": sent, "received": recv, "failed": failed,
            "conversations": convos, "unread": unread,
            "fail_rate": round(failed / sent * 100, 1) if sent else 0.0,
        },
        "status_mix": status_mix,
        "trend": trend,
        "top": top,
    }
