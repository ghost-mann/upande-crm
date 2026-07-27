"""Sales analytics for the CRM Overview.

A *read* layer, so it follows `api/crm.py`'s house style rather than
`api/activity.py`'s: every query is individually guarded and degrades to zero or
an empty list. A site missing Sales Invoice should render empty cards, not break
the whole Overview.

Money is always summed from `base_*` columns. Transaction currencies on this site
are mixed (USD/EUR/KES/GBP orders), so the base fields — denominated in the
Company's default currency — are the only summable ones. See `_company_currency`.
"""

import frappe
from frappe.utils import add_days, flt, getdate, nowdate

from upande_crm.api.crm import _guard, _has, _hascol, _range

# Receivables aging buckets, in days overdue.
AGING_LABELS = ("Current", "1-30", "31-60", "60+")


def _company_currency():
    """The currency `base_grand_total` is actually denominated in.

    Every Company on this site defaults to KES, yet the dashboard used to render
    these figures with a hardcoded '$' — a ~130x overstatement. Resolve it rather
    than assume it.
    """
    try:
        company = frappe.defaults.get_global_default("company")
        if company:
            ccy = frappe.db.get_value("Company", company, "default_currency")
            if ccy:
                return ccy
    except Exception:
        pass
    try:
        return frappe.defaults.get_global_default("currency") or "KES"
    except Exception:
        return "KES"


def _sum(doctype, amount_col, date_col, frm, to, extra=""):
    """(sum, count) of `amount_col` over `[frm, to]`, or (0, 0) if unavailable."""
    if not _has(doctype) or not _hascol(doctype, amount_col) or not _hascol(doctype, date_col):
        return 0.0, 0
    try:
        row = frappe.db.sql(
            f"""select coalesce(sum(`{amount_col}`), 0), count(*)
                from `tab{doctype}`
                where docstatus=1 and `{date_col}` between %s and %s {extra}""",
            (frm, to),
        )[0]
        return flt(row[0]), int(row[1])
    except Exception:
        return 0.0, 0


@frappe.whitelist()
def crm_sales_analytics(date_from=None, date_to=None, customer=None):
    _guard()
    frm, to = _range(date_from, date_to)
    currency = _company_currency()

    booked, booked_orders = _sum("Sales Order", "base_grand_total", "transaction_date", frm, to)
    billed, billed_invoices = _sum("Sales Invoice", "base_grand_total", "posting_date", frm, to)

    # Growth against the immediately preceding window of equal length.
    try:
        span = max((getdate(to) - getdate(frm)).days, 1)
        prev_to = add_days(getdate(frm), -1)
        prev_frm = add_days(prev_to, -span)
        prev_billed, _ = _sum(
            "Sales Invoice", "base_grand_total", "posting_date", str(prev_frm), str(prev_to)
        )
    except Exception:
        prev_billed = 0.0
    growth_pct = round((billed - prev_billed) / prev_billed * 100, 1) if prev_billed else 0.0

    outstanding, outstanding_count = _outstanding()

    return {
        "currency": currency,
        "kpis": {
            "booked": booked,
            "booked_orders": booked_orders,
            "billed": billed,
            "billed_invoices": billed_invoices,
            # Guarded: an empty range must not raise.
            "aov": round(booked / booked_orders, 2) if booked_orders else 0.0,
            "outstanding": outstanding,
            "outstanding_count": outstanding_count,
            "growth_pct": growth_pct,
        },
        "revenue_trend": _revenue_trend(frm, to),
        "rep_performance": _rep_performance(frm, to),
        "top_products": _top_products(frm, to),
        "territory_revenue": _territory_revenue(frm, to),
        "aging": _aging(),
    }


def _outstanding():
    if not _has("Sales Invoice") or not _hascol("Sales Invoice", "outstanding_amount"):
        return 0.0, 0
    try:
        row = frappe.db.sql(
            """select coalesce(sum(outstanding_amount), 0), count(*)
               from `tabSales Invoice` where docstatus=1 and outstanding_amount > 0"""
        )[0]
        return flt(row[0]), int(row[1])
    except Exception:
        return 0.0, 0


