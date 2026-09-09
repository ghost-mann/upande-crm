"""Who, on our side, is actually talking to each client.

The question this answers is "which of our people is in email contact with this
account" — asked because the desk shows a mailbox, not a relationship, and a
manager reading a thread cannot tell whether an account has one owner, four, or
none.

## Why correspondence and not Sales Team

`Sales Team` is the field ERPNext provides for this and it is unusable here: 28
rows on kaitet.local, all of them the same person, and `Sales Invoice.
sales_partner` is empty on all 13,780 invoices. Attribution has to come from
something people actually do, and they do send email — 1,004 outgoing
Communications from named individual addresses (bob@, paul@, juliana@,
pmaina@…). That is the signal.

## The join

Communication carries no party link worth having: only 56 of 37,196 rows point
at a Customer. But the address does the work, because Contact does have party
links:

    Communication.recipients  contains  Contact Email.email_id   (outbound)
    Communication.sender      equals    Contact Email.email_id   (inbound)
    Contact Email.parent  ->  Contact  ->  Dynamic Link  ->  Customer/Lead/Prospect

Measured: 15,414 of 15,457 inbound emails match a Contact, and the outbound side
yields 194 distinct (staff, party) pairs. `locate()` is used for outbound rather
than equality because `recipients` is a comma-joined list.

Automated Messages are excluded throughout. They are 20,735 of the 37,196 rows
and are sent by the system, not by a person — counting them would make the
notification mailer look like the most active salesperson in the company.
"""

import frappe

from upande_crm.api.crm import _guard, _has, _range

PARTY_TYPES = ("Customer", "Lead", "Prospect")

# Addresses that are a function rather than a person. They are real
# correspondents and are still counted, but the UI labels them so nobody reads
# "purchasing@" as an individual's performance.
SHARED_MAILBOXES = ("purchasing@", "info@", "sales@", "admin@", "accounts@", "support@", "noreply@")


def _is_shared(address):
    return any(str(address or "").lower().startswith(p) for p in SHARED_MAILBOXES)


def _available():
    return _has("Communication") and _has("Contact Email") and _has("Dynamic Link")


def _person(address):
    """Display name for an internal address: the local part, title-cased."""
    local = str(address or "").split("@")[0]
    return local.replace(".", " ").replace("_", " ").title() or address


@frappe.whitelist()
def crm_correspondence(date_from=None, date_to=None, limit=200):
    """The staff-to-client correspondence matrix.

    One row per (staff address, party), with direction counts and the last date
    either side wrote. Ordered by total volume.
    """
    _guard()
    frm, to = _range(date_from, date_to)
    limit = min(int(limit or 200), 500)
    if not _available():
        return {"rows": [], "staff": [], "unattributed": 0}

    out, sent = {}, _sent(frm, to, limit)
    for r in sent:
        key = (r.staff, r.party_type, r.party)
        out[key] = {
            "staff": r.staff,
            "staff_name": _person(r.staff),
            "shared": _is_shared(r.staff),
            "party_type": r.party_type,
            "party": r.party,
            "sent": int(r.n or 0),
            "received": 0,
            "last": str(r.last or ""),
        }

    for r in _received(frm, to, limit):
        # Inbound mail names the client, not our person, so it cannot be
        # attributed to a colleague on its own. It is folded into whichever
        # staff row already exists for that party; if none does, the party is
        # corresponding with nobody in particular and gets an unassigned row.
        matches = [k for k in out if k[2] == r.party]
        if matches:
            share = int(r.n or 0)
            for k in matches:
                out[k]["received"] += share if len(matches) == 1 else 0
            if len(matches) > 1:
                out[matches[0]]["received"] += share
        else:
            key = ("", r.party_type, r.party)
            out.setdefault(
                key,
                {
                    "staff": "",
                    "staff_name": "Unassigned",
                    "shared": False,
                    "party_type": r.party_type,
                    "party": r.party,
                    "sent": 0,
                    "received": 0,
                    "last": "",
                },
            )
            out[key]["received"] += int(r.n or 0)
            out[key]["last"] = max(out[key]["last"], str(r.last or ""))

    ranked = sorted(out.values(), key=lambda x: -(x["sent"] + x["received"]))
    rows = ranked[:limit]
    return {
        "rows": rows,
        # Totalled over the rows actually returned, not over `ranked`. The
        # sidebar's per-person account count is a legend for the table beside
        # it, so counting pairs the table does not contain would have it claim
        # 22 accounts next to a list of 21.
        "staff": _staff_totals(rows),
        "truncated": len(ranked) > len(rows),
        "date_from": frm,
        "date_to": to,
    }


def _sent(frm, to, limit):
    try:
        return frappe.db.sql(
            """select c.sender staff, dl.link_doctype party_type, dl.link_name party,
                      count(*) n, max(c.communication_date) last
               from `tabCommunication` c
               join `tabContact Email` ce
                 on locate(ce.email_id, ifnull(c.recipients, '')) > 0
               join `tabDynamic Link` dl
                 on dl.parent = ce.parent and dl.parenttype = 'Contact'
               where c.communication_type = 'Communication'
                 and c.sent_or_received = 'Sent'
                 and c.communication_date between %s and %s
                 and dl.link_doctype in %s
               group by staff, party_type, party
               order by n desc limit %s""",
            (frm, to, PARTY_TYPES, limit),
            as_dict=True,
        )
    except Exception:
        frappe.clear_last_message()
        return []


