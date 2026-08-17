"""Command-centre endpoints backing the CRM Overview.

A *read* layer, so it follows `api/crm.py`'s house style rather than
`api/activity.py`'s: every query is individually guarded and degrades to zero or
an empty list. A site without Sales Order Item should render empty cards, not
break the Overview.

Three endpoints rather than one, so the KPI row is never held behind the heaviest
query, and the mover drill costs nothing until someone opens it.

Two vocabulary decisions run through the whole module:

*Salesperson* is the Sales Order's `owner`. `Sales Team.sales_person` holds a
single distinct person across 28 rows and attaches to Customer rather than to
orders, so it cannot answer "who sold this"; `owner` has a genuine spread across
the sales staff. Same choice `analytics._rep_performance` already made.

*Flower* is the Item — varieties are items (Giselle, Fireworks, Dinara) inside the
rose item groups. Revenue per flower can therefore only come from
`Sales Order Item.base_amount`, which is line value and excludes order-level tax
and freight. Rep and order totals use `base_grand_total`, which includes them, so
the two are labelled differently everywhere they appear together.

Money is always summed from `base_*` columns: transaction currencies on this site
are mixed, so only the company-currency fields are summable.
"""

import frappe
from frappe.utils import add_days, add_months, cint, flt, getdate, nowdate

from upande_crm.api.analytics import _company_currency, _cust
from upande_crm.api.crm import _count, _df, _guard, _has, _hascol, _range, _rows, _scope, _sf
from upande_crm.api.funnel import cohort

# Series drawn on the track-record chart at once. Six is where a multi-line chart
# stops being readable, and the palette has eight entries to spend.
SERIES_LIMIT = 6
# Rows in the movers band, per direction.
MOVER_LIMIT = 5
# Varieties forming the Top-5-sellers matrix columns. The user asked for five.
SELLER_COLS = 5
# Customers, or reps, ranked against them.
SELLER_ROWS = 8
# Accounts/varieties listed inside a mover drill, per direction.
DRILL_LIMIT = 8
# Months of history in a drill's context sparkline.
DRILL_MONTHS = 12

# How far either side of today "upcoming" reaches. Overdue work is bounded so a
# site with years of abandoned ToDos doesn't bury tomorrow's meeting.
UPCOMING_BACK_DAYS = 30
UPCOMING_FORWARD_DAYS = 30
UPCOMING_LIMIT = 60
# "This week" for the KPI tile.
UPCOMING_KPI_DAYS = 7

# Rows on the conversion card, and the owners that are not really owners. A lead
# whose `lead_owner` is Guest came in through a web form and was never picked up;
# Administrator is an import. Both mean "nobody", so they share one row.
CONVERSION_ROWS = 10
UNOWNED = {"Guest", "Administrator"}
UNASSIGNED = "__unassigned__"

# Reference doctypes an awaiting-reply email may hang off.
EMAIL_REFS = ("Lead", "Opportunity", "Customer", "Quotation", "Prospect")
# Call outcomes that mean nobody was reached.
MISSED_CALL_STATUSES = ("No Answer", "Busy", "Failed")
FOLLOW_UP_LIMIT = 12

# What a mover drill may be keyed on. Anything else is rejected rather than
# interpolated into a group-by.
DRILL_DIMS = {
    "flower": {"col": "soi.item_code", "label": "Flower"},
    "rep": {"col": "so.owner", "label": "Salesperson"},
    "customer": {"col": "so.customer", "label": "Customer"},
}


# ---------------------------------------------------------------- helpers
def _prior(frm, to):
    """The immediately preceding window of equal length."""
    try:
        span = max((getdate(to) - getdate(frm)).days, 1)
        prev_to = add_days(getdate(frm), -1)
        return str(add_days(prev_to, -span)), str(prev_to)
    except Exception:
        return frm, to


def _pct(cur, prev):
    """Percent change, or 0.0 with no base to compare against.

    Callers always expose `prev` alongside, so a UI can tell "flat" from "there
    was nothing before" — which this number cannot.
    """
    if not prev:
        return 0.0
    return round((flt(cur) - flt(prev)) / flt(prev) * 100, 1)


def _sold():
    """Whether per-item sales history is readable at all."""
    return _has("Sales Order") and _has("Sales Order Item")


def _short(user):
    """A rep's display name: the local part of their login."""
    return (user or "").split("@")[0] or "Unknown"


def _buckets(frm, to):
    """(sql_template, label_fn, grain) — granularity chosen by span.

    Daily up to ~3 months, Monday-anchored weeks up to a year, months beyond, so
    a 12-month track record stays readable instead of drawing 365 points.
    `{col}` in the template is substituted with the date column.
    """
    try:
        span = (getdate(to) - getdate(frm)).days
    except Exception:
        span = 999
    if span <= 92:
        return "date_format({col}, '%%Y-%%m-%%d')", (lambda b: b[5:]), "day"
    if span <= 366:
        return (
            "date_format(date_sub({col}, interval weekday({col}) day), '%%Y-%%m-%%d')",
            (lambda b: b[5:]),
            "week",
        )
    return "date_format({col}, '%%Y-%%m')", (lambda b: b[2:]), "month"


def _decompose(a0, q0, a1, q1):
    """Split a revenue change into volume and price effects.

        delta = (q1 - q0) * r0  +  (r1 - r0) * q1
                volume             price

    where r is the average realised rate. The two terms sum to `a1 - a0` by
    construction — including when either quantity is zero — so the split is
    arithmetic rather than inference. That identity is what makes the drill's
    answer to "why did this stop selling" trustworthy, and it is asserted in
    tests/test_command.py.
    """
    a0, q0, a1, q1 = flt(a0), flt(q0), flt(a1), flt(q1)
    r0 = a0 / q0 if q0 else 0.0
    r1 = a1 / q1 if q1 else 0.0
    return (q1 - q0) * r0, (r1 - r0) * q1


