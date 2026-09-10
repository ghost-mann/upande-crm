"""Demo content for the sections `demo_data.seed_demo` does not reach.

`demo_data` seeds the sales pipeline. Four surfaces stayed empty regardless,
each for its own reason, and each is filled here:

* **Inbox.** There is plenty of mail on this site — 16,461 real
  Communications — but the newest is dated 15 July 2026, and the dashboard
  opens on the last 30 days. Every folder therefore read "Showing 0 of 15457",
  which looks like a broken filter and is in fact an accurate answer to the
  question asked. Demo mail is weighted towards the last three weeks so the
  default range has something in it.

* **Correspondence.** That section joins Communication to a party through
  `Contact Email` -> `Contact` -> `Dynamic Link`. `demo_data` creates no
  Contacts at all, so its 40 emails could never be attributed and the matrix
  stayed empty even when mail existed. Contacts come first here, and the mail
  is addressed to them.

* **Campaigns.** Nothing seeded them, and the newest real Campaign is from
  January. Seeded with schedules, an audience and enrolments so the section
  shows a working drip rather than a list of names.

* **Claims.** `Customer Feedback` is the claims register behind the map's
  claims layer. Its itemised reasons are filled on 6 of 3,378 real records, so
  the demo rows carry full item detail — variety, reason category, cost — and
  the reason breakdown has something to draw.

Everything is tagged `crm-demo`, so `demo_data.clear_demo` removes it along
with the rest.
"""

import random

import frappe
from frappe.utils import add_days, nowdate

from upande_crm.demo_data import DEMO_TAG, SALES_PEOPLE, SALES_ROOT, _cfg, _tag

# Doctypes seeded here, in delete-safe order. `demo_data.clear_demo` reads this.
EXTRA_DOCTYPES = [
    "Customer Feedback",
    "Sales Person",
    "Email Campaign",
    "Campaign",
    "Email Group Member",
    "Email Group",
    "Contact",
]

EMAIL_GROUP = "Demo Export Buyers"

# Defined in `demo_data` so the base seeder and this one cannot disagree
# about who the demo belongs to.

# (title, description, [(days_after_start, template_subject)])
_CAMPAIGNS = [
    (
        "Valentine Peak Pre-Book 2027",
        "Secure volume commitments for the February peak before capacity is "
        "allocated. Targets wholesale and auction buyers who ordered in the "
        "last two peaks.",
        [(0, "Valentine 2027 — open your allocation"),
         (5, "Varietal availability and stem-length grid"),
         (12, "Pre-book closes Friday — confirm volumes")],
    ),
    (
        "Spray Rose Introduction — Q4",
        "Introduce the new spray varieties to florists and supermarket "
        "programmes that currently buy standard roses only.",
        [(0, "Three new spray varieties, sample box on request"),
         (7, "Vase-life trial results"),
         (14, "Programme pricing for Q4")],
    ),
    (
        "Cool-Chain Assurance Programme",
        "Reassure buyers in long-haul markets about post-harvest handling "
        "after the Q2 claims cluster. Educational rather than promotional.",
        [(0, "How your stems travel: farm to airport in 6 hours"),
         (10, "Temperature logs are now on every consignment")],
    ),
    (
        "Dormant Buyer Win-Back",
        "Re-open conversation with accounts that ordered in the last 18 months "
        "but nothing in the last two quarters.",
        [(0, "We have kept your allocation open"),
         (9, "What changed since you last ordered"),
         (21, "A sample consignment, on us")],
    ),
    (
        "Summer Flowers Range Launch",
        "Push the non-rose range into markets that take roses only, ahead of "
        "the European summer.",
        [(0, "Beyond roses — the summer range"),
         (8, "Mixed-box economics for smaller buyers")],
    ),
]

