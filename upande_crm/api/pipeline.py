"""Purpose-built sales-pipeline analytics.

Deliberately **not** a report viewer. `api/reports.py` surfaces ERPNext's own
reports faithfully, which makes it a good catalogue and a poor analytics story:
those reports return dense grids, almost none declare a summary or a chart, and
most are empty over a short window. Re-skinning a nineteen-column grid does not
produce insight. This module asks its own questions instead.

## Every metric here is backed by a measured field

Field population on this site was measured before anything was charted, because a
chart over a 0%-populated column is a permanently blank chart:

    charted        Lead.source 79%, territory 100%, qualification_status 100%,
                   market_segment 100%, Opportunity.sales_stage/status/
                   probability 100%, Quotation.status/base_grand_total 100%,
                   Sales Order per_delivered/per_billed/territory 100%
    NOT charted    Lead.industry 0%, Lead.request_type 0%, campaign_name 3%,
                   Opportunity.expected_closing 3%, order_lost_reason 0%,
                   Sales Order.source 0%, sales_partner 0%, and the lost-reason
                   detail tables, which hold 0 rows

**A caveat that cost a rewrite:** a population check of the form
`coalesce(col,'') not in ('','0')` reports a numeric column as populated when every
value is `0.000000`. Measured properly, **`opportunity_amount` is zero on all 59
opportunities** — so pipeline value and any probability-weighted value would be
permanently-zero tiles. They are not charted. `probability` is genuinely populated
(all 59, averaging 81%), so it is charted on its own, and money comes from
Quotation and Sales Order totals, which are real.

## Why the funnel is cohort-based, and stops where the data stops

Counting each stage independently — what the Overview funnel does — produces
nonsense when the stages are not linked: it reports 4 leads and 1,429 orders in
the same funnel, as though orders were 300x the leads that produced them.

The document chain on this site, measured:

    Lead -> Opportunity        45 linked        usable
    Opportunity -> Quotation    3 linked        too thin to rate
    Quotation -> Sales Order    0 linked        chain not used at all
    submitted orders        10,625

So orders are raised directly, not from quotations. A lead-to-cash funnel is
therefore **not computable** here, and presenting "0% quote-to-order conversion"
would report a process fact as a performance failure. The funnel covers
Lead -> Opportunity -> Won, where the linkage is real, and the order book is
reported separately with the gap stated. `linkage` in the payload carries those
counts so the UI can say so rather than imply a funnel that does not exist.

A read layer: every query is individually guarded and degrades to empty.
"""

import frappe
from frappe.utils import flt, getdate

from upande_crm.api.crm import (
    _company_currency,
    _count,
    _df,
    _dw,
    _group,
    _guard,
    _has,
    _hascol,
    _range,
)

# Age buckets for open records, in days.
AGE_BUCKETS = ((0, 7, "0-7d"), (7, 30, "7-30d"), (30, 90, "30-90d"), (90, None, "90d+"))


def _scope(customer):
    if not customer:
        return None
    from upande_crm.api.scope import customer_scope

    return customer_scope(customer)


def _sf(scope, doctype):
    if scope is None:
        return {}
    from upande_crm.api.scope import in_scope

    return in_scope(scope, doctype)


def _sw(scope, doctype):
    if scope is None:
        return ""
    from upande_crm.api.scope import scope_sql

    return scope_sql(scope, doctype)


def _rows(sql, params=()):
    try:
        return frappe.db.sql(sql, params, as_dict=True)
    except Exception:
        return []


def _one(sql, params=(), default=0):
    try:
        row = frappe.db.sql(sql, params)
        return row[0][0] if row and row[0] and row[0][0] is not None else default
    except Exception:
        return default


def _pct(part, whole):
    return round(part / whole * 100, 1) if whole else 0.0


def _median(values):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else round((vals[mid - 1] + vals[mid]) / 2, 1)


def _age_buckets(doctype, date_col, where):
    """Open-record ages, bucketed. `where` already includes its `where` keyword."""
    if not _has(doctype) or not _hascol(doctype, date_col):
        return []
    out = []
    for low, high, label in AGE_BUCKETS:
        cond = f"datediff(curdate(), `{date_col}`) >= {low}"
        if high is not None:
            cond += f" and datediff(curdate(), `{date_col}`) < {high}"
        joiner = " and " if where else " where "
        out.append({"label": label,
                    "count": _one(f"select count(*) from `tab{doctype}` {where}{joiner}{cond}")})
    return out


