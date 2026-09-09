"""Per-territory rollups for the Territories map.

A *read* layer, so it follows `api/crm.py`'s house style: every query is
individually guarded and degrades to zero or an empty list. A site without Sales
Invoice renders a map with no revenue, not a broken page.

## Why the ledger exists

The obvious implementation — group by `territory`, paint the result — is wrong
on this data, and quietly so. Territories form a tree (continent groups over
~196 country leaves) and records are tagged against **groups** as freely as
against countries. Measured on kaitet.local: `Middle East` carries 2,816
invoices and 94 customers, `Europe` 425, `Africa` 235. That is 35% of all
tagged invoices sitting on a territory that is not a country and has no polygon.

Those rows cannot be painted. Splitting Middle East's 2,816 invoices across its
member countries would be inventing data. So they are returned separately, in
`groups`, for the UI to account for openly. `country_total + group_total` always
reconciles to the ungrouped total — a map that silently dropped a third of the
revenue would be worse than no map at all.

Money is summed from `base_*` columns: transaction currencies here are mixed
(USD/EUR/KES/GBP), so the Company-denominated base fields are the only summable
ones, matching `api/analytics.py`.
"""

import frappe
from frappe.utils import flt

from upande_crm.api.analytics import _company_currency
from upande_crm.api.crm import _guard, _has, _hascol, _range
from upande_crm.api.territory_names import to_territory

# Metric key -> the doctype and column it is counted from. `amount` is None for
# pure counts. Order matters only for readability of the payload.
COUNT_SOURCES = (
    ("leads", "Lead", None),
    ("prospects", "Prospect", None),
    ("customers", "Customer", None),
)

# Doctypes whose date column is not `creation`.
DATE_COLS = {
    "Lead": "creation",
    "Prospect": "creation",
    "Customer": "creation",
    "Opportunity": "transaction_date",
    "Sales Invoice": "posting_date",
    "Sales Order": "transaction_date",
}

# What an opportunity is worth, in company currency.
#
# `base_opportunity_amount` is the documented field and is what other sites
# populate, but every one of the 61 opportunities here has it at zero while
# `base_total` (summed from the items table) carries the real 325k. Preferring
# whichever is non-zero means neither kind of site reads as empty.
OPP_VALUE = "if(ifnull(base_opportunity_amount, 0) > 0, base_opportunity_amount, ifnull(base_total, 0))"
OPP_VALUE_COLS = ("base_opportunity_amount", "base_total")

# Every numeric field a territory row carries, so callers can rely on the shape
# even when a doctype is missing and the query never ran.
ZERO = {
    "leads": 0,
    "prospects": 0,
    "customers": 0,
    "opps": 0,
    "opp_value": 0.0,
    "revenue": 0.0,
    "claims": 0,
    "claim_stems": 0,
    "claim_cost": 0.0,
    "consignees": 0,
}


def _blank(name):
    return {"territory": name, **ZERO}


def _accumulate(bucket, name, key, value):
    bucket.setdefault(name, _blank(name))[key] = value


def _group_by_territory(doctype, frm, to, agg=None, requires=(), extra=""):
    """`[(territory, count_or_sum)]` grouped by territory, or [] if unavailable.

    `agg` is a SQL expression to SUM; None counts rows instead. `requires` names
    the columns that expression needs, so a site missing one gets an empty list
    rather than a SQL error. The date column is looked up per doctype and simply
    omitted if the table does not have it, so an unusual schema narrows nothing
    rather than raising.
    """
    if not _has(doctype) or not _hascol(doctype, "territory"):
        return []
    if any(not _hascol(doctype, col) for col in requires):
        return []

    date_col = DATE_COLS.get(doctype, "creation")
    where, params = ["ifnull(territory, '') <> ''"], []
    if _hascol(doctype, date_col):
        where.append(f"`{date_col}` between %s and %s")
        params += [frm, to]
    if _hascol(doctype, "docstatus"):
        where.append("docstatus < 2")
    if extra:
        where.append(extra)

    what = f"coalesce(sum({agg}), 0)" if agg else "count(*)"
    try:
        return frappe.db.sql(
            f"""select territory, {what} v from `tab{doctype}`
                where {" and ".join(where)} group by territory""",
            params,
            as_list=True,
        )
    except Exception:
        frappe.clear_last_message()
        return []


def _submitted(doctype):
    """`docstatus=1` for submittable money documents, else no extra clause."""
    return "docstatus = 1" if _hascol(doctype, "docstatus") else ""