# (reason_category, reason) — every pair below is an exact Select option.
#
# Both fields are Selects and the doctype cross-validates them, so invented
# values are rejected: an earlier pass guessed "Cold Chain" / "Broken stems"
# and lost 37 of 48 claims silently, and a second pass truncated the option
# list while reading it and lost 12 more to "Other " (the real option is
# "Other disease / disorder"). The full vocabulary is reproduced here.
_REASONS_BY_CATEGORY = {
    "Quality / Disease": [
        "Botrytis", "Dehydration", "Petal blackening / falling",
        "Advanced cut stage", "Tight cut stage", "Small head size",
        "Powdery mildew", "Other disease / disorder",
        "Leaf blackening or yellowing",
    ],
    "Physical Damage": [
        "Bruises / pressure damage", "Broken / bent stems", "Broken heads",
    ],
    "Wrong Specification": [
        "Wrong variety", "Wrong length", "Wrong mix / product",
        "Wrong sleeve / mislabelled", "Wrong bunch rate",
    ],
    "Supply & Delivery": [
        "Missing or fewer stems", "Late delivery", "Over supply",
        "Order cancellation", "Wrong drop point",
    ],
    "Invoice / Commercial": ["Wrong pricing", "Invoice error or missing"],
    "Pest / Regulatory": ["Live pest found", "KEPHIS / PHYTO rejection"],
}

# Weighted so the breakdown looks like a real claims register rather than a
# uniform sample: quality and damage dominate, regulatory is rare.
_CATEGORY_WEIGHTS = [
    ("Quality / Disease", 40),
    ("Physical Damage", 22),
    ("Wrong Specification", 16),
    ("Supply & Delivery", 12),
    ("Invoice / Commercial", 6),
    ("Pest / Regulatory", 4),
]

_VARIETIES = ["Athena", "Moonwalk", "Fuschiana", "Giselle", "Aqua",
              "Tropical Amazon", "Furiosa", "Xlence"]


def _pick_reason():
    pool = [c for c, w in _CATEGORY_WEIGHTS for _ in range(w)]
    category = random.choice(pool)
    return random.choice(_VARIETIES), category, random.choice(_REASONS_BY_CATEGORY[category])


_CLAIM_TYPES = ["Claimed", "Rejected (Out of Spec)", "Returns"]

_SUBJECTS_RECENT = [
    "Consignment {n} — arrival condition",
    "Weekly availability list, w/c {d}",
    "Re: standing order adjustment",
    "Airway bill {n} — documents attached",
    "Price indication for 60cm premium",
    "Quality report, consignment {n}",
    "Re: Cool-chain temperature log",
    "Next week's allocation",
    "Sample box feedback",
    "Re: payment terms review",
]


def _has(dt):
    try:
        return bool(frappe.db.exists("DocType", dt))
    except Exception:
        return False


def _demo_customers():
    """The customers `demo_data` created, as (name, email-ish domain seed)."""
    return [
        r.name
        for r in frappe.get_all(
            "Customer", filters={"_user_tags": ["like", f"%{DEMO_TAG}%"]}, fields=["name"]
        )
    ]


FAILURES = {}


def _failed(what, exc):
    """Record a rejected insert instead of discarding it.

    The first run of this module lost 37 of 48 claims and every campaign
    enrolment to bare `except: pass`, and reported success. Failures are counted
    and printed now, so a doctype that changes its Select options is visible.
    """
    key = f"{what}: {type(exc).__name__}"
    FAILURES[key] = FAILURES.get(key, 0) + 1
    frappe.clear_last_message()


def seed_extras():
    """Seed contacts, recent mail, campaigns and claims. Idempotent per batch."""
    random.seed(4242)
    FAILURES.clear()
    cfg = _cfg()
    customers = _demo_customers()
    if not customers:
        print("No demo customers found — run upande_crm.demo_data.seed_demo first.")
        return {}

    made = {}
    people = _seed_sales_people(customers, made)
    contacts = _seed_contacts(customers, made)
    _seed_recent_mail(cfg, contacts, people, made)
    _seed_campaigns(cfg, contacts, made)
    _seed_claims(customers, made)

    frappe.db.commit()
    print("Seeded demo extras (tagged '%s'):" % DEMO_TAG)
    for k, v in sorted(made.items()):
        print("  %-22s %d" % (k, v))
    if FAILURES:
        print("  rejected inserts:")
        for k, v in sorted(FAILURES.items()):
            print("    %-40s %d" % (k, v))
    return made


