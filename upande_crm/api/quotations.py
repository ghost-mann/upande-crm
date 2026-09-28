"""Quotations: what was offered, at what price, and what became an order.

Reads ERPNext's own Quotation — no parallel record. A quotation "converted" when
at least one Sales Order line points back at it (`Sales Order Item.prevdoc_docname`,
which ERPNext sets when the order is made from the quotation). Conversion is over
submitted quotations only: a draft was never sent.

On kaitet.local no order points back at any quotation yet, so conversion reads 0%
there — an honest figure about how the site is used, which the page says.
"""

import frappe
from frappe.utils import add_months, cint, date_diff, flt, get_first_day, getdate, nowdate

from upande_crm.api.crm import _company_currency, _guard, _has, _range
from upande_crm.modules import requires_module

ROW_FIELDS = ["name", "quotation_to", "party_name", "customer_name", "transaction_date", "valid_till",
              "base_grand_total", "status", "docstatus", "owner"]


def _followup_days():
    from upande_crm.api.settings import DEFAULTS, get_settings

    return cint(get_settings().get("quote_followup_days")) or DEFAULTS["quote_followup_days"]


def _orders_for(names):
    """{quotation: [sales orders]} for submitted orders made from these quotations."""
    if not names or not _has("Sales Order"):
        return {}
    out = {}
    for q, so in frappe.db.sql(
        """select distinct soi.prevdoc_docname, soi.parent from `tabSales Order Item` soi
           join `tabSales Order` so on so.name = soi.parent
           where so.docstatus = 1 and soi.prevdoc_docname in %s""", (tuple(names),)):
        out.setdefault(q, []).append(so)
    return out


def _conversion(quotes, orders):
    submitted = [q for q in quotes if cint(q["docstatus"]) == 1]
    converted = [q for q in submitted if orders.get(q["name"])]
    rate = round(100.0 * len(converted) / len(submitted), 1) if submitted else None
    return {"submitted": len(submitted), "converted": len(converted), "rate": rate}


def _flag(rows, orders, followup_days):
    """Mark open, submitted quotations older than the follow-up window."""
    today = nowdate()
    for r in rows:
        r["orders"] = orders.get(r.name, [])
        age = date_diff(today, r.transaction_date) if r.transaction_date else None
        r["age_days"] = age
        r["followup"] = bool(cint(r.docstatus) == 1 and r.status in ("Open", "Replied")
                             and not r["orders"] and age is not None and age > followup_days)
    return rows


def _price_history(items):
    """Quoted rates per item *and currency*, oldest first. A rose quoted at 0.35
    USD and at 30 KES is two histories, not a range from 0.35 to 30."""
    history = {}
    for it in items:
        key = (it.item_code, it.currency)
        h = history.setdefault(key, {"item_code": it.item_code, "item_name": it.item_name, "uom": it.uom,
                                     "currency": it.currency, "points": []})
        h["points"].append({"date": str(it.transaction_date), "rate": flt(it.rate), "quotation": it.name,
                            "currency": it.currency, "draft": cint(it.docstatus) == 0})
    for h in history.values():
        rates = [p["rate"] for p in h["points"]]
        h["latest"] = rates[-1]
        h["low"], h["high"] = min(rates), max(rates)
    return sorted(history.values(), key=lambda h: (-len(h["points"]), h["item_code"] or "", h["currency"] or ""))


