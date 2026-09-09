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
    }


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
    }


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