def _item_totals(frm, to, customer=None, group_col="soi.item_code", extra="", params=()):
    """{key: {amount, qty, orders}} over the Sales Order Item ⋈ Sales Order join.

    One shape reused by every per-flower reader here, so the movers band, the
    matrix and the drill can never disagree about what a variety sold.
    """
    if not _sold():
        return {}
    try:
        rows = frappe.db.sql(
            f"""select {group_col} k,
                       coalesce(sum(soi.base_amount), 0) amount,
                       coalesce(sum(soi.qty), 0) qty,
                       count(distinct so.name) orders
                from `tabSales Order Item` soi
                join `tabSales Order` so on so.name = soi.parent
                where so.docstatus = 1
                  and so.transaction_date between %s and %s
                  {_cust(customer, 'so')} {extra}
                group by k""",
            (frm, to, *params),
            as_dict=True,
        )
        return {
            (r.k or "Unknown"): {
                "amount": flt(r.amount), "qty": flt(r.qty), "orders": cint(r.orders),
            }
            for r in rows
        }
    except Exception:
        return {}


def _item_labels(keys):
    """{item_code: item_name} for the given codes, falling back to the code."""
    if not keys or not _has("Item"):
        return {}
    try:
        rows = frappe.get_all("Item", filters={"name": ["in", list(keys)]},
                              fields=["name", "item_name"], limit=0)
        return {r.name: (r.item_name or r.name) for r in rows}
    except Exception:
        return {}


# ---------------------------------------------------------------- endpoint 1
@frappe.whitelist()
def crm_command_center(date_from=None, date_to=None, customer=None):
    """KPI row, the upcoming tasks-and-events table, and follow-ups due."""
    _guard()
    frm, to = _range(date_from, date_to)
    p_frm, p_to = _prior(frm, to)
    scope = _scope(customer)

    upcoming = _upcoming(scope)
    follow_ups = _follow_ups(frm, to, scope, customer)

    return {
        "currency": _company_currency(),
        "range": {"from": frm, "to": to, "prev_from": p_frm, "prev_to": p_to},
        "kpis": _kpis(frm, to, p_frm, p_to, scope, customer, upcoming, follow_ups),
        "upcoming": upcoming,
        "follow_ups": follow_ups,
        # The cohort funnel, shared with Sales Analytics. `crm_dashboard_overview`
        # used to return a funnel built by counting each stage independently; it
        # could widen, and did. Only the stages travel to the client — the walk
        # also carries the full record lists, which the Overview has no use for.
        "funnel": _funnel(frm, to, scope),
    }


def _funnel(frm, to, scope):
    try:
        walk = cohort(frm, to, scope)
    except Exception:
        return []
    return walk["stages"]


def _kpis(frm, to, p_frm, p_to, scope, customer, upcoming, follow_ups):
    """The six tiles. Revenue and a bare open-task count are deliberately gone —
    revenue is the Sales Analytics band's job, and a count of tasks was a number
    with nothing to do about it."""
    ld = {**_df("Lead", "creation", frm, to), **_sf(scope, "Lead")}
    ld_prev = {**_df("Lead", "creation", p_frm, p_to), **_sf(scope, "Lead")}

    new_leads = _count("Lead", ld)
    new_leads_prev = _count("Lead", ld_prev)

    to_opp = _conversions(frm, to, scope)
    to_opp_prev = _conversions(p_frm, p_to, scope)

    pd = {**_df("Prospect", "creation", frm, to), **_sf(scope, "Prospect")}
    # The Customer tile drops the date window when an account is selected: the
    # user picked it, so "0 customers" because it predates the window reads as a
    # bug rather than as an answer. Same rule as crm_dashboard_overview.
    cd = _sf(scope, "Customer") if scope is not None else _df("Customer", "creation", frm, to)

    soon = [u for u in upcoming if u["bucket"] in ("today", "tomorrow", "week")]
    overdue = [u for u in upcoming if u["bucket"] == "overdue"]
    waiting = follow_ups.get("emails") or []
    calls_due = follow_ups.get("calls") or []
    oldest = max((cint(e.get("waiting_days")) for e in waiting), default=0)

    return {
        "new_leads": {
            "total": new_leads, "prev": new_leads_prev,
            "delta_pct": _pct(new_leads, new_leads_prev),
        },
        "to_opp": {
            "total": to_opp, "prev": to_opp_prev,
            "delta_pct": _pct(to_opp, to_opp_prev),
            # Cohort rate: of the leads created in this window, how many have
            # moved on. A different question from `total`, which counts moves
            # that happened in the window whenever the lead arrived.
            "conv_rate": round(
                _count("Lead", {**ld, "status": ["in", ["Opportunity", "Converted"]]})
                / new_leads * 100, 1) if new_leads else 0.0,
        },
        "prosp": {"total": _count("Prospect", pd)},
        "cust": {
            "active": _count("Customer", {**cd, "disabled": 0}),
            "companies": _count("Customer", {**cd, "customer_type": "Company", "disabled": 0}),
        },
        "upcoming": {
            "total": len(soon),
            "tasks": len([u for u in soon if u["kind"] == "task"]),
            "events": len([u for u in soon if u["kind"] == "event"]),
            "overdue": len(overdue),
        },
        "follow_ups": {
            "total": len(waiting) + len(calls_due),
            "emails": len(waiting),
            "calls": len(calls_due),
            "oldest_days": oldest,
        },
    }


def _conversions(frm, to, scope):
    """Leads that became opportunities *in this window*.

    Counted from the Opportunity side (`opportunity_from = 'Lead'`) rather than
    from Lead.status, because a status is a current state with no date attached —
    counting it would credit every historical conversion to whatever window is
    open. Deduplicated by source lead, since ERPNext lets several opportunities
    point at one lead.
    """
    if not _has("Opportunity") or not _hascol("Opportunity", "opportunity_from"):
        return 0
    filters = {
        "opportunity_from": "Lead",
        **_df("Opportunity", "transaction_date", frm, to),
        **_sf(scope, "Opportunity"),
    }
    try:
        rows = frappe.get_all("Opportunity", filters=filters, fields=["party_name"], limit=0)
        return len({r.party_name for r in rows if r.party_name}) or len(rows)
    except Exception:
        return _count("Opportunity", filters)