# ---------------------------------------------------------------- funnel
@frappe.whitelist()
def crm_analytics_funnel(date_from=None, date_to=None, customer=None):
    _guard()
    frm, to = _range(date_from, date_to)
    scope = _scope(customer)
    ld = {**_df("Lead", "creation", frm, to), **_sf(scope, "Lead")}

    leads = frappe.get_all("Lead", filters=ld, pluck="name", limit=0) if _has("Lead") else []
    lead_names = list(leads)

    # --- forward walk: what became of these leads
    opps = []
    if lead_names and _has("Opportunity"):
        opps = frappe.get_all(
            "Opportunity",
            filters={"opportunity_from": "Lead", "party_name": ["in", lead_names]},
            fields=["name", "status", "transaction_date", "party_name",
                    "base_opportunity_amount", "probability"],
            limit=0,
        )
    opp_names = [o.name for o in opps]
    won = [o for o in opps if o.status == "Converted"]
    lost = [o for o in opps if o.status == "Lost"]

    quotes = []
    if opp_names and _has("Quotation") and _hascol("Quotation", "opportunity"):
        quotes = frappe.get_all("Quotation", filters={"opportunity": ["in", opp_names]},
                                fields=["name", "status", "base_grand_total"], limit=0)

    customers = []
    if lead_names and _has("Customer") and _hascol("Customer", "lead_name"):
        customers = frappe.get_all("Customer", filters={"lead_name": ["in", lead_names]},
                                   fields=["name", "creation", "lead_name"], limit=0)

    n_leads = len(lead_names)
    # Only stages that are genuinely on the path, so the funnel narrows
    # monotonically. Quotations are NOT a stage here: 3 of 30 opportunities have
    # one while 20 were won, so inserting it would draw a funnel that narrows to 3
    # and then widens back to 20 — visibly wrong, and wrong about the process. It
    # is reported under `linkage` as the aside it actually is.
    stages = [
        {"key": "leads", "label": "Leads", "count": n_leads,
         "of_previous": 100.0 if n_leads else 0.0, "of_first": 100.0 if n_leads else 0.0},
        {"key": "opportunities", "label": "Became an opportunity", "count": len(opps),
         "of_previous": _pct(len(opps), n_leads), "of_first": _pct(len(opps), n_leads)},
        {"key": "won", "label": "Won", "count": len(won),
         "of_previous": _pct(len(won), len(opps)), "of_first": _pct(len(won), n_leads)},
    ]

    # --- velocity, from real timestamps only
    lead_created = {}
    if lead_names:
        for r in _rows("select name, creation from tabLead where name in %(n)s",
                       {"n": lead_names}) or []:
            lead_created[r.name] = r.creation
    to_opp_days = []
    for o in opps:
        created = lead_created.get(o.party_name)
        if created and o.transaction_date:
            try:
                to_opp_days.append((getdate(o.transaction_date) - getdate(created)).days)
            except Exception:
                pass
    to_customer_days = []
    for c in customers:
        created = lead_created.get(c.lead_name)
        if created and c.creation:
            try:
                to_customer_days.append((getdate(c.creation) - getdate(created)).days)
            except Exception:
                pass

    # --- the order book, which the funnel cannot reach
    order_filter = "docstatus=1 and transaction_date between %s and %s"
    order_params = [frm, to]
    if customer:
        order_filter += " and customer=%s"
        order_params.append(customer)
    orders = _one(f"select count(*) from `tabSales Order` where {order_filter}",
                  tuple(order_params))
    order_value = flt(_one(
        f"select coalesce(sum(base_grand_total),0) from `tabSales Order` where {order_filter}",
        tuple(order_params)))
    from_quote = 0
    if _has("Sales Order Item") and _hascol("Sales Order Item", "prevdoc_docname"):
        from_quote = _one(
            f"""select count(distinct so.name) from `tabSales Order` so
                join `tabSales Order Item` soi on soi.parent = so.name
                where {order_filter.replace('transaction_date', 'so.transaction_date').replace('docstatus', 'so.docstatus').replace('customer', 'so.customer')}
                  and coalesce(soi.prevdoc_docname, '') != ''""",
            tuple(order_params))

    return {
        "currency": _company_currency(),
        "stages": stages,
        "kpis": {
            "leads": n_leads,
            "opportunities": len(opps),
            "won": len(won),
            "lost": len(lost),
            "win_rate": _pct(len(won), len(won) + len(lost)),
            "lead_to_opp_rate": _pct(len(opps), n_leads),
            "customers_created": len(customers),
            "quotations": len(quotes),
        },
        "velocity": {
            "lead_to_opportunity_days": _median(to_opp_days),
            "lead_to_customer_days": _median(to_customer_days),
            "samples": {"lead_to_opportunity": len(to_opp_days),
                        "lead_to_customer": len(to_customer_days)},
        },
        # The linkage facts, so the UI can state why the funnel stops where it does
        # instead of implying a stage conversion it cannot measure.
        "linkage": {
            "opp_from_lead": len(opps),
            "quote_from_opp": len(quotes),
            "orders": orders,
            "orders_from_quotation": from_quote,
            "order_value": order_value,
            "chain_broken_after": "Opportunity" if orders and not from_quote else None,
        },
    }