def _revenue_trend(frm, to):
    """Booked (Sales Order) against billed (Sales Invoice), bucketed by span.

    Daily up to ~3 months, monthly beyond — same convention as the existing
    `_trend_in_range` so the Overview's charts agree on granularity.
    """
    try:
        span = (getdate(to) - getdate(frm)).days
    except Exception:
        span = 999
    by_day = span <= 92
    fmt = "%%Y-%%m-%%d" if by_day else "%%Y-%%m"
    trim = (lambda b: b[5:]) if by_day else (lambda b: b[2:])

    def series(doctype, date_col):
        if not _has(doctype) or not _hascol(doctype, date_col):
            return {}
        try:
            rows = frappe.db.sql(
                f"""select date_format(`{date_col}`, '{fmt}') bucket,
                           coalesce(sum(base_grand_total), 0) amt
                    from `tab{doctype}`
                    where docstatus=1 and `{date_col}` between %s and %s
                    group by bucket order by bucket""",
                (frm, to),
                as_dict=True,
            )
            return {r.bucket: flt(r.amt) for r in rows}
        except Exception:
            return {}

    so = series("Sales Order", "transaction_date")
    si = series("Sales Invoice", "posting_date")
    buckets = sorted(set(so) | set(si))
    return [
        {"label": trim(b), "booked": so.get(b, 0.0), "billed": si.get(b, 0.0)}
        for b in buckets
    ]


def _rep_performance(frm, to, limit=8):
    """Revenue by Sales Order owner.

    `owner` is used rather than Sales Team/sales_person, which is unpopulated on
    this site while owner has a genuine spread across the sales staff.
    """
    if not _has("Sales Order") or not _hascol("Sales Order", "owner"):
        return []
    try:
        rows = frappe.db.sql(
            """select owner label, coalesce(sum(base_grand_total), 0) amount, count(*) orders
               from `tabSales Order`
               where docstatus=1 and transaction_date between %s and %s
               group by owner order by amount desc limit %s""",
            (frm, to, int(limit)),
            as_dict=True,
        )
        return [
            {"label": (r.label or "").split("@")[0] or "Unknown",
             "amount": flt(r.amount), "orders": int(r.orders)}
            for r in rows
        ]
    except Exception:
        return []


def _top_products(frm, to, limit=8):
    if not _has("Sales Order Item"):
        return []
    try:
        rows = frappe.db.sql(
            """select coalesce(nullif(soi.item_name, ''), soi.item_code) label,
                      coalesce(sum(soi.base_amount), 0) amount,
                      coalesce(sum(soi.qty), 0) qty
               from `tabSales Order Item` soi
               join `tabSales Order` so on so.name = soi.parent
               where so.docstatus=1 and so.transaction_date between %s and %s
               group by label order by amount desc limit %s""",
            (frm, to, int(limit)),
            as_dict=True,
        )
        return [
            {"label": r.label or "Unknown", "amount": flt(r.amount), "qty": flt(r.qty)}
            for r in rows
        ]
    except Exception:
        return []


def _territory_revenue(frm, to, limit=8):
    src, date_col = (
        ("Sales Invoice", "posting_date") if _has("Sales Invoice")
        else ("Sales Order", "transaction_date")
    )
    if not _has(src) or not _hascol(src, "territory"):
        return []
    try:
        rows = frappe.db.sql(
            f"""select coalesce(nullif(territory, ''), 'Unknown') label,
                       coalesce(sum(base_grand_total), 0) amount
                from `tab{src}`
                where docstatus=1 and `{date_col}` between %s and %s
                group by label order by amount desc limit %s""",
            (frm, to, int(limit)),
            as_dict=True,
        )
        return [{"label": r.label, "amount": flt(r.amount)} for r in rows]
    except Exception:
        return []


def _aging():
    """Outstanding receivables by days overdue.

    Not date-range scoped: what is owed is owed regardless of the dashboard's
    window, and scoping it would understate the debt.
    """
    if not _has("Sales Invoice") or not _hascol("Sales Invoice", "outstanding_amount"):
        return [{"label": l, "amount": 0.0} for l in AGING_LABELS]
    has_due = _hascol("Sales Invoice", "due_date")
    if not has_due:
        total, _ = _outstanding()
        return [
            {"label": "Current", "amount": total},
            {"label": "1-30", "amount": 0.0},
            {"label": "31-60", "amount": 0.0},
            {"label": "60+", "amount": 0.0},
        ]
    today = str(getdate(nowdate()))
    try:
        row = frappe.db.sql(
            """select
                 sum(case when due_date is null or due_date >= %(t)s then outstanding_amount else 0 end),
                 sum(case when due_date < %(t)s and due_date >= date_sub(%(t)s, interval 30 day) then outstanding_amount else 0 end),
                 sum(case when due_date < date_sub(%(t)s, interval 30 day) and due_date >= date_sub(%(t)s, interval 60 day) then outstanding_amount else 0 end),
                 sum(case when due_date < date_sub(%(t)s, interval 60 day) then outstanding_amount else 0 end)
               from `tabSales Invoice` where docstatus=1 and outstanding_amount > 0""",
            {"t": today},
        )[0]
        return [
            {"label": AGING_LABELS[i], "amount": flt(row[i])} for i in range(4)
        ]
    except Exception:
        return [{"label": l, "amount": 0.0} for l in AGING_LABELS]