# ---------------------------------------------------------------- upcoming
TASK_FIELDS = (
    "name", "description", "priority", "status", "date", "allocated_to", "owner",
    "_assign", "reference_type", "reference_name", "color",
)
EVENT_FIELDS = (
    "name", "subject", "event_category", "event_type", "starts_on", "ends_on",
    "all_day", "status", "location", "owner", "_assign", "color",
)
BUCKET_RANK = {"overdue": 0, "today": 1, "tomorrow": 2, "week": 3, "later": 4}


def _bucket_for(when, today):
    if not when:
        return "later"
    try:
        d = getdate(when)
    except Exception:
        return "later"
    if d < today:
        return "overdue"
    if d == today:
        return "today"
    if d == add_days(today, 1):
        return "tomorrow"
    return "week" if (d - today).days <= UPCOMING_KPI_DAYS else "later"


def _upcoming(scope):
    """Open tasks and events as one chronological list.

    Deliberately **not** scoped to the header's date range: "upcoming" means from
    now forward, and a pill reading "Last 30 days" must not hide tomorrow's
    meeting. Same reasoning as `_targets` and `_aging` in api/analytics.py.

    Overdue tasks are included — they are the most actionable rows on the page —
    but only back 30 days, because this site carries 2,400 abandoned open ToDos
    and all of them would otherwise land here.
    """
    from upande_crm.api.crm import _crm_ref_doctypes

    today = getdate(nowdate())
    back = str(add_days(today, -UPCOMING_BACK_DAYS))
    forward = str(add_days(today, UPCOMING_FORWARD_DAYS))
    rows = []

    if _has("ToDo"):
        base = {"status": "Open", "date": ["between", [back, forward]]}
        if scope is not None:
            from upande_crm.api.scope import todo_names

            base["name"] = ["in", todo_names(scope) or [""]]
        # Same rule as _crm_todos: referencing a CRM doctype, or unlinked (which
        # is how a sales user jots down their own work).
        for extra in ({"reference_type": ["in", _crm_ref_doctypes()]},
                      {"reference_type": ["is", "not set"]}):
            for t in _rows("ToDo", list(TASK_FIELDS), {**base, **extra},
                           order_by="date asc", limit=UPCOMING_LIMIT):
                rows.append({
                    "kind": "task",
                    "name": t.get("name"),
                    "title": _strip(t.get("description")) or "Untitled task",
                    "when": str(t.get("date")) if t.get("date") else None,
                    "all_day": 1,
                    "meta": t.get("priority") or "Medium",
                    "priority": t.get("priority") or "Medium",
                    "who": t.get("allocated_to") or t.get("owner"),
                    "assign": t.get("_assign"),
                    "ref_doctype": t.get("reference_type"),
                    "ref_name": t.get("reference_name"),
                    "bucket": _bucket_for(t.get("date"), today),
                })

    if _has("Event"):
        ev = {
            "status": "Open",
            "starts_on": ["between", [f"{today} 00:00:00", f"{forward} 23:59:59"]],
        }
        if scope is not None:
            from upande_crm.api.scope import event_names

            ev["name"] = ["in", event_names(scope) or [""]]
        # Events are not read backwards: a meeting that already happened is not
        # overdue, it is just done with.
        for e in _rows("Event", list(EVENT_FIELDS), ev, order_by="starts_on asc",
                       limit=UPCOMING_LIMIT):
            rows.append({
                "kind": "event",
                "name": e.get("name"),
                "title": e.get("subject") or "Untitled event",
                "when": str(e.get("starts_on")) if e.get("starts_on") else None,
                "ends": str(e.get("ends_on")) if e.get("ends_on") else None,
                "all_day": cint(e.get("all_day")),
                "meta": e.get("event_category") or e.get("event_type") or "Event",
                "priority": "",
                "who": e.get("owner"),
                "assign": e.get("_assign"),
                "location": e.get("location"),
                "ref_doctype": None,
                "ref_name": None,
                "bucket": _bucket_for(e.get("starts_on"), today),
            })

    rows.sort(key=lambda r: (BUCKET_RANK.get(r["bucket"], 9), r["when"] or "9999"))
    return rows[:UPCOMING_LIMIT]


def _strip(html):
    """ToDo.description is rich text; the table wants one line of it."""
    if not html:
        return ""
    try:
        from frappe.utils import strip_html

        text = strip_html(html)
    except Exception:
        text = str(html)
    return " ".join(text.split())[:180]


# ---------------------------------------------------------------- follow-ups
def _follow_ups(frm, to, scope, customer):
    """Two lists of work that is waiting on someone: unanswered mail, and calls
    where nobody was reached."""
    return {"emails": _awaiting_reply(frm, to, scope), "calls": _calls_due(frm, to, customer)}


def _awaiting_reply(frm, to, scope):
    """Sent CRM mail with no reply since, one row per record, oldest first.

    "No reply" is `not exists (a Received communication on the same reference,
    later)` — the same reference thread, not the same subject, because subjects
    get edited and references do not.
    """
    if not _has("Communication"):
        return []
    refs = ", ".join(frappe.db.escape(r) for r in EMAIL_REFS)
    scope_sql = ""
    if scope is not None:
        names = [n for names in scope.values() for n in names] or [""]
        quoted = ", ".join(frappe.db.escape(n) for n in names)
        scope_sql = f" and c.reference_name in ({quoted})"
    try:
        rows = frappe.db.sql(
            f"""select c.name, c.subject, c.recipients, c.sender,
                       c.communication_date, c.reference_doctype, c.reference_name,
                       datediff(%s, date(c.communication_date)) waiting_days
                from `tabCommunication` c
                where c.communication_type = 'Communication'
                  and c.sent_or_received = 'Sent'
                  and c.reference_doctype in ({refs})
                  and coalesce(c.reference_name, '') != ''
                  and c.communication_date between %s and %s
                  {scope_sql}
                  and not exists (
                      select 1 from `tabCommunication` r
                      where r.communication_type = 'Communication'
                        and r.sent_or_received = 'Received'
                        and r.reference_doctype = c.reference_doctype
                        and r.reference_name = c.reference_name
                        and r.communication_date > c.communication_date)
                order by c.communication_date desc""",
            (str(getdate(nowdate())), frm, f"{to} 23:59:59"),
            as_dict=True,
        )
    except Exception:
        return []

    # One row per record: the latest unanswered send is the one to chase.
    seen, out = set(), []
    for r in rows:
        key = (r.reference_doctype, r.reference_name)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "name": r.name,
            "subject": r.subject or "(no subject)",
            "recipients": r.recipients or "",
            "sender": r.sender or "",
            "sent_on": str(r.communication_date) if r.communication_date else None,
            "waiting_days": max(cint(r.waiting_days), 0),
            "ref_doctype": r.reference_doctype,
            "ref_name": r.reference_name,
        })
    # Longest-waiting first: that is the order they should be worked.
    out.sort(key=lambda r: -r["waiting_days"])
    return out[:FOLLOW_UP_LIMIT]