def _received(frm, to, limit):
    try:
        return frappe.db.sql(
            """select dl.link_doctype party_type, dl.link_name party,
                      count(*) n, max(c.communication_date) last
               from `tabCommunication` c
               join `tabContact Email` ce on ce.email_id = c.sender
               join `tabDynamic Link` dl
                 on dl.parent = ce.parent and dl.parenttype = 'Contact'
               where c.communication_type = 'Communication'
                 and c.sent_or_received = 'Received'
                 and c.communication_date between %s and %s
                 and dl.link_doctype in %s
               group by party_type, party
               order by n desc limit %s""",
            (frm, to, PARTY_TYPES, limit),
            as_dict=True,
        )
    except Exception:
        frappe.clear_last_message()
        return []


def _staff_totals(rows):
    """Per-person totals: how many accounts they touch and how much they write."""
    agg = {}
    for r in rows:
        if not r["staff"]:
            continue
        a = agg.setdefault(
            r["staff"],
            {
                "staff": r["staff"],
                "staff_name": r["staff_name"],
                "shared": r["shared"],
                "accounts": 0,
                "sent": 0,
                "received": 0,
                "last": "",
            },
        )
        a["accounts"] += 1
        a["sent"] += r["sent"]
        a["received"] += r["received"]
        a["last"] = max(a["last"], r["last"])
    return sorted(agg.values(), key=lambda x: -x["sent"])


def staff_for_territory(territory, frm, to, limit=6):
    """Correspondents for customers in one territory.

    Used by the territory map's detail panel. Customers only: Lead and Prospect
    carry a territory too, but mixing them would double-count an account that has
    been converted and still has its old lead record.
    """
    if not _available() or not _has("Customer"):
        return []
    try:
        rows = frappe.db.sql(
            """select c.sender staff, count(*) n,
                      count(distinct cu.name) accounts,
                      max(c.communication_date) last
               from `tabCommunication` c
               join `tabContact Email` ce
                 on locate(ce.email_id, ifnull(c.recipients, '')) > 0
               join `tabDynamic Link` dl
                 on dl.parent = ce.parent and dl.parenttype = 'Contact'
                 and dl.link_doctype = 'Customer'
               join `tabCustomer` cu on cu.name = dl.link_name
               where c.communication_type = 'Communication'
                 and c.sent_or_received = 'Sent'
                 and c.communication_date between %s and %s
                 and cu.territory = %s
               group by staff order by n desc limit %s""",
            (frm, to, territory, limit),
            as_dict=True,
        )
    except Exception:
        frappe.clear_last_message()
        return []
    return [
        {
            "staff": r.staff,
            "staff_name": _person(r.staff),
            "shared": _is_shared(r.staff),
            "emails": int(r.n or 0),
            "accounts": int(r.accounts or 0),
            "last": str(r.last or ""),
        }
        for r in rows
    ]


@frappe.whitelist()
def crm_party_correspondents(party, party_type="Customer", limit=8):
    """Who has written to one account, newest first.

    Backs the "handled by" chip on a thread and on a customer row: given the
    party, say which colleagues are in the conversation.
    """
    _guard()
    if not party or not _available():
        return []
    if party_type not in PARTY_TYPES:
        party_type = "Customer"
    try:
        rows = frappe.db.sql(
            """select c.sender staff, count(*) n, max(c.communication_date) last
               from `tabCommunication` c
               join `tabContact Email` ce
                 on locate(ce.email_id, ifnull(c.recipients, '')) > 0
               join `tabDynamic Link` dl
                 on dl.parent = ce.parent and dl.parenttype = 'Contact'
               where c.communication_type = 'Communication'
                 and c.sent_or_received = 'Sent'
                 and dl.link_doctype = %s and dl.link_name = %s
               group by staff order by n desc limit %s""",
            (party_type, party, min(int(limit or 8), 25)),
            as_dict=True,
        )
    except Exception:
        frappe.clear_last_message()
        return []
    return [
        {
            "staff": r.staff,
            "staff_name": _person(r.staff),
            "shared": _is_shared(r.staff),
            "emails": int(r.n or 0),
            "last": str(r.last or ""),
        }
        for r in rows
    ]


@frappe.whitelist()
def crm_correspondent_for_emails(addresses):
    """Map client email addresses to the colleague who last wrote to them.

    Batched on purpose. The mail list renders 50 rows at a time and needs a
    badge on each; asking per row would be 50 requests per page.
    """
    _guard()
    if isinstance(addresses, str):
        addresses = [a.strip() for a in addresses.split(",") if a.strip()]
    addresses = [a for a in (addresses or []) if a][:200]
    if not addresses or not _available():
        return {}

    try:
        rows = frappe.db.sql(
            """select ce.email_id addr, c.sender staff, max(c.communication_date) last,
                      count(*) n
               from `tabCommunication` c
               join `tabContact Email` ce
                 on locate(ce.email_id, ifnull(c.recipients, '')) > 0
               where c.communication_type = 'Communication'
                 and c.sent_or_received = 'Sent'
                 and ce.email_id in %s
               group by addr, staff""",
            (addresses,),
            as_dict=True,
        )
    except Exception:
        frappe.clear_last_message()
        return {}

    best = {}
    for r in rows:
        cur = best.get(r.addr)
        if not cur or (r.n or 0) > cur["emails"]:
            best[r.addr] = {
                "staff": r.staff,
                "staff_name": _person(r.staff),
                "shared": _is_shared(r.staff),
                "emails": int(r.n or 0),
                "last": str(r.last or ""),
            }
    return best