# ---------------------------------------------------------------- leads
@frappe.whitelist()
def crm_analytics_leads(date_from=None, date_to=None, customer=None):
    _guard()
    frm, to = _range(date_from, date_to)
    scope = _scope(customer)
    w = _dw("Lead", "creation", frm, to, base=_sw(scope, "Lead"))
    ld = {**_df("Lead", "creation", frm, to), **_sf(scope, "Lead")}
    total = _count("Lead", ld)

    # Conversion by source: of the leads from each source, how many produced an
    # opportunity. `source` is 79% populated, so this is worth charting; campaign
    # (3%) is not, and is deliberately absent.
    by_source = []
    if _has("Lead") and _hascol("Lead", "source"):
        # Every column is alias-qualified: `_dw` emits an unaliased `creation`,
        # which is ambiguous once the join is present and made this return nothing.
        lw = f"l.creation between '{frm}' and '{to}'"
        if scope is not None:
            inner = _sw(scope, "Lead")
            lw += " and " + (inner.replace("`name`", "l.`name`") if inner else "1=1")
        rows = _rows(
            f"""select coalesce(nullif(l.source,''),'Unknown') label, count(*) leads,
                       coalesce(sum(case when o.party_name is not null then 1 else 0 end),0) converted
                from `tabLead` l
                left join (select distinct party_name from `tabOpportunity`
                           where opportunity_from='Lead') o on o.party_name = l.name
                where {lw}
                group by label order by leads desc limit 12""")
        by_source = [{"label": r.label, "leads": int(r.leads or 0),
                      "converted": int(r.converted or 0),
                      "rate": _pct(int(r.converted or 0), int(r.leads or 0))} for r in rows]

    open_where = _dw("Lead", "creation", frm, to,
                     base=" and ".join(f for f in [
                         _sw(scope, "Lead"),
                         "status not in ('Converted','Lost','Do Not Contact')",
                     ] if f))

    return {
        "kpis": {
            "total": total,
            "converted": _count("Lead", {**ld, "status": "Converted"}),
            "lost": _count("Lead", {**ld, "status": "Lost"}),
            "with_source": _one(
                f"select count(*) from tabLead {w}{' and ' if w else ' where '}coalesce(source,'') != ''"),
            "conv_rate": _pct(_count("Lead", {**ld, "status": "Converted"}), total),
        },
        "by_source": by_source,
        "status_mix": _group("Lead", "status", w),
        "qualification_mix": _group("Lead", "qualification_status", w),
        "territory_mix": _group("Lead", "territory", w),
        "segment_mix": _group("Lead", "market_segment", w),
        "country_mix": _group("Lead", "country", w),
        "owner_mix": _group("Lead", "lead_owner", w),
        "age_buckets": _age_buckets("Lead", "creation", open_where),
    }