def _calls_due(frm, to, customer):
    """Calls where nobody was reached, newest first."""
    if not _has("Call Log"):
        return []
    from upande_crm.api.calls import _attach_links, _scope_names

    filters = {
        "status": ["in", list(MISSED_CALL_STATUSES)],
        **_df("Call Log", "start_time", frm, to),
    }
    if customer:
        filters["name"] = ["in", _scope_names(customer) or [""]]
    rows = _rows("Call Log", [
        "name", "type", "status", "from", "to", "start_time", "customer", "owner",
        "summary", "type_of_call",
    ], filters, order_by="start_time desc", limit=FOLLOW_UP_LIMIT)
    return _attach_links(rows)


# ---------------------------------------------------------------- endpoint 2
@frappe.whitelist()
def crm_sales_track_record(date_from=None, date_to=None, customer=None):
    """The track-record chart, the movers band, top sellers, and rep scorecards.

    Split out from `crm_command_center` so the KPI row and the day's work render
    without waiting on the per-item aggregation behind all of this.
    """
    _guard()
    frm, to = _range(date_from, date_to)
    p_frm, p_to = _prior(frm, to)

    flowers = _rank(_item_totals(frm, to, customer), SERIES_LIMIT)
    reps = _rep_totals(frm, to, customer)

    return {
        "currency": _company_currency(),
        "range": {"from": frm, "to": to, "prev_from": p_frm, "prev_to": p_to},
        "track_record": _track_record(frm, to, customer, flowers, reps[:SERIES_LIMIT]),
        "movers": _movers(frm, to, p_frm, p_to, customer),
        "top_sellers": _top_sellers(frm, to, p_frm, p_to, customer),
        "rep_performance": _rep_performance(frm, to, p_frm, p_to, reps, customer),
        "rep_conversion": _rep_conversion(frm, to, _scope(customer)),
    }


def _rank(totals, limit):
    """A {key: {...}} map as a ranked list of the top `limit` by amount."""
    ordered = sorted(totals.items(), key=lambda kv: -kv[1]["amount"])[:limit]
    labels = _item_labels([k for k, _ in ordered])
    return [
        {"key": k, "label": labels.get(k, k), "amount": v["amount"],
         "qty": v["qty"], "orders": v["orders"]}
        for k, v in ordered
    ]


def _rep_totals(frm, to, customer=None, limit=20):
    """Reps ranked by order value. Order-level `base_grand_total`, so these agree
    with Booked in the sales band rather than with line values."""
    if not _has("Sales Order") or not _hascol("Sales Order", "owner"):
        return []
    try:
        rows = frappe.db.sql(
            f"""select so.owner k,
                       coalesce(sum(so.base_grand_total), 0) amount,
                       count(*) orders,
                       count(distinct so.customer) customers
                from `tabSales Order` so
                where so.docstatus = 1
                  and so.transaction_date between %s and %s{_cust(customer, 'so')}
                group by so.owner order by amount desc limit %s""",
            (frm, to, int(limit)), as_dict=True,
        )
        return [
            {"key": r.k or "Unknown", "label": _short(r.k), "amount": flt(r.amount),
             "orders": cint(r.orders), "customers": cint(r.customers)}
            for r in rows
        ]
    except Exception:
        return []


# ---------------------------------------------------------------- track record
def _track_record(frm, to, customer, flowers, reps):
    """Bucketed series for the multi-line chart, by flower and by salesperson.

    Series are keyed `s0..sN` rather than by item code or email: recharts reads a
    dataKey as a path, so a key containing a dot would silently resolve to
    nothing. The `series` list carries the real key and its label.
    """
    template, label_of, grain = _buckets(frm, to)

    flower_rows = _series(
        template.format(col="so.transaction_date"),
        [f["key"] for f in flowers], "soi.item_code", customer, frm, to, item_level=True,
    )
    rep_rows = _series(
        template.format(col="so.transaction_date"),
        [r["key"] for r in reps], "so.owner", customer, frm, to, item_level=False,
    )

    return {
        "grain": grain,
        "flower": _pivot(flowers, flower_rows, label_of),
        "rep": _pivot(reps, rep_rows, label_of),
    }


