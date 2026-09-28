"""The customer page: one customer's whole story, one endpoint per tab.

The header is cheap and loads with the page. Each tab loads on first open,
because a single customer here can carry thousands of invoices, and a page that
fetched them all to show the Overview would be slow for the customers that
matter most.

Every endpoint takes the customer's name and checks, in order: the module is
on, the caller is a CRM user, the Customer exists, and the caller may read it.
All queries are parameterised; the name arrives from the client.

Money is submitted Sales Invoice `base_grand_total`, in the company currency —
the same basis as the rest of the CRM. "Agreed pricing" is the customer's price
list (or its customer group's), because on this site no Item Price or Pricing
Rule is customer-specific; the payload says which list it read so the page
never implies a per-customer agreement that does not exist.
"""

import frappe
from frappe import _
from frappe.utils import add_months, cint, date_diff, flt, get_first_day, getdate, nowdate

from upande_crm.api.crm import _company_currency, _guard, _has, _hascol
from upande_crm.modules import CUSTPAGE_TABS, requires_module

ORDER_KINDS = {
    # kind: (date column, has outstanding_amount)
    "Sales Order": ("transaction_date", False),
    "Delivery Note": ("posting_date", False),
    "Sales Invoice": ("posting_date", True),
}
MAX_PAGE = 100


def _customer(name):
    """Gate one customer: exists, and the caller may read it."""
    _guard()
    if not name or not frappe.db.exists("Customer", name):
        frappe.throw(_("Customer {0} not found").format(name), frappe.DoesNotExistError)
    frappe.has_permission("Customer", "read", name, throw=True)
    return name


def _page(start, page_len, default):
    start = max(0, cint(start))
    size = cint(page_len) or default
    return start, max(1, min(MAX_PAGE, size))


def _like(text):
    """A LIKE pattern matching `text` literally — `_` and `%` are wildcards."""
    esc = str(text).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


def _one(sql, values):
    row = frappe.db.sql(sql, values)
    return row[0][0] if row else None


# ---------------------------------------------------------------- header
@frappe.whitelist()
@requires_module("customer_page")
def crm_customer_header(name, date_from=None, date_to=None):
    from upande_crm.api.settings import get_settings, parse_lines

    _customer(name)
    wanted = ["name", "customer_name", "customer_group", "territory", "default_price_list",
              "account_manager", "disabled", "image", "owner"]
    fields = [f for f in wanted if f == "name" or _hascol("Customer", f)]
    cust = frappe.db.get_value("Customer", name, fields, as_dict=True)
    cust.setdefault("account_manager", None)
    cust["account_manager"] = cust.get("account_manager") or cust.pop("owner", None)
    cust.pop("owner", None)

    lifetime = flt(_one(
        "select coalesce(sum(base_grand_total),0) from `tabSales Invoice` where customer=%s and docstatus=1",
        name))
    so = frappe.db.sql(
        """select count(*), coalesce(sum(base_grand_total),0), max(transaction_date)
           from `tabSales Order` where customer=%s and docstatus=1""", name)[0]
    last_si = _one("select max(posting_date) from `tabSales Invoice` where customer=%s and docstatus=1", name)
    last = max([d for d in (so[2], last_si) if d], default=None)

    range_revenue = None
    if date_from and date_to:
        range_revenue = flt(_one(
            """select coalesce(sum(base_grand_total),0) from `tabSales Invoice`
               where customer=%s and docstatus=1 and posting_date between %s and %s""",
            (name, date_from, date_to)))

    open_quotes = 0
    if _has("Quotation"):
        open_quotes = cint(_one(
            """select count(*) from `tabQuotation` where quotation_to='Customer' and party_name=%s
               and docstatus=1 and status in ('Open','Replied')""", name))

    s = get_settings()
    tabs = [t for t in parse_lines(s.get("custpage_tabs")) if t in CUSTPAGE_TABS] or list(CUSTPAGE_TABS)
    default_tab = s.get("custpage_default_tab")
    return {
        "customer": cust,
        "currency": _company_currency(),
        "figures": {
            "lifetime_revenue": lifetime,
            "range_revenue": range_revenue,
            "order_count": cint(so[0]),
            "avg_order_value": flt(so[1]) / cint(so[0]) if cint(so[0]) else 0,
            "last_order_date": str(last) if last else None,
            "days_since_last_order": date_diff(nowdate(), last) if last else None,
            "open_quotations": open_quotes,
        },
        "tabs": tabs,
        "default_tab": default_tab if default_tab in tabs else tabs[0],
    }


# ---------------------------------------------------------------- overview
def _month_labels(n=12):
    first = get_first_day(nowdate())
    return [str(add_months(first, -i))[:7] for i in range(n - 1, -1, -1)]


@frappe.whitelist()
@requires_module("customer_page")
def crm_customer_overview(name):
    from upande_crm.api import scope as scope_mod

    _customer(name)
    labels = _month_labels()
    rows = frappe.db.sql(
        """select date_format(posting_date, '%%Y-%%m') as m, sum(base_grand_total) as amount
           from `tabSales Invoice` where customer=%s and docstatus=1 and posting_date >= %s
           group by m""", (name, labels[0] + "-01"), as_dict=True)
    by_month = {r.m: flt(r.amount) for r in rows}
    trend = [{"label": m, "amount": by_month.get(m, 0.0)} for m in labels]

    top_items = frappe.db.sql(
        """select sii.item_code, max(sii.item_name) as item_name,
                  sum(sii.base_net_amount) as amount, sum(sii.stock_qty) as qty
           from `tabSales Invoice Item` sii join `tabSales Invoice` si on si.name = sii.parent
           where si.customer=%s and si.docstatus=1 and ifnull(sii.item_code,'') != ''
           group by sii.item_code order by amount desc limit 10""", name, as_dict=True)

    scope = scope_mod.customer_scope(name)
    next_event = None
    events = scope_mod.event_names(scope)
    if events:
        found = frappe.get_all("Event", filters={"name": ["in", events], "starts_on": [">=", nowdate()]},
                               fields=["name", "subject", "starts_on"], order_by="starts_on asc", limit=1)
        next_event = found[0] if found else None

    todos = scope_mod.todo_names(scope)
    open_todos = frappe.get_all(
        "ToDo", filters={"name": ["in", todos], "status": "Open"},
        fields=["name", "description", "date", "allocated_to", "priority"],
        order_by="date asc", limit=20) if todos else []

    return {"trend": trend, "top_items": top_items, "next_event": next_event, "open_todos": open_todos}


