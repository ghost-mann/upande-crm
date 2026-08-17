"""The cohort funnel: one lead population, walked forward.

Extracted so the Overview and Sales Analytics cannot disagree about what a funnel
is. They used to. `api/pipeline.py` built a correct cohort walk for Analytics and
documented, in its own docstring, why the alternative is worthless:

    Counting each stage independently -- what the Overview funnel does --
    produces nonsense when the stages are not linked: it reports 4 leads and
    1,429 orders in the same funnel, as though orders were 300x the leads that
    produced them.

...and then left that Overview funnel in place. This module is the one walk, and
both sections import it.

## Two routes to an opportunity, not one

A lead reaches an Opportunity either directly (`opportunity_from='Lead'`) or
through a Prospect (`Prospect Lead` -> Prospect -> `opportunity_from='Prospect'`).
The walk unions both and deduplicates on opportunity name, because a lead can be
linked both ways and must not be counted twice.

**The second route currently yields nothing on this site, and that is a finding,
not a bug here.** Measured: 45 opportunities come from a Lead and 8 from a
Prospect, but those 8 sit on five prospects (Asia Pacific Florals, Deutsche
Blumen AG, Gulf Horticulture Holdings, MSD, Nippon Flower Trading) that have
*zero* rows in `Prospect Lead`. The 30 prospects that do carry lead links have no
opportunities. So the two populations do not overlap at all, and `via_prospect`
comes back 0.

The route is still walked rather than dropped: it is the correct traversal, it
costs one indexed query, and the moment somebody converts a lead through a
prospect — which `api/leads.py` now makes possible from the Overview — it starts
counting. What it must not do is be *described* as recovering opportunities the
old walk missed. It recovers none today.

## Why Prospect is not a stage

Prospect is a *branch*, not a step. 30 leads link to a prospect while 45 reach an
opportunity, so drawing Prospect between Leads and Opportunities makes the shape
narrow to 30 and then widen back to 45 -- a funnel that is not a funnel. This is
the same trap `pipeline.py` avoided when it refused to insert Quotations:

    inserting it would draw a funnel that narrows to 3 and then widens back to
    20 -- visibly wrong, and wrong about the process.

The prospect route is reported as `via_prospect` *inside* the Opportunities
stage, where it is a true decomposition and cannot break monotonicity.

A read module: every query is individually guarded and degrades to empty.
"""

import frappe

from upande_crm.api.crm import _df, _has, _hascol, _sf

# Records carried inside a stage so the UI can drill without a second endpoint.
SAMPLE_LIMIT = 20

# Names per `IN (...)` clause. The cohort is every lead in the range, which on a
# long window is however many leads the site has ever had — one clause holding all
# of them is a query no database should be asked to parse. Batching keeps each
# statement bounded without changing a single count.
BATCH = 1000


def _pct(part, whole):
    return round(part / whole * 100, 1) if whole else 0.0


def _batched(values, size=BATCH):
    values = list(values)
    for i in range(0, len(values), size):
        yield values[i:i + size]


def _fetch_in(doctype, field, values, fields, extra=None):
    """`frappe.get_all` over an `in` filter, batched. Returns [] on any failure."""
    if not values or not _has(doctype):
        return []
    out = []
    try:
        for chunk in _batched(values):
            out.extend(frappe.get_all(
                doctype,
                filters={**(extra or {}), field: ["in", chunk]},
                fields=fields,
                limit=0,
            ))
    except Exception:
        return []
    return out


def _names(doctype, filters, limit=0):
    if not _has(doctype):
        return []
    try:
        return frappe.get_all(doctype, filters=filters, pluck="name", limit=limit)
    except Exception:
        return []


def _lead_cohort(frm, to, scope):
    """The leads this funnel is about: created in range, inside the scope."""
    return _names("Lead", {**_df("Lead", "creation", frm, to), **_sf(scope, "Lead")})


def _prospects_of(leads):
    """Prospects reached from these leads, via the `Prospect Lead` child table.

    Returns (prospect names, {prospect: [lead, ...]}). The reverse map is what
    lets an opportunity that arrived through a prospect be attributed back to the
    lead — and so to the salesperson — that started it.
    """
    rows = _fetch_in("Prospect Lead", "lead", leads, ["parent", "lead"],
                     extra={"parenttype": "Prospect"})
    back = {}
    for r in rows:
        if r.parent and r.lead:
            back.setdefault(r.parent, []).append(r.lead)
    return sorted(back), back