def _series(bucket_expr, keys, group_col, customer, frm, to, item_level):
    """[(bucket, key, revenue, stems)] for the given keys.

    `item_level` picks where revenue comes from: a flower's revenue can only be
    line value (`base_amount`), while a rep's is the order total
    (`base_grand_total`) so it reconciles with Booked. Stems always come from the
    line, since only lines carry quantity — which is why the rep query joins the
    child table even though its revenue does not need it.
    """
    if not keys or not _sold():
        return []
    quoted = ", ".join(frappe.db.escape(k) for k in keys)
    try:
        if item_level:
            return frappe.db.sql(
                f"""select {bucket_expr} bucket, {group_col} k,
                           coalesce(sum(soi.base_amount), 0) revenue,
                           coalesce(sum(soi.qty), 0) stems
                    from `tabSales Order Item` soi
                    join `tabSales Order` so on so.name = soi.parent
                    where so.docstatus = 1
                      and so.transaction_date between %s and %s
                      and {group_col} in ({quoted}){_cust(customer, 'so')}
                    group by bucket, k order by bucket""",
                (frm, to), as_dict=True,
            )
        # One row per order, then summed per bucket: aggregating over the join
        # would multiply each order total by its line count.
        return frappe.db.sql(
            f"""select bucket, k, coalesce(sum(revenue), 0) revenue,
                       coalesce(sum(stems), 0) stems
                from (
                    select {bucket_expr} bucket, {group_col} k, so.name,
                           so.base_grand_total revenue,
                           (select coalesce(sum(qty), 0) from `tabSales Order Item`
                             where parent = so.name) stems
                    from `tabSales Order` so
                    where so.docstatus = 1
                      and so.transaction_date between %s and %s
                      and {group_col} in ({quoted}){_cust(customer, 'so')}
                ) x
                group by bucket, k order by bucket""",
            (frm, to), as_dict=True,
        )
    except Exception:
        return []


def _pivot(ranked, rows, label_of):
    """Long rows → {series, revenue, stems} in the shape recharts wants."""
    series = [
        {"id": f"s{i}", "key": r["key"], "label": r["label"],
         "total": r["amount"], "stems": r.get("qty", 0)}
        for i, r in enumerate(ranked)
    ]
    by_key = {s["key"]: s["id"] for s in series}
    buckets, rev, stems = [], {}, {}
    for r in rows:
        sid = by_key.get(r.get("k"))
        if not sid:
            continue
        b = r.get("bucket")
        if b not in rev:
            buckets.append(b)
            rev[b], stems[b] = {}, {}
        rev[b][sid] = flt(r.get("revenue"))
        stems[b][sid] = flt(r.get("stems"))
    buckets.sort()

    def frame(store):
        return [
            {"label": label_of(b), "bucket": b,
             **{s["id"]: store.get(b, {}).get(s["id"], 0.0) for s in series}}
            for b in buckets
        ]

    return {"series": series, "revenue": frame(rev), "stems": frame(stems)}


# ---------------------------------------------------------------- movers
def _movers(frm, to, p_frm, p_to, customer=None):
    """Biggest revenue movers by flower, against the preceding window.

    Every variety is aggregated in both windows rather than only the current
    top-N: the largest decline on any farm is a variety that sold well *last*
    period and is absent from this one, and a current-top-N list is exactly where
    that row is missing.
    """
    cur = _item_totals(frm, to, customer)
    prev = _item_totals(p_frm, p_to, customer)
    keys = set(cur) | set(prev)
    if not keys:
        return {"declines": [], "gains": [], "count": 0}

    labels = _item_labels(keys)
    rows = []
    for k in keys:
        c = cur.get(k) or {"amount": 0.0, "qty": 0.0, "orders": 0}
        p = prev.get(k) or {"amount": 0.0, "qty": 0.0, "orders": 0}
        volume, price = _decompose(p["amount"], p["qty"], c["amount"], c["qty"])
        rows.append({
            "key": k, "label": labels.get(k, k),
            "amount": c["amount"], "prev": p["amount"],
            "qty": c["qty"], "prev_qty": p["qty"],
            "delta": c["amount"] - p["amount"],
            "delta_pct": _pct(c["amount"], p["amount"]),
            "qty_delta_pct": _pct(c["qty"], p["qty"]),
            "volume_effect": volume, "price_effect": price,
            "rate": (c["amount"] / c["qty"]) if c["qty"] else 0.0,
            "prev_rate": (p["amount"] / p["qty"]) if p["qty"] else 0.0,
            "stopped": bool(p["amount"] and not c["amount"]),
            "started": bool(c["amount"] and not p["amount"]),
            "driver": "volume" if abs(volume) >= abs(price) else "price",
        })

    declines = sorted([r for r in rows if r["delta"] < 0], key=lambda r: r["delta"])
    gains = sorted([r for r in rows if r["delta"] > 0], key=lambda r: -r["delta"])
    return {
        "declines": declines[:MOVER_LIMIT],
        "gains": gains[:MOVER_LIMIT],
        "count": len(rows),
    }


# ---------------------------------------------------------------- top sellers
def _top_sellers(frm, to, p_frm, p_to, customer=None):
    """The three views the Overview offers over the same five varieties:
    a customer x flower matrix, each account's own top five, and the reps behind
    them."""
    top = _rank(_item_totals(frm, to, customer), SELLER_COLS)
    keys = [t["key"] for t in top]

    return {
        "varieties": top,
        "matrix": _seller_matrix(frm, to, p_frm, p_to, keys, customer),
        "per_customer": _per_customer_top(frm, to, customer),
        "by_rep": _by_rep_customers(frm, to, customer),
    }


def _cell_rows(frm, to, keys, customer=None, limit=0):
    """[(customer, item_code, amount, qty)] for the given varieties."""
    if not keys or not _sold():
        return []
    quoted = ", ".join(frappe.db.escape(k) for k in keys)
    try:
        return frappe.db.sql(
            f"""select so.customer c, soi.item_code k,
                       coalesce(sum(soi.base_amount), 0) amount,
                       coalesce(sum(soi.qty), 0) qty
                from `tabSales Order Item` soi
                join `tabSales Order` so on so.name = soi.parent
                where so.docstatus = 1
                  and so.transaction_date between %s and %s
                  and soi.item_code in ({quoted}){_cust(customer, 'so')}
                group by so.customer, soi.item_code""",
            (frm, to), as_dict=True,
        )
    except Exception:
        return []


