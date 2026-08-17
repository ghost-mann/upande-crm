"""Flowers clients are asking for, as distinct from flowers they bought.

Everything else in this app that counts a variety counts a *Sales Order Item* —
`command.py`'s top sellers, its movers band, its per-customer matrix. That is
revenue, and revenue is history. Nothing answered the forward question: what are
accounts asking for that has not become an order yet?

Demand is read from the item lines on documents that are still open:

    Opportunity Item   parent docstatus < 2, status not Lost/Closed
    Quotation Item     parent submitted,     status not Lost/Expired/Cancelled

Both are wants. A Sales Order is no longer a want, so the order book is
deliberately absent — including it would just reproduce the top-sellers card with
a different title.

## This card starts nearly empty, and says so

Measured before it was built: 6 Opportunity Item rows and 48 Quotation Item rows
on this site, against 43,714 Sales Order Item rows. Reps raise opportunities
without lines and orders are entered directly, so there is very little forward
demand recorded anywhere.

That is a real finding, not a broken query, and the payload carries
`sources.opportunity_lines` / `sources.quotation_lines` so the UI can state the
sample size instead of rendering a blank panel that reads as a bug. The lines
entered when a lead is converted (see `api/leads.py`) are what fill this in.

Money is summed from `base_amount` only. Transaction currencies on this site are
mixed, so company-currency columns are the only summable ones — the same rule
`command.py` states and follows.

A read module: every query is individually guarded and degrades to empty.
"""

import frappe
from frappe.utils import cint, flt

from upande_crm.api.analytics import _company_currency
from upande_crm.api.crm import _guard, _has, _hascol, _range

# Varieties on the card, and accounts listed under each.
DEMAND_LIMIT = 8
CLIENT_LIMIT = 6

# Parent states that mean the want is gone rather than outstanding.
DEAD_OPPORTUNITY = ("Lost", "Closed")
DEAD_QUOTATION = ("Lost", "Expired", "Cancelled")


# `lines` is reserved in MariaDB (LOAD DATA ... LINES TERMINATED BY), so the line
# tally is aliased `line_count`. Aliasing it `lines` made both demand queries fail
# silently and the card report "no demand" on a site that had some.


def _sql(query, params=()):
    try:
        return frappe.db.sql(query, params, as_dict=True) or []
    except Exception:
        return []


def _quoted(values):
    return ", ".join(frappe.db.escape(v) for v in values)


def _opportunity_lines(frm, to, customer=None):
    """[(item_code, client, qty, amount)] from open opportunities."""
    if not (_has("Opportunity Item") and _has("Opportunity")):
        return []
    if not _hascol("Opportunity Item", "item_code"):
        return []
    # `customer_name` is the readable party on an Opportunity whichever doctype
    # `party_name` points at, so it is the client label; `party_name` is the join
    # key and the fallback.
    cond = ""
    params = [frm, to]
    if customer:
        cond = " and (o.party_name = %s or o.customer_name = %s)"
        params += [customer, customer]
    return _sql(
        f"""select oi.item_code k,
                   coalesce(nullif(o.customer_name, ''), o.party_name) client,
                   coalesce(sum(oi.qty), 0) qty,
                   coalesce(sum(oi.base_amount), 0) amount,
                   count(*) line_count
            from `tabOpportunity Item` oi
            join `tabOpportunity` o on o.name = oi.parent
            where o.docstatus < 2
              and coalesce(o.status, '') not in ({_quoted(DEAD_OPPORTUNITY)})
              and o.transaction_date between %s and %s{cond}
            group by oi.item_code, client""",
        tuple(params),
    )


def _quotation_lines(frm, to, customer=None):
    """[(item_code, client, qty, amount)] from live quotations."""
    if not (_has("Quotation Item") and _has("Quotation")):
        return []
    if not _hascol("Quotation Item", "item_code"):
        return []
    cond = ""
    params = [frm, to]
    if customer:
        cond = " and (q.party_name = %s or q.customer_name = %s)"
        params += [customer, customer]
    return _sql(
        f"""select qi.item_code k,
                   coalesce(nullif(q.customer_name, ''), q.party_name) client,
                   coalesce(sum(qi.qty), 0) qty,
                   coalesce(sum(qi.base_amount), 0) amount,
                   count(*) line_count
            from `tabQuotation Item` qi
            join `tabQuotation` q on q.name = qi.parent
            where q.docstatus = 1
              and coalesce(q.status, '') not in ({_quoted(DEAD_QUOTATION)})
              and q.transaction_date between %s and %s{cond}
            group by qi.item_code, client""",
        tuple(params),
    )


def _item_labels(codes):
    """{item_code: item_name}, falling back to the code."""
    if not codes or not _has("Item"):
        return {}
    try:
        rows = frappe.get_all("Item", filters={"name": ["in", list(codes)]},
                              fields=["name", "item_name"], limit=0)
    except Exception:
        return {}
    return {r.name: (r.item_name or r.name) for r in rows}


@frappe.whitelist()
def crm_demand(date_from=None, date_to=None, customer=None):
    """Varieties clients are asking for, and who is asking."""
    _guard()
    frm, to = _range(date_from, date_to)

    opp_rows = _opportunity_lines(frm, to, customer)
    quo_rows = _quotation_lines(frm, to, customer)

    varieties = {}
    for source, rows in (("opportunity", opp_rows), ("quotation", quo_rows)):
        for r in rows:
            if not r.get("k"):
                continue
            v = varieties.setdefault(r["k"], {
                "qty": 0.0, "amount": 0.0, "clients": {},
                "opportunity_qty": 0.0, "quotation_qty": 0.0,
            })
            qty, amount = flt(r.get("qty")), flt(r.get("amount"))
            v["qty"] += qty
            v["amount"] += amount
            v[f"{source}_qty"] += qty
            client = r.get("client") or "Unnamed"
            c = v["clients"].setdefault(client, {"qty": 0.0, "amount": 0.0})
            c["qty"] += qty
            c["amount"] += amount

    labels = _item_labels(varieties.keys())
    ranked = sorted(varieties.items(), key=lambda kv: (-kv[1]["qty"], -kv[1]["amount"]))

    rows = []
    for code, v in ranked[:DEMAND_LIMIT]:
        clients = sorted(v["clients"].items(), key=lambda kv: -kv[1]["qty"])
        rows.append({
            "key": code,
            "label": labels.get(code, code),
            "qty": v["qty"],
            "amount": v["amount"],
            "clients": len(v["clients"]),
            "from_opportunities": v["opportunity_qty"],
            "from_quotations": v["quotation_qty"],
            "top_clients": [
                {"client": name, "qty": c["qty"], "amount": c["amount"]}
                for name, c in clients[:CLIENT_LIMIT]
            ],
        })

    all_clients = {c for v in varieties.values() for c in v["clients"]}
    return {
        "currency": _company_currency(),
        "range": {"from": frm, "to": to},
        "rows": rows,
        "totals": {
            "varieties": len(varieties),
            "clients": len(all_clients),
            "qty": sum(flt(v["qty"]) for v in varieties.values()),
            "amount": sum(flt(v["amount"]) for v in varieties.values()),
        },
        # Sample size, so the card can say why it is thin rather than look broken.
        "sources": {
            "opportunity_lines": sum(cint(r.get("line_count")) for r in opp_rows),
            "quotation_lines": sum(cint(r.get("line_count")) for r in quo_rows),
        },
    }