@frappe.whitelist()
def crm_territory_map(date_from=None, date_to=None):
    """Every territory that carries data in the window, split country vs group.

    One grouped query per source doctype — six in total, not one per territory.
    """
    _guard()
    frm, to = _range(date_from, date_to)

    bucket = {}
    for key, doctype, _ in COUNT_SOURCES:
        for name, value in _group_by_territory(doctype, frm, to):
            _accumulate(bucket, name, key, int(value or 0))

    for name, value in _group_by_territory("Opportunity", frm, to):
        _accumulate(bucket, name, "opps", int(value or 0))
    for name, value in _group_by_territory(
        "Opportunity", frm, to, agg=OPP_VALUE, requires=OPP_VALUE_COLS
    ):
        _accumulate(bucket, name, "opp_value", flt(value))

    src = "Sales Invoice" if _has("Sales Invoice") else "Sales Order"
    for name, value in _group_by_territory(
        src, frm, to, agg="base_grand_total", requires=("base_grand_total",), extra=_submitted(src)
    ):
        _accumulate(bucket, name, "revenue", flt(value))

    claims, claims_orphaned = _claims_by_territory(frm, to)
    for name, row in claims.items():
        for key, value in row.items():
            _accumulate(bucket, name, key, value)

    consignees, consignees_orphaned = _consignees_by_territory()
    for name, value in consignees.items():
        _accumulate(bucket, name, "consignees", value)

    # A territory's kind decides whether it can be painted. Read once for the
    # names actually present rather than loading the whole 206-row tree.
    groups = _group_flags(list(bucket))

    countries, regional = [], []
    for name, row in bucket.items():
        (regional if groups.get(name) else countries).append(row)

    countries.sort(key=lambda r: -r["revenue"])
    regional.sort(key=lambda r: -r["revenue"])

    return {
        "currency": _company_currency(),
        "date_from": frm,
        "date_to": to,
        "territories": countries,
        # Real data that belongs to no country. The UI must show this; see the
        # module docstring for why it cannot be distributed onto the map.
        "groups": regional,
        "totals": _totals(countries, regional),
        # Rows that resolved to no territory at all. Claims name their customer
        # in free text and consignees name a country in a different vocabulary,
        # so neither joins cleanly for every row; what did not join is counted
        # here rather than dropped. The UI shows it next to the regional ledger.
        "orphaned": {"claims": claims_orphaned, "consignees": consignees_orphaned},
    }


def _claims_by_territory(frm, to):
    """Quality claims per territory, and how many could not be placed.

    `Customer Feedback.customer_company` is free text, not a Link — so a claim
    reaches a territory only by matching that text to a Customer and reading its
    territory. On kaitet.local 85% of 3,378 claims match a Customer name exactly;
    the rest name a company that was never created as one (FLAMINGO UK, for
    instance). Those are returned as a count, not silently discarded: a claims
    map that showed 85% of the claims while implying it showed all of them would
    misstate where the trouble is.
    """
    if not _has("Customer Feedback") or not _has("Customer"):
        return {}, 0

    try:
        rows = frappe.db.sql(
            """select cu.territory, count(*) n,
                      coalesce(sum(cf.total_stems_claimed), 0) stems,
                      coalesce(sum(cf.total_claim_cost), 0) cost
               from `tabCustomer Feedback` cf
               join `tabCustomer` cu on cu.name = cf.customer_company
               where cf.feedback_date between %s and %s
                 and ifnull(cu.territory, '') <> ''
               group by cu.territory""",
            (frm, to),
            as_dict=True,
        )
        orphaned = frappe.db.sql(
            """select count(*) from `tabCustomer Feedback` cf
               left join `tabCustomer` cu
                 on cu.name = cf.customer_company and ifnull(cu.territory, '') <> ''
               where cf.feedback_date between %s and %s and cu.name is null""",
            (frm, to),
        )[0][0]
    except Exception:
        frappe.clear_last_message()
        return {}, 0

    return (
        {
            r.territory: {
                "claims": int(r.n or 0),
                "claim_stems": int(r.stems or 0),
                "claim_cost": flt(r.cost),
            }
            for r in rows
        },
        int(orphaned or 0),
    )