def _seller_matrix(frm, to, p_frm, p_to, keys, customer=None):
    """Rows = top customers, columns = the five varieties.

    A missing cell is returned as None rather than 0: an account that does not
    buy a house-top variety is a different fact from one that bought none this
    period, and the table renders them differently.
    """
    cur = _cell_rows(frm, to, keys, customer)
    prev = _cell_rows(p_frm, p_to, keys, customer)
    if not cur and not prev:
        return []

    def index(rows):
        out = {}
        for r in rows:
            out.setdefault(r.c or "Unknown", {})[r.k] = {
                "amount": flt(r.amount), "qty": flt(r.qty)}
        return out

    ci, pi = index(cur), index(prev)
    totals = {c: sum(v["amount"] for v in cells.values()) for c, cells in ci.items()}
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])[:SELLER_ROWS]

    rows = []
    for name, total in ranked:
        cells = {}
        for k in keys:
            c = ci.get(name, {}).get(k)
            p = pi.get(name, {}).get(k)
            if not c and not p:
                cells[k] = None
                continue
            amount = (c or {}).get("amount", 0.0)
            before = (p or {}).get("amount", 0.0)
            cells[k] = {
                "amount": amount, "qty": (c or {}).get("qty", 0.0),
                "prev": before, "delta_pct": _pct(amount, before),
                "stopped": bool(before and not amount),
            }
        prev_total = sum(v["amount"] for v in pi.get(name, {}).values())
        rows.append({
            "customer": name, "total": total, "prev_total": prev_total,
            "delta_pct": _pct(total, prev_total), "cells": cells,
        })
    return rows


def _per_customer_top(frm, to, customer=None, top=5):
    """Each leading account's own best-selling varieties — a small account's mix
    is not the house mix, which is the whole point of showing this beside the
    matrix."""
    if not _sold():
        return []
    try:
        rows = frappe.db.sql(
            f"""select so.customer c, soi.item_code k,
                       coalesce(sum(soi.base_amount), 0) amount,
                       coalesce(sum(soi.qty), 0) qty
                from `tabSales Order Item` soi
                join `tabSales Order` so on so.name = soi.parent
                where so.docstatus = 1
                  and so.transaction_date between %s and %s{_cust(customer, 'so')}
                group by so.customer, soi.item_code""",
            (frm, to), as_dict=True,
        )
    except Exception:
        return []

    by_cust = {}
    for r in rows:
        by_cust.setdefault(r.c or "Unknown", []).append(
            {"key": r.k, "amount": flt(r.amount), "qty": flt(r.qty)})
    labels = _item_labels({r.k for r in rows})

    out = []
    for name, items in by_cust.items():
        items.sort(key=lambda i: -i["amount"])
        out.append({
            "customer": name,
            "total": sum(i["amount"] for i in items),
            "varieties": len(items),
            "top": [{**i, "label": labels.get(i["key"], i["key"])} for i in items[:top]],
        })
    out.sort(key=lambda r: -r["total"])
    return out[:SELLER_ROWS]


def _by_rep_customers(frm, to, customer=None, top=5):
    """Top reps, each with the accounts behind their number."""
    reps = _rep_totals(frm, to, customer, limit=SELLER_COLS)
    if not reps:
        return []
    quoted = ", ".join(frappe.db.escape(r["key"]) for r in reps)
    try:
        rows = frappe.db.sql(
            f"""select so.owner o, so.customer c,
                       coalesce(sum(so.base_grand_total), 0) amount, count(*) orders
                from `tabSales Order` so
                where so.docstatus = 1
                  and so.transaction_date between %s and %s
                  and so.owner in ({quoted}){_cust(customer, 'so')}
                group by so.owner, so.customer""",
            (frm, to), as_dict=True,
        )
    except Exception:
        rows = []

    by_rep = {}
    for r in rows:
        by_rep.setdefault(r.o, []).append(
            {"customer": r.c or "Unknown", "amount": flt(r.amount), "orders": cint(r.orders)})
    out = []
    for rep in reps:
        accounts = sorted(by_rep.get(rep["key"], []), key=lambda a: -a["amount"])
        out.append({**rep, "accounts": accounts[:top], "account_count": len(accounts)})
    return out


# ---------------------------------------------------------------- rep scorecard
def _rep_performance(frm, to, p_frm, p_to, reps, customer=None):
    """Result beside effort: what each rep sold, and what they did.

    The activity columns are keyed on the same user the revenue is — so a rep with
    falling revenue and no calls logged reads as one row, not two reports.
    """
    if not reps:
        return []
    reps = reps[:SELLER_ROWS]
    keys = [r["key"] for r in reps]
    prev = {r["key"]: r for r in _rep_totals(p_frm, p_to, customer, limit=200)}
    stems = _rep_stems(frm, to, keys, customer)
    activity = _rep_activity(frm, to, keys)

    out = []
    for r in reps:
        before = (prev.get(r["key"]) or {}).get("amount", 0.0)
        s = stems.get(r["key"]) or {"qty": 0.0, "varieties": 0}
        out.append({
            **r,
            "prev": before,
            "delta_pct": _pct(r["amount"], before),
            "aov": round(r["amount"] / r["orders"], 2) if r["orders"] else 0.0,
            "stems": s["qty"],
            "varieties": s["varieties"],
            "activity": activity.get(r["key"], {
                "calls": 0, "emails": 0, "tasks": 0, "events": 0}),
        })
    return out