def _opportunities(leads, prospects):
    """Opportunities reached from this cohort by either route, deduplicated.

    Each row is tagged with the route it arrived by. A lead linked both directly
    and through a prospect yields one row; the direct route wins the tag, because
    that is the document the opportunity actually points at.
    """
    if not _has("Opportunity"):
        return []
    fields = ["name", "status", "party_name", "transaction_date", "opportunity_from"]
    if _hascol("Opportunity", "base_opportunity_amount"):
        fields.append("base_opportunity_amount")
    if _hascol("Opportunity", "customer_name"):
        fields.append("customer_name")

    def fetch(party_type, parties):
        return _fetch_in("Opportunity", "party_name", parties, fields,
                         extra={"opportunity_from": party_type})

    out, seen = [], set()
    for route, rows in (("direct", fetch("Lead", leads)),
                        ("via_prospect", fetch("Prospect", prospects))):
        for r in rows:
            if r.name in seen:
                continue
            seen.add(r.name)
            r["route"] = route
            out.append(r)
    return out


def _sample(rows, label_of):
    return [{"name": r["name"], "label": label_of(r)} for r in rows[:SAMPLE_LIMIT]]


def cohort(frm, to, scope=None):
    """Walk one lead cohort forward. Returns stages, linkage, and the raw rows.

    `stages` is guaranteed monotonic -- every stage's count is <= the one before
    it -- because each stage is a subset of the previous one by construction, not
    by an independent query that happens to return a smaller number.
    """
    leads = _lead_cohort(frm, to, scope)
    prospects, prospect_leads = _prospects_of(leads)
    opps = _opportunities(leads, prospects)
    won = [o for o in opps if o.get("status") == "Converted"]
    lost = [o for o in opps if o.get("status") == "Lost"]

    n_leads, n_opps, n_won = len(leads), len(opps), len(won)
    via = sum(1 for o in opps if o.get("route") == "via_prospect")

    # Lead-level attribution: which leads got somewhere, regardless of route. Kept
    # as sets of *leads* rather than counts of opportunities, because "did this
    # rep's lead progress" is a question about the lead. One lead that spawned
    # three opportunities progressed once, not three times.
    in_cohort = set(leads)
    reached, closed = set(), set()
    for o in opps:
        party = o.get("party_name")
        origins = ([party] if o.get("route") == "direct"
                   else prospect_leads.get(party, []))
        for lead in origins:
            if lead not in in_cohort:
                continue
            reached.add(lead)
            if o.get("status") == "Converted":
                closed.add(lead)

    # Only the leads the drill will actually show need a readable label; fetching
    # one for every lead in the cohort is a table scan nobody reads.
    shown = leads[:SAMPLE_LIMIT]
    lead_label = {
        r["name"]: (r.get("company_name") or r.get("lead_name") or r["name"])
        for r in _fetch_in("Lead", "name", shown, ["name", "lead_name", "company_name"])
    }

    def opp_label(o):
        return o.get("customer_name") or o.get("party_name") or o["name"]

    stages = [
        {
            "key": "leads",
            "label": "Leads",
            "count": n_leads,
            "of_previous": 100.0 if n_leads else 0.0,
            "of_first": 100.0 if n_leads else 0.0,
            "dropped": n_leads - n_opps,
            "dropped_label": "never progressed",
            "sample": [{"name": n, "label": lead_label.get(n, n)} for n in leads[:SAMPLE_LIMIT]],
        },
        {
            "key": "opportunities",
            "label": "Became an opportunity",
            "count": n_opps,
            "of_previous": _pct(n_opps, n_leads),
            "of_first": _pct(n_opps, n_leads),
            "dropped": n_opps - n_won,
            "dropped_label": "lost or still open",
            # A true decomposition of this stage, so it can never widen the shape.
            "direct": n_opps - via,
            "via_prospect": via,
            "sample": _sample(opps, opp_label),
        },
        {
            "key": "won",
            "label": "Won",
            "count": n_won,
            "of_previous": _pct(n_won, n_opps),
            "of_first": _pct(n_won, n_leads),
            "dropped": 0,
            "dropped_label": "",
            "sample": _sample(won, opp_label),
        },
    ]

    return {
        "stages": stages,
        "leads": leads,
        "prospects": prospects,
        "prospect_leads": prospect_leads,
        "opportunities": opps,
        "won": won,
        "lost": lost,
        # Lead names, for per-salesperson conversion in api/command.py.
        "leads_reached_opp": sorted(reached),
        "leads_won": sorted(closed),
        "counts": {
            "leads": n_leads,
            "prospects": len(prospects),
            "opportunities": n_opps,
            "won": n_won,
            "lost": len(lost),
            "direct": n_opps - via,
            "via_prospect": via,
        },
    }