def _consignees_by_territory():
    """Consignees per territory, and how many name a place with no Territory.

    Consignee carries a free `country` string from the ISO-3166 vocabulary
    ("Russian Federation") rather than Territory's common-name one ("Russia"),
    so the alias table in `territory_names` does the translation. Deliberately
    not date-filtered: a consignee is a standing relationship, not an event, and
    scoping it to the dashboard's window would empty the layer for any short
    range.
    """
    if not _has("Consignee") or not _hascol("Consignee", "country"):
        return {}, 0

    try:
        rows = frappe.db.sql(
            """select country, count(*) n from `tabConsignee`
               where ifnull(country, '') <> '' group by country""",
            as_dict=True,
        )
    except Exception:
        frappe.clear_last_message()
        return {}, 0

    known = {t.name for t in frappe.get_all("Territory", fields=["name"])}
    out, orphaned = {}, 0
    for r in rows:
        name = to_territory(r.country)
        if name and name in known:
            out[name] = out.get(name, 0) + int(r.n or 0)
        else:
            orphaned += int(r.n or 0)
    return out, orphaned


def _group_flags(names):
    """`{name: is_group}` for the territories present, defaulting to leaf."""
    if not names or not _has("Territory"):
        return {}
    try:
        rows = frappe.get_all(
            "Territory", filters={"name": ["in", names]}, fields=["name", "is_group"]
        )
        return {r.name: bool(r.is_group) for r in rows}
    except Exception:
        frappe.clear_last_message()
        return {}


def _totals(countries, regional):
    """Country and regional subtotals, plus their sum.

    The UI reconciles against these: if `mapped` and `regional` do not add up to
    `all`, something was dropped and the map is lying.
    """
    def add(rows):
        out = dict(ZERO)
        for r in rows:
            for k in ZERO:
                out[k] += r[k]
        return out

    mapped, region = add(countries), add(regional)
    return {
        "mapped": mapped,
        "regional": region,
        "all": {k: mapped[k] + region[k] for k in ZERO},
    }


@frappe.whitelist()
def crm_territory_detail(territory, date_from=None, date_to=None, limit=6):
    """Deeper intel for one territory, fetched only when a country is pinned.

    Kept out of `crm_territory_map` so hovering costs nothing: the map payload
    already holds every number the hover preview needs.
    """
    _guard()
    if not territory:
        return {}
    frm, to = _range(date_from, date_to)
    limit = min(int(limit or 6), 25)

    return {
        "territory": territory,
        "currency": _company_currency(),
        "top_accounts": _top_accounts(territory, frm, to, limit),
        "stages": _stage_split(territory, frm, to),
        "recent": _recent(territory, limit),
        "trend": _trend(territory, frm, to),
        "flowers": _top_flowers(territory, frm, to, limit),
        "claim_types": _claim_types(territory, frm, to),
        "claim_reasons": _claim_reasons(territory, frm, to),
        "staff": _staff(territory, frm, to, limit),
        "consignees": _consignees(territory, limit),
        "fulfilment": _fulfilment(territory, frm, to),
    }


def _fulfilment(territory, frm, to):
    """How much of this territory's order book got picked and packed.

    Only the middle of the chain is here, because only the middle is joined.
    Measured on kaitet.local:

        Harvest              19,566 rows, and no forward link of any kind —
                             it records a bucket, a greenhouse and a variety,
                             never an order or a customer
        Farm Pack List        8,612 / 8,614 carry a Sales Order  (100%)
        Order Pick List      13,807 / 13,807 carry a Sales Order (100%)
        Dispatch Form             1 / 126 carries a Sales Order   (1%)

    So "harvest to dispatch" cannot be drawn: the first stage joins to nothing
    and the last is essentially unused. Pretending otherwise would mean a funnel
    whose top and bottom are guesses. `gaps` names the missing stages so the UI
    can say which parts of the chain it is not showing.
    """
    out = {"stages": [], "gaps": []}

    if _has("Sales Order") and _hascol("Sales Order", "territory"):
        for label, doctype, join_col in (
            ("Picked", "Order Pick List", "sales_order"),
            ("Packed", "Farm Pack List", "custom_sales_order"),
        ):
            if not _has(doctype) or not _hascol(doctype, join_col):
                continue
            try:
                n = frappe.db.sql(
                    f"""select count(distinct so.name) from `tab{doctype}` x
                        join `tabSales Order` so on so.name = x.`{join_col}`
                        where so.territory = %s and so.docstatus = 1
                          and so.transaction_date between %s and %s""",
                    (territory, frm, to),
                )[0][0]
            except Exception:
                frappe.clear_last_message()
                continue
            out["stages"].append({"label": label, "orders": int(n or 0)})

        try:
            ordered = frappe.db.sql(
                """select count(*) from `tabSales Order`
                   where territory = %s and docstatus = 1
                     and transaction_date between %s and %s""",
                (territory, frm, to),
            )[0][0]
            out["stages"].insert(0, {"label": "Ordered", "orders": int(ordered or 0)})
        except Exception:
            frappe.clear_last_message()

    if _has("Harvest"):
        out["gaps"].append("Harvest records no order or customer, so it cannot be traced forward.")
    if _has("Dispatch Form") and _hascol("Dispatch Form", "custom_sales_order"):
        try:
            tot = frappe.db.count("Dispatch Form")
            linked = frappe.db.sql(
                "select count(*) from `tabDispatch Form` where ifnull(custom_sales_order,'') <> ''"
            )[0][0]
            if tot and linked / tot < 0.5:
                out["gaps"].append(
                    f"Dispatch Form links to an order on {linked} of {tot} records, too few to chart."
                )
        except Exception:
            frappe.clear_last_message()

    return out