# ---------------------------------------------------------------- rep conversion
def _rep_conversion(frm, to, scope):
    """How far each salesperson gets the leads they own.

    Keyed on `Lead.lead_owner`, **not** on the Sales Order `owner` that the rest
    of this module calls a salesperson. Measured on this site: `lead_owner` has 14
    distinct values against `Lead.owner`'s 46 Guest / 31 Administrator, so `owner`
    records who imported the row rather than who works it. The price is that the
    two rep cards do not share a population — only six users appear in both — and
    that is exactly why this is its own card rather than three more columns on the
    scorecard above, where thirteen of nineteen rows would read as dashes.

    Progression comes from document linkage (via `api/funnel.py`, so this card and
    the funnel cannot disagree), never from `Lead.status`: the status is set by a
    workflow that does not always fire, and counting it would credit a rep for a
    field somebody typed.
    """
    if not _has("Lead") or not _hascol("Lead", "lead_owner"):
        return []
    try:
        walk = cohort(frm, to, scope)
    except Exception:
        return []

    leads = walk["leads"]
    if not leads:
        return []

    owner_of = {}
    try:
        for r in frappe.get_all("Lead", filters={"name": ["in", leads]},
                                fields=["name", "lead_owner"], limit=0):
            owner_of[r.name] = r.lead_owner or ""
    except Exception:
        return []

    reached = set(walk["leads_reached_opp"])
    closed = set(walk["leads_won"])

    tally = {}
    for lead in leads:
        # Guest, Administrator and blank are one bucket. On this site that is 63 of
        # 112 leads — the largest row on the card, and the finding in it: most
        # leads have nobody working them. Splitting it three ways would hide that.
        raw = owner_of.get(lead) or ""
        key = raw if raw and raw not in UNOWNED else UNASSIGNED
        t = tally.setdefault(key, {"leads": 0, "to_opp": 0, "won": 0})
        t["leads"] += 1
        if lead in reached:
            t["to_opp"] += 1
        if lead in closed:
            t["won"] += 1

    rows = [
        {
            "key": key,
            "label": _rep_label(key),
            "unassigned": key == UNASSIGNED,
            "leads": v["leads"],
            "to_opp": v["to_opp"],
            "won": v["won"],
            "opp_rate": _pct_of(v["to_opp"], v["leads"]),
            "rate": _pct_of(v["won"], v["leads"]),
        }
        for key, v in tally.items()
    ]
    # Sorted by lead count, not by rate. One lead converted is not a 100% closer,
    # and rate-sorting puts that row on top. The bar in the UI still ranks by rate,
    # so nothing is hidden — the ordering just stops overstating a sample of one.
    #
    # Unassigned is held out of the top-N and appended, rather than sorted last and
    # then truncated with everything else. It is the largest row on this site — 63
    # of 112 leads — so letting the limit eat it would drop the card's main finding
    # to make room for a rep with two leads.
    named = [r for r in rows if not r["unassigned"]]
    unassigned = [r for r in rows if r["unassigned"]]
    named.sort(key=lambda r: (-r["leads"], r["label"]))
    return named[:CONVERSION_ROWS] + unassigned


def _rep_label(key):
    if key == UNASSIGNED:
        return "Unassigned"
    try:
        return frappe.db.get_value("User", key, "full_name") or key
    except Exception:
        return key


def _pct_of(part, whole):
    return round(part / whole * 100, 1) if whole else 0.0


def _rep_stems(frm, to, keys, customer=None):
    """{rep: {qty, varieties}} — stems shipped and how wide a range they sold."""
    if not keys or not _sold():
        return {}
    quoted = ", ".join(frappe.db.escape(k) for k in keys)
    try:
        rows = frappe.db.sql(
            f"""select so.owner k, coalesce(sum(soi.qty), 0) qty,
                       count(distinct soi.item_code) varieties
                from `tabSales Order Item` soi
                join `tabSales Order` so on so.name = soi.parent
                where so.docstatus = 1
                  and so.transaction_date between %s and %s
                  and so.owner in ({quoted}){_cust(customer, 'so')}
                group by so.owner""",
            (frm, to), as_dict=True,
        )
        return {r.k: {"qty": flt(r.qty), "varieties": cint(r.varieties)} for r in rows}
    except Exception:
        return {}


def _rep_activity(frm, to, keys):
    """{rep: {calls, emails, tasks, events}} in one query per source.

    Each source is counted per-user in a single grouped query rather than one
    query per rep per source, which would be 32 round trips for eight reps.
    """
    out = {k: {"calls": 0, "emails": 0, "tasks": 0, "events": 0} for k in keys}
    if not keys:
        return out
    quoted = ", ".join(frappe.db.escape(k) for k in keys)

    def tally(field, doctype, col, where, params, dated=True):
        if not _has(doctype) or not _hascol(doctype, col):
            return
        try:
            rows = frappe.db.sql(
                f"""select {col} k, count(*) n from `tab{doctype}`
                    where {col} in ({quoted}) and {where}
                    group by {col}""",
                params, as_dict=True)
            for r in rows:
                if r.k in out:
                    out[r.k][field] = cint(r.n)
        except Exception:
            pass

    tally("calls", "Call Log", "owner", "start_time between %s and %s",
          (frm, f"{to} 23:59:59"))
    tally("emails", "Communication", "sender",
          "communication_type = 'Communication' and sent_or_received = 'Sent'"
          " and communication_date between %s and %s", (frm, f"{to} 23:59:59"))
    # Open work is current state, not a window: how much is on someone's plate
    # right now is the question, and a date filter would answer a different one.
    tally("tasks", "ToDo", "allocated_to", "status = 'Open'", ())
    tally("events", "Event", "owner",
          "status = 'Open' and starts_on >= %s", (str(getdate(nowdate())),))
    return out