# ---------------------------------------------------------------- orders
@frappe.whitelist()
@requires_module("customer_page")
def crm_customer_orders(name, kind="Sales Order", status=None, start=0, page_len=25):
    _customer(name)
    if kind not in ORDER_KINDS:
        frappe.throw(_("Unknown order type {0}").format(kind), frappe.ValidationError)
    datecol, has_outstanding = ORDER_KINDS[kind]
    start, size = _page(start, page_len, 25)

    where = "customer=%(c)s and docstatus < 2"
    values = {"c": name}
    if status:
        where += " and status=%(s)s"
        values["s"] = status
    outstanding = "outstanding_amount" if has_outstanding else "null"
    rows = frappe.db.sql(
        f"""select name, `{datecol}` as date, status, base_grand_total as grand_total,
                   {outstanding} as outstanding, docstatus
            from `tab{kind}` where {where}
            order by `{datecol}` desc, creation desc limit %(size)s offset %(start)s""",
        {**values, "size": size, "start": start}, as_dict=True)
    total = cint(_one(f"select count(*) from `tab{kind}` where {where}", values))
    statuses = [r[0] for r in frappe.db.sql(
        f"select distinct status from `tab{kind}` where customer=%s and docstatus < 2 and ifnull(status,'')!=''",
        name)]

    since = _month_labels()[0] + "-01"
    per = frappe.db.sql(
        f"""select date_format(`{datecol}`, '%%Y-%%m') as m, count(*) as n from `tab{kind}`
            where customer=%s and docstatus=1 and `{datecol}` >= %s group by m""",
        (name, since), as_dict=True)
    per_map = {r.m: cint(r.n) for r in per}
    summary = {
        "per_month": [{"label": m, "count": per_map.get(m, 0)} for m in _month_labels()],
        "outstanding": flt(_one(
            "select coalesce(sum(outstanding_amount),0) from `tabSales Invoice` where customer=%s and docstatus=1",
            name)),
        "since": since,
    }
    for r in rows:
        r["date"] = str(r["date"]) if r["date"] else None
    return {"kind": kind, "rows": rows, "total": total, "start": start, "page_len": size,
            "statuses": sorted(statuses), "summary": summary}


# ---------------------------------------------------------------- pricing
def _price_list(name):
    own = frappe.db.get_value("Customer", name, "default_price_list")
    if own:
        return own, "customer"
    group = frappe.db.get_value("Customer", name, "customer_group")
    if group and _hascol("Customer Group", "default_price_list"):
        inherited = frappe.db.get_value("Customer Group", group, "default_price_list")
        if inherited:
            return inherited, "customer_group"
    return None, None


@frappe.whitelist()
@requires_module("customer_page")
def crm_customer_pricing(name, search=None, start=0, page_len=50):
    _customer(name)
    start, size = _page(start, page_len, 50)
    price_list, source = _price_list(name)
    out = {"price_list": price_list, "source": source, "rows": [], "total": 0,
           "start": start, "page_len": size}
    if not price_list:
        return out

    where = "price_list=%(pl)s"
    values = {"pl": price_list}
    if search:
        where += " and (item_code like %(q)s or item_name like %(q)s)"
        values["q"] = _like(search)
    rows = frappe.db.sql(
        f"""select item_code, item_name, uom, price_list_rate as rate, currency
            from `tabItem Price` where {where}
            order by item_code limit %(size)s offset %(start)s""",
        {**values, "size": size, "start": start}, as_dict=True)
    out["total"] = cint(_one(f"select count(*) from `tabItem Price` where {where}", values))

    codes = [r.item_code for r in rows if r.item_code]
    last = {}
    if codes:
        for r in frappe.db.sql(
            """select sii.item_code, sii.rate, si.posting_date, si.currency
               from `tabSales Invoice Item` sii join `tabSales Invoice` si on si.name = sii.parent
               where si.customer=%s and si.docstatus=1 and sii.item_code in %s
               order by si.posting_date desc, si.creation desc""", (name, tuple(codes)), as_dict=True):
            last.setdefault(r.item_code, r)
    for r in rows:
        hit = last.get(r.item_code)
        r["last_rate"] = flt(hit.rate) if hit else None
        r["last_date"] = str(hit.posting_date) if hit else None
        r["last_currency"] = hit.currency if hit else None
    out["rows"] = rows
    return out


# ---------------------------------------------------------------- contracts
@frappe.whitelist()
@requires_module("customer_page")
def crm_customer_contracts(name):
    _customer(name)
    if not _has("Contract"):
        return {"rows": [], "available": False}
    wanted = ["name", "status", "start_date", "end_date", "is_signed", "contract_template"]
    fields = [f for f in wanted if f == "name" or _hascol("Contract", f)]
    rows = frappe.get_all("Contract", filters={"party_type": "Customer", "party_name": name},
                          fields=fields, order_by="start_date desc", limit=200)
    return {"rows": rows, "available": True}