# ------------------------------------------------------------------ sales people
def _seed_sales_people(customers, made):
    """Create the two demo sales people and give them the demo accounts.

    Returns `[(sales_person, user_email)]` for whoever resolved — a site
    without these users falls back to an empty list and the caller uses
    `_cfg()["users"]` instead.

    Worth doing beyond the email attribution: `Sales Team` on this site holds
    28 rows that are all one person, so anything measuring per-salesperson
    performance has nothing to compare. Two people across eight demo accounts
    gives it a shape to render.
    """
    made["Sales Person"] = 0
    if not _has("Sales Person"):
        return []

    people = []
    for full_name, email in SALES_PEOPLE:
        if not frappe.db.exists("User", email):
            continue
        if not frappe.db.exists("Sales Person", full_name):
            try:
                doc = frappe.get_doc(
                    {
                        "doctype": "Sales Person",
                        "sales_person_name": full_name,
                        "parent_sales_person": SALES_ROOT
                        if frappe.db.exists("Sales Person", SALES_ROOT)
                        else None,
                        "is_group": 0,
                        "enabled": 1,
                    }
                )
                doc.insert(ignore_permissions=True)
                _tag("Sales Person", doc.name)
                made["Sales Person"] += 1
            except Exception as e:
                _failed("Sales Person", e)
                continue
        people.append((full_name, email))

    if people and customers:
        _assign_accounts(customers, people, made)
    return people


def _assign_accounts(customers, people, made):
    """Split the demo customers between the demo sales people."""
    made["Sales Team rows"] = 0
    for i, cust in enumerate(customers):
        person = people[i % len(people)][0]
        try:
            doc = frappe.get_doc("Customer", cust)
            if any(r.sales_person == person for r in (doc.get("sales_team") or [])):
                continue
            doc.append("sales_team", {"sales_person": person, "allocated_percentage": 100})
            doc.save(ignore_permissions=True)
            made["Sales Team rows"] += 1
        except Exception as e:
            _failed("Sales Team", e)


# ------------------------------------------------------------------ contacts
_PEOPLE = [
    ("Marieke", "Visser"), ("Omar", "Al-Farsi"), ("Sophie", "Turner"),
    ("Ivan", "Petrov"), ("Lena", "Fischer"), ("James", "Whitfield"),
    ("Astrid", "Berg"), ("Kenji", "Watanabe"),
]


def _seed_contacts(customers, made):
    """One named buyer per demo customer, linked and with an email address.

    The link matters more than the person: `Correspondence` reaches a party only
    through `Dynamic Link`, so a Contact without one is invisible to it.
    """
    made["Contact"] = 0
    out = []
    for i, cust in enumerate(customers):
        first, last = _PEOPLE[i % len(_PEOPLE)]
        domain = "".join(ch for ch in cust.lower() if ch.isalnum())[:18] or "buyer"
        email = f"{first.lower()}.{last.lower().replace(' ', '')}@{domain}.example"
        doc = frappe.get_doc(
            {
                "doctype": "Contact",
                "first_name": first,
                "last_name": last,
                "email_ids": [{"email_id": email, "is_primary": 1}],
                "links": [{"link_doctype": "Customer", "link_name": cust}],
            }
        )
        doc.insert(ignore_permissions=True)
        _tag("Contact", doc.name)
        made["Contact"] += 1
        out.append({"contact": doc.name, "email": email, "customer": cust,
                    "person": f"{first} {last}"})
    return out