# Item groups that are actual product, as opposed to freight, services and the
# raw-material codes the packhouse books against. Without this filter "top
# flowers" is led by `Raw Material` codes AB/AA/NH, which are grades rather than
# varieties and tell a sales reader nothing.
FLOWER_GROUPS = ("Spray Roses", "Standard Roses", "Summer Flowers", "Chrysanthemums")


def _top_flowers(territory, frm, to, limit):
    """Best-selling varieties in this territory.

    Lines with no `item_code` are excluded and counted separately. They are not
    a rounding error: on this site they are the single largest block of invoice
    value, so a varieties list that quietly absorbed them would be wrong, and one
    that ignored them without saying so would overstate how complete it is.
    """
    if not _has("Sales Invoice Item") or not _hascol("Sales Invoice", "territory"):
        return {"rows": [], "unattributed": 0.0}
    try:
        rows = frappe.db.sql(
            """select sii.item_code label, i.item_group grp,
                      coalesce(sum(sii.base_amount), 0) amount,
                      coalesce(sum(sii.qty), 0) qty
               from `tabSales Invoice Item` sii
               join `tabSales Invoice` si on si.name = sii.parent
               left join `tabItem` i on i.name = sii.item_code
               where si.territory = %s and si.docstatus = 1
                 and si.posting_date between %s and %s
                 and ifnull(sii.item_code, '') <> ''
               group by label, grp order by amount desc limit %s""",
            (territory, frm, to, limit),
            as_dict=True,
        )
        blank = frappe.db.sql(
            """select coalesce(sum(sii.base_amount), 0)
               from `tabSales Invoice Item` sii
               join `tabSales Invoice` si on si.name = sii.parent
               where si.territory = %s and si.docstatus = 1
                 and si.posting_date between %s and %s
                 and ifnull(sii.item_code, '') = ''""",
            (territory, frm, to),
        )[0][0]
    except Exception:
        frappe.clear_last_message()
        return {"rows": [], "unattributed": 0.0}
    return {"rows": rows, "unattributed": flt(blank)}


def _claim_types(territory, frm, to):
    """Claims in this territory by claim type — Claimed, Rejected, Returns."""
    if not _has("Customer Feedback") or not _has("Customer"):
        return []
    try:
        return frappe.db.sql(
            """select coalesce(nullif(cf.claim_type, ''), 'Unclassified') label,
                      count(*) count,
                      coalesce(sum(cf.total_claim_cost), 0) amount,
                      coalesce(sum(cf.total_stems_claimed), 0) stems
               from `tabCustomer Feedback` cf
               join `tabCustomer` cu on cu.name = cf.customer_company
               where cu.territory = %s and cf.feedback_date between %s and %s
               group by label order by count desc""",
            (territory, frm, to),
            as_dict=True,
        )
    except Exception:
        frappe.clear_last_message()
        return []


def _claim_reasons(territory, frm, to):
    """Why claims were raised, from the itemised child table.

    Returns `coverage` alongside the rows because this field is barely populated:
    6 of 3,378 claims carry any itemised reason on this site. The UI states that
    coverage rather than presenting a three-row list as the shape of quality
    problems in a market. The query is written for the day it is filled in.
    """
    empty = {"rows": [], "covered": 0, "total": 0}
    if not _has("Customer Feedback Item") or not _has("Customer"):
        return empty
    try:
        rows = frappe.db.sql(
            """select coalesce(nullif(cfi.reason_category, ''), 'Unclassified') label,
                      coalesce(nullif(cfi.reason, ''), '') detail,
                      count(*) count,
                      coalesce(sum(cfi.claim_cost), 0) amount
               from `tabCustomer Feedback Item` cfi
               join `tabCustomer Feedback` cf on cf.name = cfi.parent
               join `tabCustomer` cu on cu.name = cf.customer_company
               where cu.territory = %s and cf.feedback_date between %s and %s
               group by label, detail order by count desc limit 8""",
            (territory, frm, to),
            as_dict=True,
        )
        covered, total = frappe.db.sql(
            """select count(distinct cfi.parent), count(distinct cf.name)
               from `tabCustomer Feedback` cf
               join `tabCustomer` cu on cu.name = cf.customer_company
               left join `tabCustomer Feedback Item` cfi on cfi.parent = cf.name
               where cu.territory = %s and cf.feedback_date between %s and %s""",
            (territory, frm, to),
        )[0]
    except Exception:
        frappe.clear_last_message()
        return empty
    return {"rows": rows, "covered": int(covered or 0), "total": int(total or 0)}