def _median(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def _empty(followup_days):
    return {"kpis": {k: 0 for k in ("drafts", "submitted", "open", "converted", "lost", "expired",
                                    "avg_value", "needs_followup")} | {"conversion_rate": None,
                                                                      "median_days_to_order": None},
            "trend": [], "by_status": [], "rows": [], "top_items": [], "followup_days": followup_days,
            "currency": _company_currency(), "available": False}


@frappe.whitelist()
@requires_module("quotations")
def crm_dashboard_quotations(date_from=None, date_to=None, customer=None):
    _guard()
    days = _followup_days()
    if not _has("Quotation") or not frappe.has_permission("Quotation", "read"):
        return _empty(days)
    frm, to = _range(date_from, date_to)
    filters = {"transaction_date": ["between", [frm, to]], "docstatus": ["<", 2]}
    if customer:
        filters.update({"quotation_to": "Customer", "party_name": customer})
    rows = frappe.get_all("Quotation", filters=filters, fields=ROW_FIELDS,
                          order_by="transaction_date desc", limit=1000)
    orders = _orders_for([r.name for r in rows])
    _flag(rows, orders, days)
    conv = _conversion(rows, orders)

    # Quote -> first order, in days.
    first_order = {}
    if orders:
        for so, date in frappe.db.sql("select name, transaction_date from `tabSales Order` where name in %s",
                                      (tuple({s for v in orders.values() for s in v}),)):
            first_order[so] = date
    to_order = []
    for r in rows:
        dates = [first_order[s] for s in r["orders"] if first_order.get(s)]
        if dates and r.transaction_date:
            to_order.append(date_diff(min(dates), r.transaction_date))

    submitted = [r for r in rows if cint(r.docstatus) == 1]
    by_status = {}
    for r in rows:
        label = "Draft" if cint(r.docstatus) == 0 else r.status
        by_status[label] = by_status.get(label, 0) + 1

    # Its own query: the chart says "last 12 months", whatever range the page is on.
    first = get_first_day(getdate(to))
    months = [str(add_months(first, -i))[:7] for i in range(11, -1, -1)]
    trend = {m: {"label": m, "count": 0, "value": 0.0, "converted": 0} for m in months}
    tfilters = {"docstatus": 1, "transaction_date": ["between", [months[0] + "-01", to]]}
    if customer:
        tfilters.update({"quotation_to": "Customer", "party_name": customer})
    trows = frappe.get_all("Quotation", filters=tfilters, fields=["name", "transaction_date", "base_grand_total"], limit=0)
    torders = _orders_for([r.name for r in trows])
    for r in trows:
        m = str(r.transaction_date)[:7]
        if m in trend:
            trend[m]["count"] += 1
            trend[m]["value"] += flt(r.base_grand_total)
            trend[m]["converted"] += 1 if torders.get(r.name) else 0

    top_items = []
    if rows:
        top_items = frappe.db.sql(
            """select qi.item_code, max(qi.item_name) item_name, count(distinct qi.parent) quotes,
                      sum(qi.base_net_amount) value, avg(qi.base_rate) avg_base_rate
               from `tabQuotation Item` qi where qi.parent in %s and ifnull(qi.item_code,'') != ''
               group by qi.item_code order by value desc limit 10""",
            (tuple(r.name for r in rows),), as_dict=True)

    for r in rows:
        r["transaction_date"] = str(r.transaction_date) if r.transaction_date else None
        r["valid_till"] = str(r.valid_till) if r.valid_till else None
        r["party"] = r.customer_name or r.party_name

    return {
        "kpis": {
            "drafts": sum(1 for r in rows if cint(r.docstatus) == 0),
            "submitted": conv["submitted"],
            "open": sum(1 for r in submitted if r.status in ("Open", "Replied") and not r["orders"]),
            "converted": conv["converted"],
            "lost": sum(1 for r in submitted if r.status == "Lost"),
            "expired": sum(1 for r in submitted if r.status == "Expired"),
            "conversion_rate": conv["rate"],
            "avg_value": (sum(flt(r.base_grand_total) for r in submitted) / len(submitted)) if submitted else 0,
            "median_days_to_order": _median(to_order),
            "needs_followup": sum(1 for r in rows if r["followup"]),
        },
        "trend": list(trend.values()),
        "by_status": [{"label": k, "count": v} for k, v in sorted(by_status.items(), key=lambda x: -x[1])],
        "rows": rows,
        "top_items": top_items,
        "followup_days": days,
        "currency": _company_currency(),
        "available": True,
        "range": {"from": frm, "to": to},
    }


@frappe.whitelist()
@requires_module("quotations")
def crm_customer_quotations(name):
    """One customer's quotations, and every rate quoted to them per item over time."""
    _guard()
    frappe.has_permission("Customer", "read", name, throw=True)
    days = _followup_days()
    if not _has("Quotation") or not frappe.has_permission("Quotation", "read"):
        return {"rows": [], "price_history": [], "available": False, "currency": _company_currency()}
    rows = frappe.get_all("Quotation", filters={"quotation_to": "Customer", "party_name": name, "docstatus": ["<", 2]},
                          fields=ROW_FIELDS, order_by="transaction_date desc", limit=200)
    orders = _orders_for([r.name for r in rows])
    _flag(rows, orders, days)
    items = []
    if rows:
        items = frappe.db.sql(
            """select qi.item_code, qi.item_name, qi.rate, qi.uom, q.transaction_date, q.name, q.currency, q.docstatus
               from `tabQuotation Item` qi join `tabQuotation` q on q.name = qi.parent
               where q.name in %s and ifnull(qi.item_code,'') != ''
               order by q.transaction_date asc""", (tuple(r.name for r in rows),), as_dict=True)
    history = _price_history(items)
    for r in rows:
        r["transaction_date"] = str(r.transaction_date) if r.transaction_date else None
        r["valid_till"] = str(r.valid_till) if r.valid_till else None
    return {"rows": rows, "available": True, "currency": _company_currency(), "followup_days": days,
            "price_history": history}