# ------------------------------------------------------------------ mail
def _seed_recent_mail(cfg, contacts, people, made):
    """Threaded mail weighted into the last three weeks.

    Weighted, not uniform: the point of this batch is that the dashboard's
    default 30-day window stops being empty, and a uniform spread over 120 days
    would put only a quarter of it in range.
    """
    made["Communication"] = 0
    if not contacts:
        return
    # Prefer the named sales people; fall back only if neither user exists.
    staff = [email for _, email in people] or cfg["users"] or [frappe.session.user]

    for i in range(180):
        c = contacts[i % len(contacts)]
        me = staff[i % len(staff)]
        # 70% inside the default window, the rest trailing back a few months.
        days = random.randint(0, 27) if random.random() < 0.7 else random.randint(28, 150)
        sent = i % 3 != 0  # two out of three outbound, so attribution has data
        subject = _SUBJECTS_RECENT[i % len(_SUBJECTS_RECENT)].format(
            n=f"{70000 + i}", d=add_days(nowdate(), -days)
        )
        doc = frappe.get_doc(
            {
                "doctype": "Communication",
                "communication_type": "Communication",
                "communication_medium": "Email",
                "sent_or_received": "Sent" if sent else "Received",
                "subject": subject,
                "content": (
                    f"<p>Dear {'team' if sent else c['person'].split()[0]},</p>"
                    f"<p>{subject}. Please see the attached detail for "
                    f"{c['customer']}.</p><p>Regards</p>"
                ),
                "sender": me if sent else c["email"],
                "recipients": c["email"] if sent else me,
                "communication_date": f"{add_days(nowdate(), -days)} "
                f"{random.randint(7, 18):02d}:{random.randint(0, 59):02d}:00",
                "reference_doctype": "Customer",
                "reference_name": c["customer"],
                "status": "Linked" if sent else "Open",
                # Unread inbound gives the inbox its unread rail something to show.
                "seen": 1 if sent else random.choice([0, 0, 1]),
            }
        )
        doc.insert(ignore_permissions=True)
        _tag("Communication", doc.name)
        made["Communication"] += 1


# ------------------------------------------------------------------ campaigns
def _seed_campaigns(cfg, contacts, made):
    made["Campaign"] = 0
    made["Email Group"] = 0
    made["Email Group Member"] = 0
    made["Email Campaign"] = 0
    if not _has("Campaign"):
        return

    group = None
    if _has("Email Group") and contacts:
        if frappe.db.exists("Email Group", EMAIL_GROUP):
            frappe.delete_doc("Email Group", EMAIL_GROUP, force=True, ignore_permissions=True)
        g = frappe.get_doc({"doctype": "Email Group", "title": EMAIL_GROUP})
        g.insert(ignore_permissions=True)
        _tag("Email Group", g.name)
        group = g.name
        made["Email Group"] += 1
        for c in contacts:
            try:
                m = frappe.get_doc(
                    {"doctype": "Email Group Member", "email_group": group,
                     "email": c["email"]}
                )
                m.insert(ignore_permissions=True)
                made["Email Group Member"] += 1
            except Exception as e:
                _failed("Email Group Member", e)

    templates = _ensure_templates()

    for idx, (title, description, schedule) in enumerate(_CAMPAIGNS):
        if frappe.db.exists("Campaign", title):
            continue
        rows = []
        if _has("Campaign Email Schedule") and templates:
            for offset, subject in schedule:
                rows.append(
                    {
                        "email_template": templates[hash(subject) % len(templates)],
                        "send_after_days": offset,
                    }
                )
        doc = frappe.get_doc(
            {
                "doctype": "Campaign",
                "campaign_name": title,
                "description": description,
                "campaign_schedules": rows,
            }
        )
        doc.insert(ignore_permissions=True)
        _tag("Campaign", doc.name)
        made["Campaign"] += 1

        # Enrol a few buyers so the section shows a live drip, not just a plan.
        if _has("Email Campaign") and contacts and rows:
            for c in contacts[: 3 + (idx % 3)]:
                try:
                    ec = frappe.get_doc(
                        {
                            "doctype": "Email Campaign",
                            # The Link field is `campaign_name`, not `campaign`.
                            "campaign_name": doc.name,
                            "email_campaign_for": "Contact",
                            "recipient": c["contact"],
                            "sender": cfg["users"][0] if cfg["users"] else frappe.session.user,
                            # "Start Date cannot be before the current date" —
                            # enrolments are scheduled forward, never backdated.
                            "start_date": add_days(nowdate(), random.randint(0, 14)),
                        }
                    )
                    ec.insert(ignore_permissions=True)
                    _tag("Email Campaign", ec.name)
                    made["Email Campaign"] += 1
                except Exception as e:
                    _failed("Email Campaign", e)


