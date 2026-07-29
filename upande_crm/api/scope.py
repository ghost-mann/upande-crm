"""Resolve "everything about this customer" into per-doctype name lists.

The header's customer pill used to be a lie: eight endpoints accepted a
`customer` argument and four ignored it outright, so picking a customer narrowed
the revenue figure and left the funnel, the lead counts, the tasks and the whole
sales band global.

The hard part is not the plumbing, it is *what a customer's leads even are* — a
Lead is not a Customer yet. Rather than let each endpoint invent an answer, that
definition lives here once, and every reader applies the same one.

## The chain, as this site actually links records

Measured on kaitet.local: `Lead.customer` is a real Link (Lead -> Customer);
`Customer` carries `lead_name`, `prospect_name` and `opportunity_name` back to
whatever it was converted from; `Opportunity.party_name` is a Dynamic Link keyed
by `opportunity_from` (45 from Lead, 8 from Prospect, 6 from Customer); the same
shape holds for `Quotation.party_name` / `quotation_to`; `Prospect` has no
Customer link at all, only child tables of its leads and opportunities.

So the scope is walked forwards, each step using what the previous one found:

    leads         Lead.customer = X, plus the Lead that X was converted from
    prospects     X.prospect_name, plus prospects whose child `leads` rows
                  reference one of those leads
    opportunities party_name = X, plus X.opportunity_name, plus opportunities
                  whose party is one of the resolved leads or prospects
    quotations    party_name = X, plus quotations against a resolved lead, plus
                  quotations linked to a resolved opportunity
    activity      ToDos and Events pointing at any resolved record above

Sales Orders and Invoices are deliberately absent: they carry a plain `customer`
column, so the money queries filter directly and need nothing from here.

Everything degrades to an empty list rather than raising, matching `api/crm.py`'s
house style — a missing doctype narrows the scope, it does not break the page.

Every query is parameterised: a customer name arrives from the client.
"""

import frappe

from upande_crm.api.crm import _has, _hascol

# Doctypes a scope can contain, in resolution order.
SCOPE_DOCTYPES = ("Lead", "Prospect", "Opportunity", "Quotation")


def _pluck(doctype, filters, or_filters=None):
    """Names matching `filters`, or [] if the doctype/column is unavailable."""
    if not _has(doctype):
        return []
    try:
        cols = set(frappe.db.get_table_columns(doctype))
    except Exception:
        return []
    for key in list(filters or {}):
        if key not in cols:
            return []
    try:
        return frappe.get_all(
            doctype, filters=filters or {}, or_filters=or_filters,
            pluck="name", limit=0, ignore_permissions=True,
        )
    except Exception:
        return []


def _customer_origin(customer):
    """What this Customer was converted from: (lead, prospect, opportunity)."""
    fields = [f for f in ("lead_name", "prospect_name", "opportunity_name")
              if _hascol("Customer", f)]
    if not fields or not _has("Customer"):
        return None, None, None
    try:
        row = frappe.db.get_value("Customer", customer, fields, as_dict=True) or {}
    except Exception:
        return None, None, None
    return row.get("lead_name"), row.get("prospect_name"), row.get("opportunity_name")


def _party_names(doctype, party_field, kind_field, kind, names):
    """Dynamic-link lookup: rows of `doctype` whose party is one of `names`."""
    if not names or not _hascol(doctype, party_field) or not _hascol(doctype, kind_field):
        return []
    return _pluck(doctype, {kind_field: kind, party_field: ["in", list(names)]})


def _prospects_for_leads(leads):
    """Prospects whose child `leads` table references any of `leads`."""
    if not leads or not _has("Prospect Lead"):
        return []
    try:
        return list({
            r.parent for r in frappe.get_all(
                "Prospect Lead", filters={"lead": ["in", list(leads)]},
                fields=["parent"], limit=0, ignore_permissions=True,
            ) if r.parent
        })
    except Exception:
        return []