# ---------------------------------------------------------------- endpoint 3
@frappe.whitelist()
def crm_mover_detail(kind, key, date_from=None, date_to=None, customer=None):
    """Why a flower or a rep moved — fetched only when a drill is opened.

    Returns the exact volume/price split, ranked per-account and cross-dimension
    contributions, a longer monthly series for context, and the same window a year
    earlier where invoices reach that far back.
    """
    _guard()
    if kind not in ("flower", "rep"):
        frappe.throw("Unknown mover kind")
    if not key:
        frappe.throw("Nothing to explain")

    frm, to = _range(date_from, date_to)
    p_frm, p_to = _prior(frm, to)
    where = f" and {DRILL_DIMS[kind]['col']} = %s"

    # Group by the drill's own dimension, so the result is exactly one row: the
    # subject's total. Grouping by the default (item_code) would split a rep's
    # sales across every variety they sold, and taking the first group would then
    # report one arbitrary variety as the rep's whole number.
    own = DRILL_DIMS[kind]["col"]
    cur = _item_totals(frm, to, customer, group_col=own, extra=where, params=(key,))
    prev = _item_totals(p_frm, p_to, customer, group_col=own, extra=where, params=(key,))
    # The single group, or nothing when the subject did not sell in that window.
    c = next(iter(cur.values()), {"amount": 0.0, "qty": 0.0, "orders": 0})
    p = next(iter(prev.values()), {"amount": 0.0, "qty": 0.0, "orders": 0})
    volume, price = _decompose(p["amount"], p["qty"], c["amount"], c["qty"])

    # A flower is explained by who bought it and who sold it; a rep by what they
    # sold and to whom.
    dims = ("customer", "rep") if kind == "flower" else ("flower", "customer")

    return {
        "currency": _company_currency(),
        "kind": kind,
        "key": key,
        "label": _item_labels([key]).get(key, key) if kind == "flower" else _short(key),
        "range": {"from": frm, "to": to, "prev_from": p_frm, "prev_to": p_to},
        "totals": {
            "amount": c["amount"], "prev": p["amount"],
            "delta": c["amount"] - p["amount"],
            "delta_pct": _pct(c["amount"], p["amount"]),
            "qty": c["qty"], "prev_qty": p["qty"],
            "qty_delta_pct": _pct(c["qty"], p["qty"]),
            "orders": c["orders"], "prev_orders": p["orders"],
            "rate": (c["amount"] / c["qty"]) if c["qty"] else 0.0,
            "prev_rate": (p["amount"] / p["qty"]) if p["qty"] else 0.0,
            "volume_effect": volume,
            "price_effect": price,
            "driver": "volume" if abs(volume) >= abs(price) else "price",
        },
        "contributions": {
            d: _contributions(d, kind, key, frm, to, p_frm, p_to, customer) for d in dims
        },
        "monthly": _drill_monthly(kind, key, to, customer),
        "year_ago": _year_ago(kind, key, frm, to, customer),
    }


def _contributions(dim, kind, key, frm, to, p_frm, p_to, customer=None):
    """Who moved, ranked most-negative first.

    An account with revenue before and none now is flagged `stopped` rather than
    "-100%": the two read differently to whoever has to act on the row.
    """
    if dim == kind:
        return {"down": [], "up": []}
    col = DRILL_DIMS[dim]["col"]
    where = f" and {DRILL_DIMS[kind]['col']} = %s"
    cur = _item_totals(frm, to, customer, group_col=col, extra=where, params=(key,))
    prev = _item_totals(p_frm, p_to, customer, group_col=col, extra=where, params=(key,))

    labels = _item_labels(set(cur) | set(prev)) if dim == "flower" else {}
    rows = []
    for k in set(cur) | set(prev):
        c = cur.get(k) or {"amount": 0.0, "qty": 0.0, "orders": 0}
        p = prev.get(k) or {"amount": 0.0, "qty": 0.0, "orders": 0}
        label = labels.get(k, k) if dim == "flower" else (_short(k) if dim == "rep" else k)
        rows.append({
            "key": k, "label": label,
            "amount": c["amount"], "prev": p["amount"],
            "delta": c["amount"] - p["amount"],
            "delta_pct": _pct(c["amount"], p["amount"]),
            "qty": c["qty"], "prev_qty": p["qty"],
            "stopped": bool(p["amount"] and not c["amount"]),
            "started": bool(c["amount"] and not p["amount"]),
        })
    rows.sort(key=lambda r: r["delta"])
    down = [r for r in rows if r["delta"] < 0][:DRILL_LIMIT]
    up = [r for r in rows if r["delta"] > 0]
    up.sort(key=lambda r: -r["delta"])
    return {"down": down, "up": up[:DRILL_LIMIT]}


def _drill_monthly(kind, key, to, customer=None, months=DRILL_MONTHS):
    """A year of monthly totals, so a dip can be read against its own history
    rather than against one preceding window."""
    if not _sold():
        return []
    try:
        end = getdate(to)
        start = add_months(end.replace(day=1), -(months - 1))
    except Exception:
        return []
    col = DRILL_DIMS[kind]["col"]
    try:
        rows = frappe.db.sql(
            f"""select date_format(so.transaction_date, '%%Y-%%m') bucket,
                       coalesce(sum(soi.base_amount), 0) amount,
                       coalesce(sum(soi.qty), 0) qty
                from `tabSales Order Item` soi
                join `tabSales Order` so on so.name = soi.parent
                where so.docstatus = 1
                  and so.transaction_date between %s and %s
                  and {col} = %s{_cust(customer, 'so')}
                group by bucket order by bucket""",
            (str(start), str(end), key), as_dict=True,
        )
        return [
            {"label": r.bucket[2:], "bucket": r.bucket,
             "amount": flt(r.amount), "qty": flt(r.qty)}
            for r in rows
        ]
    except Exception:
        return []


def _year_ago(kind, key, frm, to, customer=None):
    """The same window one year earlier, from invoices.

    Read from Sales Invoice rather than Sales Order because orders on this site
    only begin in late 2025 while invoices reach back to 2022 — without this a
    seasonal trough would be indistinguishable from a lost account. Labelled
    `invoiced` for that reason: it is not the same measure as the rest of the
    drill, and the UI says so.
    """
    if not _has("Sales Invoice") or not _has("Sales Invoice Item"):
        return None
    col = "sii.item_code" if kind == "flower" else "si.owner"
    try:
        y_frm, y_to = str(add_months(getdate(frm), -12)), str(add_months(getdate(to), -12))
        row = frappe.db.sql(
            f"""select coalesce(sum(sii.base_amount), 0) amount,
                       coalesce(sum(sii.qty), 0) qty
                from `tabSales Invoice Item` sii
                join `tabSales Invoice` si on si.name = sii.parent
                where si.docstatus = 1
                  and si.posting_date between %s and %s
                  and {col} = %s{_cust(customer, 'si')}""",
            (y_frm, y_to, key),
        )[0]
    except Exception:
        return None
    amount = flt(row[0])
    if not amount:
        return None
    return {"amount": amount, "qty": flt(row[1]), "from": y_frm, "to": y_to,
            "basis": "invoiced"}