# ---------------------------------------------------------------- opportunities
@frappe.whitelist()
def crm_analytics_opportunities(date_from=None, date_to=None, customer=None):
    _guard()
    frm, to = _range(date_from, date_to)
    scope = _scope(customer)
    w = _dw("Opportunity", "transaction_date", frm, to, base=_sw(scope, "Opportunity"))
    od = {**_df("Opportunity", "transaction_date", frm, to), **_sf(scope, "Opportunity")}
    total = _count("Opportunity", od)
    won = _count("Opportunity", {**od, "status": "Converted"})
    lost = _count("Opportunity", {**od, "status": "Lost"})

    # No value or weighted-value metrics: `opportunity_amount` is zero on every
    # opportunity on this site, so both would be permanently-zero tiles. What IS
    # recorded is `probability`, so stages carry counts and an average confidence,
    # and `amounts_recorded` below lets the UI say why value is missing rather than
    # drawing a flat line.
    gross = flt(_one(f"select coalesce(sum(base_opportunity_amount),0) from `tabOpportunity` {w}"))
    amounts_recorded = _one(
        f"""select count(*) from `tabOpportunity` {w}
            {'and' if w else 'where'} coalesce(base_opportunity_amount, 0) > 0""")

    by_stage = [
        {"label": r.label, "count": int(r.n or 0), "value": flt(r.value),
         "avg_probability": round(flt(r.prob), 1)}
        for r in _rows(
            f"""select coalesce(nullif(sales_stage,''),'Unknown') label, count(*) n,
                       coalesce(sum(base_opportunity_amount),0) value,
                       coalesce(avg(probability),0) prob
                from `tabOpportunity` {w}
                group by label order by n desc limit 12""")
    ]

    by_owner = [
        {"label": (r.label or "Unknown").split("@")[0], "count": int(r.n or 0),
         "won": int(r.won or 0), "lost": int(r.lost or 0),
         "win_rate": _pct(int(r.won or 0), int(r.decided or 0))}
        for r in _rows(
            f"""select coalesce(nullif(opportunity_owner,''),'Unknown') label, count(*) n,
                       sum(status='Converted') won, sum(status='Lost') lost,
                       sum(status in ('Converted','Lost')) decided
                from `tabOpportunity` {w}
                group by label order by n desc limit 10""")
    ]

    open_where = _dw("Opportunity", "transaction_date", frm, to,
                     base=" and ".join(f for f in [
                         _sw(scope, "Opportunity"),
                         "status not in ('Converted','Lost','Closed')",
                     ] if f))

    return {
        "currency": _company_currency(),
        "kpis": {
            "total": total,
            "open": total - won - lost,
            "won": won,
            "lost": lost,
            "win_rate": _pct(won, won + lost),
            "avg_probability": round(flt(_one(
                f"select coalesce(avg(probability),0) from `tabOpportunity` {w}")), 1),
            "from_prospect": _count("Opportunity", {**od, "opportunity_from": "Prospect"}),
            # Surfaced so the UI can say value is unavailable and why, instead of
            # rendering zeros as though the pipeline were worth nothing.
            "amounts_recorded": amounts_recorded,
            "gross_value": gross,
        },
        "by_stage": by_stage,
        "by_owner": by_owner,
        "status_mix": _group("Opportunity", "status", w),
        "type_mix": _group("Opportunity", "opportunity_type", w),
        "source_mix": _group("Opportunity", "source", w),
        "territory_mix": _group("Opportunity", "territory", w),
        "age_buckets": _age_buckets("Opportunity", "transaction_date", open_where),
    }


# ---------------------------------------------------------------- quotes & orders
# Order-value histogram edges, in company currency.
VALUE_BUCKETS = ((0, 50_000, "<50k"), (50_000, 250_000, "50-250k"),
                 (250_000, 1_000_000, "250k-1M"), (1_000_000, None, "1M+"))