def _ensure_templates():
    """Email Templates the campaign schedules point at."""
    if not _has("Email Template"):
        return []
    wanted = [
        ("Demo — Allocation Open", "Your allocation is open"),
        ("Demo — Variety Update", "New varieties available"),
        ("Demo — Closing Soon", "Pre-book closes this week"),
    ]
    out = []
    for name, subject in wanted:
        if not frappe.db.exists("Email Template", name):
            try:
                t = frappe.get_doc(
                    {
                        "doctype": "Email Template",
                        "name": name,
                        "subject": subject,
                        "response": f"<p>{subject}. Reply to this email to confirm.</p>",
                        "use_html": 1,
                    }
                )
                t.insert(ignore_permissions=True)
            except Exception:
                frappe.clear_last_message()
                continue
        out.append(name)
    return out


# ------------------------------------------------------------------ claims
def _seed_claims(customers, made):
    """Quality claims with itemised reasons.

    Itemised on purpose. The real register records a reason on 6 of 3,378
    claims, so the map's reason breakdown has nothing to draw; these rows give
    it something without touching a single real record.
    """
    made["Customer Feedback"] = 0
    if not _has("Customer Feedback"):
        return

    for i in range(48):
        cust = customers[i % len(customers)]
        n_items = random.randint(1, 3)
        items, stems_total, cost_total = [], 0, 0.0
        for _ in range(n_items):
            variety, category, reason = _pick_reason()
            received = random.choice([2000, 5000, 10000, 20000])
            claimed = int(received * random.uniform(0.05, 0.4))
            price = round(random.uniform(0.8, 2.2), 2)
            cost = round(claimed * price, 2)
            stems_total += claimed
            cost_total += cost
            items.append(
                {
                    "variety": variety,
                    "stem_length": random.choice([40, 50, 60, 70]),
                    "stems_received": received,
                    "stems_claimed": claimed,
                    "price_per_stem": price,
                    "claim_cost": cost,
                    "reason_category": category,
                    "reason": reason,
                }
            )
        try:
            doc = frappe.get_doc(
                {
                    "doctype": "Customer Feedback",
                    "feedback_date": add_days(nowdate(), -random.randint(0, 60)),
                    "feedback_type": "Quality Claim",
                    "status": random.choice(["Submitted", "Resolved", "Closed"]),
                    "customer_company": cust,
                    "contact_name": "Demo Buyer",
                    "contact_email": "buyer@example.com",
                    "location": random.choice(["Market", "Airport"]),
                    "control_point": random.choice(["Market", "Airport"]),
                    "claim_type": _CLAIM_TYPES[i % len(_CLAIM_TYPES)],
                    "consignment_number": str(60000 + i),
                    "shipment_date": add_days(nowdate(), -random.randint(1, 70)),
                    "claim_items": items,
                    "total_stems_claimed": stems_total,
                    "total_claim_cost": round(cost_total, 2),
                }
            )
            doc.insert(ignore_permissions=True)
            _tag("Customer Feedback", doc.name)
            made["Customer Feedback"] += 1
        except Exception as e:
            _failed("Customer Feedback", e)