def customer_scope(customer):
    """{doctype: [names]} for everything belonging to `customer`.

    The Customer itself is included under "Customer" so callers can treat the
    scope uniformly when matching activity references.
    """
    scope = {"Customer": [], "Lead": [], "Prospect": [],
             "Opportunity": [], "Quotation": []}
    if not customer:
        return scope
    scope["Customer"] = [customer]

    origin_lead, origin_prospect, origin_opp = _customer_origin(customer)

    # --- leads: the direct link, plus whatever this customer was converted from
    leads = set(_pluck("Lead", {"customer": customer}))
    if origin_lead:
        leads.add(origin_lead)
    scope["Lead"] = sorted(leads)

    # --- prospects: the origin, plus any prospect holding one of those leads
    prospects = set(_prospects_for_leads(leads))
    if origin_prospect:
        prospects.add(origin_prospect)
    scope["Prospect"] = sorted(prospects)

    # --- opportunities: against the customer, the origin, or a resolved lead/prospect
    opps = set(_party_names("Opportunity", "party_name", "opportunity_from", "Customer", [customer]))
    if origin_opp:
        opps.add(origin_opp)
    opps.update(_party_names("Opportunity", "party_name", "opportunity_from", "Lead", leads))
    opps.update(_party_names("Opportunity", "party_name", "opportunity_from", "Prospect", prospects))
    scope["Opportunity"] = sorted(opps)

    # --- quotations: against the customer, a resolved lead, or a resolved opportunity
    quotes = set(_party_names("Quotation", "party_name", "quotation_to", "Customer", [customer]))
    quotes.update(_party_names("Quotation", "party_name", "quotation_to", "Lead", leads))
    if opps and _hascol("Quotation", "opportunity"):
        quotes.update(_pluck("Quotation", {"opportunity": ["in", sorted(opps)]}))
    scope["Quotation"] = sorted(quotes)

    return scope


def scope_pairs(scope):
    """[(doctype, name)] for every record in a scope.

    The shape `ToDo.reference_type`/`reference_name` and `Event Participants`
    need to match against.
    """
    return [(dt, name) for dt in ("Customer",) + SCOPE_DOCTYPES for name in scope.get(dt) or []]


def todo_names(scope):
    """ToDos referencing anything in the scope."""
    if not _has("ToDo") or not _hascol("ToDo", "reference_type"):
        return []
    # or_filters cannot express (type AND name) pairs, so this is one query per
    # doctype rather than a single OR over tuples. At most five.
    names = set()
    for doctype in ("Customer",) + SCOPE_DOCTYPES:
        refs = scope.get(doctype) or []
        if not refs:
            continue
        names.update(_pluck("ToDo", {"reference_type": doctype,
                                     "reference_name": ["in", refs]}))
    return sorted(names)


def event_names(scope):
    """Events linked to the scope, via participants or the Dynamic Link table."""
    names = set()
    pairs = scope_pairs(scope)
    if not pairs:
        return []

    if _has("Event Participants"):
        for doctype in ("Customer",) + SCOPE_DOCTYPES:
            refs = scope.get(doctype) or []
            if not refs:
                continue
            try:
                names.update(
                    r.parent for r in frappe.get_all(
                        "Event Participants",
                        filters={"reference_doctype": doctype,
                                 "reference_docname": ["in", refs]},
                        fields=["parent"], limit=0, ignore_permissions=True,
                    ) if r.parent
                )
            except Exception:
                pass

    # Events also carry a generic Dynamic Link child table.
    if _has("Dynamic Link"):
        for doctype in ("Customer",) + SCOPE_DOCTYPES:
            refs = scope.get(doctype) or []
            if not refs:
                continue
            try:
                names.update(
                    r.parent for r in frappe.get_all(
                        "Dynamic Link",
                        filters={"parenttype": "Event", "link_doctype": doctype,
                                 "link_name": ["in", refs]},
                        fields=["parent"], limit=0, ignore_permissions=True,
                    ) if r.parent
                )
            except Exception:
                pass

    return sorted(names)


def in_scope(scope, doctype):
    """A filters-dict fragment restricting `doctype` to the scope.

    Returns `{"name": ["in", [...]]}`, or a filter that matches nothing when the
    scope is empty — the honest answer for "this customer's leads" when there are
    none. Returning `{}` instead would silently widen back to every record, which
    is the bug this module exists to fix.
    """
    names = scope.get(doctype)
    if names is None:
        return {}
    return {"name": ["in", names]} if names else {"name": ["in", [""]]}


def scope_sql(scope, doctype, column="name"):
    """A SQL fragment for the same restriction, for the raw-SQL readers.

    Names are quoted through frappe.db.escape rather than interpolated.
    """
    names = scope.get(doctype)
    if names is None:
        return ""
    if not names:
        return "1=0"
    quoted = ", ".join(frappe.db.escape(n) for n in names)
    return f"`{column}` in ({quoted})"