@frappe.whitelist()
def crm_analytics_revenue(date_from=None, date_to=None, customer=None):
    _guard()
    frm, to = _range(date_from, date_to)
    scope = _scope(customer)
    qw = _dw("Quotation", "transaction_date", frm, to, base=_sw(scope, "Quotation"))
    qd = {**_df("Quotation", "transaction_date", frm, to), **_sf(scope, "Quotation")}

    cust_sql = " and customer=%s" if customer else ""
    params = (frm, to, customer) if customer else (frm, to)
    base = f"docstatus=1 and transaction_date between %s and %s{cust_sql}"

    orders = _one(f"select count(*) from `tabSales Order` where {base}", params)
    booked = flt(_one(
        f"select coalesce(sum(base_grand_total),0) from `tabSales Order` where {base}", params))

    value_dist = []
    for low, high, label in VALUE_BUCKETS:
        cond = f" and base_grand_total >= {low}"
        if high is not None:
            cond += f" and base_grand_total < {high}"
        value_dist.append({
            "label": label,
            "count": _one(f"select count(*) from `tabSales Order` where {base}{cond}", params),
            "value": flt(_one(
                f"select coalesce(sum(base_grand_total),0) from `tabSales Order` where {base}{cond}",
                params)),
        })

    # Fulfilment. The naive population check said per_delivered/per_billed were
    # fully populated; measured properly they are **zero on every submitted order**
    # on this site, and 10,623 of 10,625 sit at status "To Deliver and Bill". So
    # `recorded` is returned alongside the averages and the UI explains the gap
    # rather than drawing two 0% meters, which would read as a delivery crisis
    # rather than as a field nobody updates.
    fulfilment = {
        "recorded": _one(
            f"""select count(*) from `tabSales Order` where {base}
                and (coalesce(per_delivered,0) > 0 or coalesce(per_billed,0) > 0)""", params),
        "avg_delivered_pct": round(flt(_one(
            f"select coalesce(avg(per_delivered),0) from `tabSales Order` where {base}", params)), 1),
        "avg_billed_pct": round(flt(_one(
            f"select coalesce(avg(per_billed),0) from `tabSales Order` where {base}", params)), 1),
        "fully_delivered": _one(
            f"select count(*) from `tabSales Order` where {base} and per_delivered >= 99.99", params),
        "unbilled": _one(
            f"select count(*) from `tabSales Order` where {base} and per_billed < 99.99", params),
        "dominant_status": (lambda r: r[0] if r else None)(_rows(
            f"""select coalesce(nullif(status,''),'Unknown') label, count(*) n
                from `tabSales Order` where {base} group by label order by n desc limit 1""",
            params)),
    }

    new_vs_repeat = _rows(
        f"""select date_format(so.transaction_date, '%%Y-%%m') bucket,
                   count(distinct case when c.creation >= date_sub(so.transaction_date, interval 90 day)
                        then so.customer end) new_customers,
                   count(distinct so.customer) customers
            from `tabSales Order` so
            join `tabCustomer` c on c.name = so.customer
            where so.docstatus=1 and so.transaction_date between %s and %s
            group by bucket order by bucket""", (frm, to))

    return {
        "currency": _company_currency(),
        "kpis": {
            "quotations": _count("Quotation", qd),
            "quotation_value": flt(_one(
                f"select coalesce(sum(base_grand_total),0) from `tabQuotation` {qw}")),
            "orders": orders,
            "booked": booked,
            "avg_order": round(booked / orders, 2) if orders else 0.0,
            "customers_ordering": _one(
                f"select count(distinct customer) from `tabSales Order` where {base}", params),
        },
        "quotation_status_mix": _group("Quotation", "status", qw),
        "quotation_order_type": _group("Quotation", "order_type", qw),
        "value_distribution": value_dist,
        "fulfilment": fulfilment,
        "order_status_mix": [
            {"label": r.label, "count": int(r.n or 0)}
            for r in _rows(
                f"""select coalesce(nullif(status,''),'Unknown') label, count(*) n
                    from `tabSales Order` where {base} group by label order by n desc limit 10""",
                params)
        ],
        "territory_value": [
            {"label": r.label, "value": flt(r.value)}
            for r in _rows(
                f"""select coalesce(nullif(territory,''),'Unknown') label,
                           coalesce(sum(base_grand_total),0) value
                    from `tabSales Order` where {base}
                    group by label order by value desc limit 10""", params)
        ],
        "top_customers": [
            {"label": r.label, "value": flt(r.value), "orders": int(r.n or 0)}
            for r in _rows(
                f"""select customer label, coalesce(sum(base_grand_total),0) value, count(*) n
                    from `tabSales Order` where {base}
                    group by customer order by value desc limit 10""", params)
        ],
        "monthly": [
            {"label": str(r.bucket)[2:], "customers": int(r.customers or 0),
             "new_customers": int(r.new_customers or 0)}
            for r in new_vs_repeat
        ],
    }