def _staff(territory, frm, to, limit):
    """Who is actually in contact with customers in this territory.

    Not `Sales Team`: that child table holds 28 rows on this site and every one
    of them is the same person, so it answers nothing. Correspondence does — the
    sender of an outgoing email is a real, per-account signal. See
    `api/correspondence.py`, which owns the join; this only narrows it to one
    territory.
    """
    from upande_crm.api.correspondence import staff_for_territory

    return staff_for_territory(territory, frm, to, limit)


def _consignees(territory, limit):
    """Consignees whose country resolves to this territory."""
    if not _has("Consignee"):
        return []
    aliases = [c for c, t in _alias_pairs() if t == territory]
    candidates = list({territory, *aliases})
    try:
        return frappe.get_all(
            "Consignee",
            filters={"country": ["in", candidates]},
            fields=["name as label", "customer"],
            limit=limit,
            order_by="name",
        )
    except Exception:
        frappe.clear_last_message()
        return []


def _alias_pairs():
    from upande_crm.api.territory_names import COUNTRY_ALIASES

    return list(COUNTRY_ALIASES.items())


def _top_accounts(territory, frm, to, limit):
    """Highest-billing customers in this territory."""
    src = "Sales Invoice" if _has("Sales Invoice") else "Sales Order"
    if not _has(src) or not _hascol(src, "territory") or not _hascol(src, "customer"):
        return []
    date_col = DATE_COLS.get(src, "posting_date")
    try:
        return frappe.db.sql(
            f"""select customer label, coalesce(sum(base_grand_total), 0) amount
                from `tab{src}`
                where territory = %s and docstatus = 1
                  and `{date_col}` between %s and %s
                group by customer order by amount desc limit %s""",
            (territory, frm, to, limit),
            as_dict=True,
        )
    except Exception:
        frappe.clear_last_message()
        return []


def _stage_split(territory, frm, to):
    """Open opportunities by sales stage."""
    if not _has("Opportunity") or not _hascol("Opportunity", "sales_stage"):
        return []
    try:
        return frappe.db.sql(
            f"""select coalesce(nullif(sales_stage, ''), 'Unstaged') label,
                       count(*) count,
                       coalesce(sum({OPP_VALUE}), 0) amount
                from `tabOpportunity`
                where territory = %s and docstatus < 2
                  and transaction_date between %s and %s
                group by label order by amount desc, count desc""",
            (territory, frm, to),
            as_dict=True,
        )
    except Exception:
        frappe.clear_last_message()
        return []


def _recent(territory, limit):
    """Latest leads and opportunities, newest first, as one merged stream."""
    out = []
    for doctype, title_col in (("Lead", "lead_name"), ("Opportunity", "party_name")):
        if not _has(doctype) or not _hascol(doctype, "territory"):
            continue
        try:
            rows = frappe.get_all(
                doctype,
                filters={"territory": territory},
                fields=["name", f"{title_col} as title", "status", "modified"],
                order_by="modified desc",
                limit=limit,
            )
        except Exception:
            frappe.clear_last_message()
            continue
        out += [{**r, "doctype": doctype} for r in rows]

    out.sort(key=lambda r: r.get("modified") or "", reverse=True)
    return out[:limit]


def _trend(territory, frm, to):
    """Monthly revenue across the window, oldest first."""
    src = "Sales Invoice" if _has("Sales Invoice") else "Sales Order"
    if not _has(src) or not _hascol(src, "territory"):
        return []
    date_col = DATE_COLS.get(src, "posting_date")
    try:
        return frappe.db.sql(
            f"""select date_format(`{date_col}`, '%%Y-%%m') label,
                       coalesce(sum(base_grand_total), 0) amount
                from `tab{src}`
                where territory = %s and docstatus = 1
                  and `{date_col}` between %s and %s
                group by label order by label""",
            (territory, frm, to),
            as_dict=True,
        )
    except Exception:
        frappe.clear_last_message()
        return []
