"""Delivery points: who ships through which handler out of Nairobi.

Everything here is origin-side. `Delivery Point Flowers` sounds like a
destination but its 41 rows are freight handlers at Jomo Kenyatta International
Airport — AIRFLO, MITCHEL COTTS, EXPOLANKA, AFS, Agrotronics Freight Avenue.
Every flower leaving these farms goes through one of them, so on a world map
they would all stack on a single pixel over Nairobi. They earn a view of their
own instead.

The usable field is not the master list but `Sales Order.custom_delivery_point`,
populated on 9,806 of 11,323 orders, which is what ties a handler to the
customers and volume moving through it.

## On the coordinates

There are none. No delivery point on this site carries a latitude, longitude or
address, and inventing surveyed positions for freight sheds would be fabricating
data that reads as authoritative. So `crm_delivery_points` returns rank and
volume, and the UI arranges the handlers radially around the JKIA marker as a
**schematic** — labelled as such on screen. The ring says "these all move through
this airport, and this is how much each carries"; it does not claim to say where
the warehouses stand.
"""

import frappe
from frappe.utils import flt

from upande_crm.api.crm import _guard, _has, _hascol, _range

# Jomo Kenyatta International Airport, Nairobi. The hub every delivery point
# here feeds; used as the anchor the schematic ring is drawn around.
JKIA = {
    "code": "NBO",
    "name": "Jomo Kenyatta International Airport",
    "city": "Nairobi",
    "territory": "Kenya",
    "lonlat": [36.9278, -1.3192],
}

FIELD = "custom_delivery_point"


def _available():
    return _has("Sales Order") and _hascol("Sales Order", FIELD)


@frappe.whitelist()
def crm_delivery_points(date_from=None, date_to=None, limit=40):
    """Handlers at JKIA, ranked by order volume, with customer counts."""
    _guard()
    frm, to = _range(date_from, date_to)
    limit = min(int(limit or 40), 100)
    if not _available():
        return {"hub": JKIA, "points": [], "unrouted": 0, "currency": None}

    from upande_crm.api.analytics import _company_currency

    try:
        rows = frappe.db.sql(
            f"""select `{FIELD}` label,
                       count(*) orders,
                       count(distinct customer) customers,
                       coalesce(sum(base_grand_total), 0) value,
                       max(transaction_date) last
                from `tabSales Order`
                where ifnull(`{FIELD}`, '') <> '' and docstatus = 1
                  and transaction_date between %s and %s
                group by label order by orders desc limit %s""",
            (frm, to, limit),
            as_dict=True,
        )
        # Orders that never named a handler. Reported rather than ignored: the
        # ring otherwise implies every shipment is accounted for.
        unrouted = frappe.db.sql(
            f"""select count(*) from `tabSales Order`
                where ifnull(`{FIELD}`, '') = '' and docstatus = 1
                  and transaction_date between %s and %s""",
            (frm, to),
        )[0][0]
    except Exception:
        frappe.clear_last_message()
        return {"hub": JKIA, "points": [], "unrouted": 0, "currency": None}

    return {
        "hub": JKIA,
        "currency": _company_currency(),
        "date_from": frm,
        "date_to": to,
        "points": [
            {
                "label": r.label,
                "orders": int(r.orders or 0),
                "customers": int(r.customers or 0),
                "value": flt(r.value),
                "last": str(r.last or ""),
            }
            for r in rows
        ],
        "unrouted": int(unrouted or 0),
        # Positions are a schematic ring, not survey data. Stated in the payload
        # so a future consumer cannot mistake the arrangement for geography.
        "positions_are_schematic": True,
    }


@frappe.whitelist()
def crm_delivery_point_detail(point, date_from=None, date_to=None, limit=12):
    """Customers and destinations moving through one handler."""
    _guard()
    if not point or not _available():
        return {}
    frm, to = _range(date_from, date_to)
    limit = min(int(limit or 12), 50)

    from upande_crm.api.analytics import _company_currency

    def q(sql, params):
        try:
            return frappe.db.sql(sql, params, as_dict=True)
        except Exception:
            frappe.clear_last_message()
            return []

    customers = q(
        f"""select so.customer label, count(*) orders,
                   coalesce(sum(so.base_grand_total), 0) value,
                   max(so.territory) territory
            from `tabSales Order` so
            where so.`{FIELD}` = %s and so.docstatus = 1
              and so.transaction_date between %s and %s
            group by so.customer order by value desc limit %s""",
        (point, frm, to, limit),
    )

    # Where this handler's shipments actually end up — the one place the
    # origin-side view reconnects to the world map.
    destinations = q(
        f"""select coalesce(nullif(so.territory, ''), 'Untagged') label,
                   count(*) orders,
                   coalesce(sum(so.base_grand_total), 0) value
            from `tabSales Order` so
            where so.`{FIELD}` = %s and so.docstatus = 1
              and so.transaction_date between %s and %s
            group by label order by value desc limit %s""",
        (point, frm, to, limit),
    )

    return {
        "point": point,
        "currency": _company_currency(),
        "customers": customers,
        "destinations": destinations,
    }
