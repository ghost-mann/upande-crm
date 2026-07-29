"""Campaigns: define a drip sequence, enrol recipients, measure the result.

## How ERPNext's campaign machinery actually works

Researched before building, because two different doctypes are both called
"campaign" and they do unrelated jobs:

**`Campaign`** (CRM module) is the *definition*: a title, a description, and a child
table `Campaign Email Schedule` of `(email_template, send_after_days)` rows — a drip
sequence. 32 already exist on this site, 27 with a schedule, created by real staff.
Its `autoname` is `naming_series:` (`SAL-CAM-.YYYY.-`), so a new campaign's `name` is
a series id and the human title lives in `campaign_name`. The UI must show the
latter.

**`Email Campaign`** (CRM module) is an *enrolment*: one Campaign pointed at one
recipient — a Lead, a Contact or an Email Group — with a sender and a start date.
Its `end_date` is derived as `start_date + max(send_after_days)`.

**`UTM Campaign`** (Website module) is *attribution*, and is a separate thing:
`Lead.utm_campaign` links to it. It carries a `crm_campaign` Link field pointing
back at a `Campaign`, which is ERPNext's own bridge between the two concepts, so
that is what `_ensure_utm` populates rather than inventing a convention. Its
`autoname` is `prompt`, so the row name is the title itself — matching the 32 rows
already there.

**Sending is the scheduler's job, not ours.** `daily_maintenance` runs
`erpnext...email_campaign.send_email_to_leads_or_contacts` and
`set_email_campaign_status` once a day. Nothing sends on save, so the day-0 email
goes out on the next daily run. The UI says so; a user expecting an instant blast
would otherwise think it was broken.

## Validations the core controller enforces, which shape this API

Read from `erpnext/crm/doctype/email_campaign/email_campaign.py`:

* `start_date` before today throws;
* the Campaign must have a schedule, or "Please set up the Campaign Schedule";
* a Lead recipient must have an `email_id`;
* the same campaign cannot be enrolled twice for one recipient while Scheduled or
  In Progress.

Enrolment here is **bulk** — a user picks many leads at once — so one recipient
failing must not abort the batch. `crm_campaign_enrol` returns a per-recipient
result with the reason, and commits the ones that worked.

## Permissions

`Email Campaign` is System-Manager-only and `UTM Campaign` is granted to
System/Newsletter/Marketing Manager — neither includes the Sales roles this CRM is
for. So, exactly as `crm_send_email` does for Communication and `crm_whatsapp_send`
for WhatsApp Message, every endpoint role-gates through `_guard()` and then writes
with `ignore_permissions=True`. Campaign itself is writable by Sales Manager, so
that gate is real rather than nominal. The widening is deliberate and bounded: only
these doctypes, only through these endpoints, with recipients validated.

Writes surface every failure; the dashboard read degrades to empty.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate, today

from upande_crm.api.activity import _load, _pick
from upande_crm.api.crm import _count, _guard, _has, _hascol, _range

# What an enrolment may target, mirroring Email Campaign's own Select options.
ENROL_TARGETS = ("Lead", "Contact", "Email Group")

# Fields accepted from the client for a Campaign. Anything else is dropped.
CAMPAIGN_FIELDS = {"campaign_name", "description"}

# Enrolment states the core controller uses.
ACTIVE_STATUSES = ("Scheduled", "In Progress")


def _require():
    if not _has("Campaign") or not _has("Email Campaign"):
        frappe.throw(_("Campaigns need ERPNext's CRM module, which is not installed."))


def _is_manager():
    from upande_crm.api.activity import MANAGER_ROLES

    return bool(set(frappe.get_roles(frappe.session.user)) & MANAGER_ROLES)


# ---------------------------------------------------------------- reads
@frappe.whitelist()
def crm_email_templates():
    """Templates available for a drip schedule."""
    _guard()
    if not _has("Email Template"):
        return []
    try:
        return [
            {"name": r.name, "subject": r.subject or r.name}
            for r in frappe.get_all("Email Template", fields=["name", "subject"],
                                    order_by="name asc", limit=0, ignore_permissions=True)
        ]
    except Exception:
        return []


@frappe.whitelist()
def crm_email_groups():
    """Audience lists, with live member counts.

    `Email Group.total_subscribers` is a stored counter and can drift, so the
    active count is computed from the member rows instead.
    """
    _guard()
    if not _has("Email Group"):
        return []
    try:
        return [
            {"name": r.name, "total": cint(r.total), "active": cint(r.active),
             "unsubscribed": cint(r.total) - cint(r.active)}
            for r in frappe.db.sql(
                """select eg.name,
                          (select count(*) from `tabEmail Group Member` m
                           where m.email_group = eg.name) total,
                          (select count(*) from `tabEmail Group Member` m
                           where m.email_group = eg.name
                             and coalesce(m.unsubscribed, 0) = 0) active
                   from `tabEmail Group` eg
                   order by active desc""", as_dict=True)
        ]
    except Exception:
        return []


def _schedule_of(names):
    """{campaign name: [{email_template, send_after_days}]} in one query."""
    if not names or not _has("Campaign Email Schedule"):
        return {}
    out = {}
    try:
        for r in frappe.get_all(
            "Campaign Email Schedule",
            filters={"parent": ["in", list(names)]},
            fields=["parent", "email_template", "send_after_days"],
            order_by="parent asc, send_after_days asc", limit=0, ignore_permissions=True,
        ):
            out.setdefault(r.parent, []).append({
                "email_template": r.email_template,
                "send_after_days": cint(r.send_after_days),
            })
    except Exception:
        return {}
    return out


@frappe.whitelist()
def crm_dashboard_campaigns(date_from=None, date_to=None, customer=None):
    """Campaigns, their enrolments and what they are attributed to. Degrades."""
    _guard()
    if not _has("Campaign"):
        return {"available": False, "kpis": {}, "campaigns": [], "enrolments": [],
                "status_mix": [], "target_mix": [], "audiences": []}
    frm, to = _range(date_from, date_to)

    try:
        campaigns = frappe.get_all(
            "Campaign", fields=["name", "campaign_name", "description", "owner", "creation"],
            order_by="creation desc", limit=0, ignore_permissions=True)
    except Exception:
        campaigns = []

    schedules = _schedule_of([c.name for c in campaigns])

    # Enrolments per campaign, and the attribution counts, both in one pass.
    enrol_counts, active_counts = {}, {}
    try:
        for r in frappe.db.sql(
            """select campaign_name c, status s, count(*) n
               from `tabEmail Campaign` group by c, s""", as_dict=True):
            enrol_counts[r.c] = enrol_counts.get(r.c, 0) + cint(r.n)
            if r.s in ACTIVE_STATUSES:
                active_counts[r.c] = active_counts.get(r.c, 0) + cint(r.n)
    except Exception:
        pass

    attributed = {}
    if _hascol("Lead", "utm_campaign"):
        try:
            for r in frappe.db.sql(
                """select utm_campaign c, count(*) n, sum(status='Converted') converted
                   from tabLead where coalesce(utm_campaign,'') != ''
                   group by c""", as_dict=True):
                attributed[r.c] = {"leads": cint(r.n), "converted": cint(r.converted)}
        except Exception:
            pass

    # UTM row -> Campaign, so attribution can be reported against the campaign even
    # though the two are named differently (series id against title).
    utm_of = {}
    if _has("UTM Campaign") and _hascol("UTM Campaign", "crm_campaign"):
        try:
            for r in frappe.get_all("UTM Campaign", fields=["name", "crm_campaign"],
                                    limit=0, ignore_permissions=True):
                if r.crm_campaign:
                    utm_of[r.crm_campaign] = r.name
        except Exception:
            pass

    rows = []
    for c in campaigns:
        sched = schedules.get(c.name) or []
        utm = utm_of.get(c.name) or c.campaign_name
        attr = attributed.get(utm) or {}
        rows.append({
            "name": c.name,
            "title": (c.campaign_name or c.name).strip(),
            "description": c.description or "",
            "owner": c.owner,
            "creation": c.creation,
            "schedule": sched,
            "steps": len(sched),
            "duration_days": max([s["send_after_days"] for s in sched], default=0),
            "enrolled": enrol_counts.get(c.name, 0),
            "active": active_counts.get(c.name, 0),
            "attributed_leads": attr.get("leads", 0),
            "attributed_converted": attr.get("converted", 0),
        })

    enrolments = []
    try:
        enrolments = frappe.get_all(
            "Email Campaign",
            fields=["name", "campaign_name", "email_campaign_for", "recipient", "status",
                    "start_date", "end_date", "sender", "owner", "creation"],
            order_by="creation desc", limit=300, ignore_permissions=True)
    except Exception:
        enrolments = []
    titles = {c.name: (c.campaign_name or c.name).strip() for c in campaigns}
    for e in enrolments:
        e["campaign_title"] = titles.get(e.campaign_name, e.campaign_name)

    def mix(field):
        try:
            return [
                {"label": r.label or "Unknown", "count": cint(r.n)}
                for r in frappe.db.sql(
                    f"""select coalesce(nullif(`{field}`,''),'Unknown') label, count(*) n
                        from `tabEmail Campaign` group by label order by n desc limit 10""",
                    as_dict=True)
            ]
        except Exception:
            return []

    total_enrolled = sum(r["enrolled"] for r in rows)
    return {
        "available": True,
        "kpis": {
            "campaigns": len(rows),
            "with_schedule": sum(1 for r in rows if r["steps"]),
            "without_schedule": sum(1 for r in rows if not r["steps"]),
            "enrolled": total_enrolled,
            "active": sum(r["active"] for r in rows),
            "attributed_leads": sum(r["attributed_leads"] for r in rows),
            "in_range": _count("Campaign", {"creation": ["between", [frm, to]]}),
        },
        "campaigns": rows,
        "enrolments": enrolments,
        "status_mix": mix("status"),
        "target_mix": mix("email_campaign_for"),
        "audiences": crm_email_groups()[:10],
        # Stated in the UI: nothing sends on save.
        "sends_via_scheduler": True,
    }


@frappe.whitelist()
def crm_campaign_detail(name):
    """One campaign with its schedule and enrolments."""
    _guard()
    _require()
    if not frappe.db.exists("Campaign", name):
        frappe.throw(_("Campaign not found"), frappe.DoesNotExistError)
    doc = frappe.get_doc("Campaign", name)
    return {
        "name": doc.name,
        "title": (doc.campaign_name or doc.name).strip(),
        "description": doc.description or "",
        "schedule": [
            {"email_template": r.email_template, "send_after_days": cint(r.send_after_days)}
            for r in sorted(doc.get("campaign_schedules") or [],
                            key=lambda r: cint(r.send_after_days))
        ],
        "enrolments": frappe.get_all(
            "Email Campaign", filters={"campaign_name": name},
            fields=["name", "email_campaign_for", "recipient", "status", "start_date",
                    "end_date", "sender"],
            order_by="creation desc", limit=0, ignore_permissions=True),
    }


# ---------------------------------------------------------------- writes
@frappe.whitelist()
def crm_campaign_save(campaign):
    """Create or update a Campaign and its drip schedule.

    The schedule is replaced wholesale: the client always sends the full list, so
    removing a step client-side removes it here — the same contract Event
    participants use in api/activity.py.
    """
    _guard()
    _require()
    payload = _load(campaign) or {}
    name = payload.get("name")
    fields = _pick(payload, CAMPAIGN_FIELDS)

    title = str(fields.get("campaign_name") or "").strip()
    if not title:
        frappe.throw(_("A campaign needs a name."))
    fields["campaign_name"] = title

    schedule = payload.get("schedule") or []
    if not isinstance(schedule, list):
        frappe.throw(_("Malformed schedule"))

    seen = set()
    cleaned = []
    for row in schedule:
        template = str((row or {}).get("email_template") or "").strip()
        days = cint((row or {}).get("send_after_days"))
        if not template:
            frappe.throw(_("Every schedule step needs an email template."))
        if not frappe.db.exists("Email Template", template):
            frappe.throw(_("Unknown email template: {0}").format(template))
        if days < 0:
            frappe.throw(_("A step cannot send a negative number of days after the start."))
        if days in seen:
            # Two templates on the same day is legal in the doctype but almost
            # always a mistake, and impossible to reason about in a drip.
            frappe.throw(_("Two steps both send after {0} days — give them different offsets.").format(days))
        seen.add(days)
        cleaned.append({"email_template": template, "send_after_days": days})

    if name:
        doc = frappe.get_doc("Campaign", name)
        _assert_may_edit(doc)
        doc.update(fields)
    else:
        # Campaign is named by its title on this site, so a repeated name is a
        # primary-key collision. Caught here because the raw DuplicateEntryError
        # surfaces as a traceback rather than something a user can act on.
        if frappe.db.exists("Campaign", title):
            frappe.throw(
                _("A campaign called {0} already exists — pick a different name.").format(title),
                frappe.DuplicateEntryError,
            )
        doc = frappe.get_doc({"doctype": "Campaign", **fields})

    doc.set("campaign_schedules", [])
    for row in sorted(cleaned, key=lambda r: r["send_after_days"]):
        doc.append("campaign_schedules", row)

    if name:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)
    return {"name": doc.name, "title": doc.campaign_name, "steps": len(cleaned)}


def _assert_may_edit(doc):
    """Only the campaign's owner or a manager may change it.

    Campaigns are shared marketing assets that other people have enrolled
    recipients into, so an arbitrary Sales User editing someone else's schedule
    would silently change what those recipients receive next.
    """
    if doc.owner != frappe.session.user and not _is_manager():
        frappe.throw(
            _("Only {0} or a manager can change this campaign.").format(doc.owner),
            frappe.PermissionError,
        )


def _ensure_utm(campaign_name, title):
    """The UTM Campaign row used to attribute leads to this campaign.

    `UTM Campaign.autoname` is `prompt`, so the row name is the title itself, which
    matches the 32 rows already on this site. Its `crm_campaign` Link is ERPNext's
    own bridge back to the Campaign, so attribution is not a local convention.
    Returns the UTM name, or None if the doctype is unavailable.
    """
    if not _has("UTM Campaign"):
        return None
    title = (title or campaign_name).strip()
    if not title:
        return None
    try:
        if not frappe.db.exists("UTM Campaign", title):
            row = frappe.get_doc({"doctype": "UTM Campaign", "__newname": title})
            if _hascol("UTM Campaign", "crm_campaign"):
                row.crm_campaign = campaign_name
            row.insert(ignore_permissions=True)
        elif _hascol("UTM Campaign", "crm_campaign"):
            # Keep the bridge pointing at the campaign even for rows that predate it.
            if not frappe.db.get_value("UTM Campaign", title, "crm_campaign"):
                frappe.db.set_value("UTM Campaign", title, "crm_campaign", campaign_name,
                                    update_modified=False)
        return title
    except Exception:
        frappe.log_error(frappe.get_traceback(), "campaign UTM attribution failed")
        return None


@frappe.whitelist()
def crm_campaign_enrol(campaign=None, target=None, recipients=None, start_date=None,
                       sender=None, attribute=1):
    """Enrol many recipients in a campaign, one Email Campaign each.

    Bulk by design, so a single rejected recipient must not lose the whole batch:
    every recipient gets its own result with the reason it failed. The core
    controller rejects a Lead with no email, a duplicate active enrolment, and a
    start date in the past — all of which are per-recipient facts.
    """
    _guard()
    _require()

    if not campaign or not frappe.db.exists("Campaign", campaign):
        frappe.throw(_("Pick a campaign."))
    if target not in ENROL_TARGETS:
        frappe.throw(_("A campaign can be sent to a {0}.").format(" / ".join(ENROL_TARGETS)))

    names = _load(recipients)
    if isinstance(names, str):
        names = [names]
    names = [str(n).strip() for n in (names or []) if str(n or "").strip()]
    if not names:
        frappe.throw(_("Pick at least one recipient."))

    schedule = frappe.get_all("Campaign Email Schedule", filters={"parent": campaign},
                              fields=["send_after_days"], limit=0, ignore_permissions=True)
    if not schedule:
        frappe.throw(_(
            "This campaign has no schedule yet, so there is nothing to send. "
            "Add at least one template step first."
        ))

    start = str(start_date or today())
    if getdate(start) < getdate(nowdate()):
        frappe.throw(_("The start date cannot be in the past."))

    title = (frappe.db.get_value("Campaign", campaign, "campaign_name")
             or campaign).strip()
    utm = _ensure_utm(campaign, title) if cint(attribute) else None

    results = []
    for recipient in names:
        if not frappe.db.exists(target, recipient):
            results.append({"recipient": recipient, "ok": False,
                            "error": _("{0} not found").format(target)})
            continue
        try:
            doc = frappe.get_doc({
                "doctype": "Email Campaign",
                "campaign_name": campaign,
                "email_campaign_for": target,
                "recipient": recipient,
                "sender": sender or frappe.session.user,
                "start_date": start,
            })
            doc.insert(ignore_permissions=True)
            attributed = False
            if utm and target == "Lead" and _hascol("Lead", "utm_campaign"):
                # Attribution is the point of tagging: without it no campaign can be
                # evaluated, since utm_campaign is unset on every lead on this site.
                frappe.db.set_value("Lead", recipient, "utm_campaign", utm,
                                    update_modified=False)
                attributed = True
            results.append({"recipient": recipient, "ok": True, "name": doc.name,
                            "attributed": attributed})
        except Exception as e:
            results.append({"recipient": recipient, "ok": False,
                            "error": str(e)[:200]})

    enrolled = [r for r in results if r["ok"]]
    return {
        "campaign": campaign,
        "title": title,
        "utm_campaign": utm,
        "enrolled": len(enrolled),
        "failed": len(results) - len(enrolled),
        "results": results,
        # Said plainly, because nothing has been sent yet at this point.
        "note": _("Enrolled. The first email goes out on the next daily scheduler run, "
                  "not immediately."),
    }


@frappe.whitelist()
def crm_campaign_cancel(name):
    """Remove one enrolment. Owner or manager only."""
    _guard()
    _require()
    owner = frappe.db.get_value("Email Campaign", name, "owner")
    if not owner:
        frappe.throw(_("Enrolment not found"), frappe.DoesNotExistError)
    if owner != frappe.session.user and not _is_manager():
        frappe.throw(_("Only {0} or a manager can cancel this enrolment.").format(owner),
                     frappe.PermissionError)
    frappe.delete_doc("Email Campaign", name, ignore_permissions=True)
    return {"name": name, "cancelled": True}


@frappe.whitelist()
def crm_campaign_recipients(target=None, search="", limit=50):
    """Candidate recipients for the enrol dialog.

    Leads without an email address are returned but flagged: the core controller
    will refuse them, and showing why up front beats a failed row after the fact.
    """
    _guard()
    if target not in ENROL_TARGETS:
        return []
    search = str(search or "").strip()
    limit = max(1, min(cint(limit) or 50, 200))

    try:
        if target == "Lead":
            filters = {}
            if search:
                filters = {"lead_name": ["like", f"%{search}%"]}
            rows = frappe.get_all("Lead", filters=filters,
                                  fields=["name", "lead_name", "company_name", "email_id",
                                          "status"],
                                  order_by="creation desc", limit=limit,
                                  ignore_permissions=True)
            return [{"name": r.name,
                     "label": r.lead_name or r.company_name or r.name,
                     "detail": r.email_id or _("no email address"),
                     "eligible": bool(r.email_id)} for r in rows]
        if target == "Contact":
            filters = {}
            if search:
                filters = {"first_name": ["like", f"%{search}%"]}
            rows = frappe.get_all("Contact", filters=filters,
                                  fields=["name", "first_name", "last_name", "email_id"],
                                  order_by="modified desc", limit=limit,
                                  ignore_permissions=True)
            return [{"name": r.name,
                     "label": " ".join(x for x in (r.first_name, r.last_name) if x) or r.name,
                     "detail": r.email_id or _("no email address"),
                     "eligible": bool(r.email_id)} for r in rows]
        groups = crm_email_groups()
        if search:
            groups = [g for g in groups if search.lower() in g["name"].lower()]
        return [{"name": g["name"], "label": g["name"],
                 "detail": _("{0} active subscribers").format(g["active"]),
                 "eligible": g["active"] > 0} for g in groups[:limit]]
    except Exception:
        return []
