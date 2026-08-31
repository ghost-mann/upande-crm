"""Moving a record to the next document in the pipeline.

Split out of `api/leads.py`, which had become the write module for capture *and*
conversion. That file keeps lead capture; this one owns every hop:

    Lead  -> Prospect | Opportunity | Quotation | Customer
    Prospect     -> Opportunity | Customer
    Opportunity  -> Quotation | Customer
    Quotation    -> Customer

Same contract as the module it came from, and it matters more here than anywhere
else in the app: **every failure must surface.** A quotation the salesperson
believes they raised and which was silently dropped is the worst outcome this
module can produce. Never add a bare `except` around a write.

## Delegate, don't reimplement

Every hop is an ERPNext mapper. This module owns the role gate, the permission
check, the field allowlist, the item lines, the duplicate guard and the UI
contract. The field mapping between doctypes is ERPNext's and stays ERPNext's.
`HOPS` below is the whole of the routing, and the mapper is resolved **from that
table only** — never from anything the client sends.

## Three things the mappers do not do

**They do not stop you making a second customer.** `lead.make_customer`,
`prospect.make_customer` and `opportunity.make_customer` have no existing-customer
check; ERPNext's own Lead form avoids a duplicate purely by hiding the button when
`has_customer()` is set. Exposing a button means owning that check, so
`_no_customer_yet` runs before every hop to Customer.

**They do not carry the data across.** ERPNext's customer mappers move a handful
of fields, two of the *required* ones are populated on this site under different
names, and `Customer.email_id`/`mobile_no` cannot be written at all — they are
fetched from the primary contact. See `api/carry_across.py`, which this module
calls for any hop whose target is a Customer.

**One of them is not a mapper.** `quotation._make_customer` is a resolver: it
returns the existing customer if the lead or prospect already has one, and
otherwise creates *and inserts* it. That hop is marked `inserts=True` and `_advance`
skips its own insert rather than pretending the shapes are the same.

## Quotations are drafts

Nothing here submits. A consequence worth stating rather than papering over:
`Lead.status` does not become "Quotation", because ERPNext only counts submitted
quotes (`Lead.has_quotation` filters `docstatus: 1`). Setting it by hand would make
the funnel count a quote nobody sent.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, getdate

from upande_crm.api import carry_across
from upande_crm.api.crm import _guard
from upande_crm.api.leads import _payload, _pick, _require

# Opportunity header fields a hop may set. `party_name`, `opportunity_from` and
# `company` come from the mapper and are not overridable.
OPPORTUNITY_FIELDS = {
    "opportunity_type",
    "sales_stage",
    "expected_closing",
    "probability",
    "opportunity_amount",
    "territory",
    "contact_email",
    "contact_mobile",
    "opportunity_owner",
}

# Quotation header fields. Deliberately short: company, currency, price list,
# conversion rate and taxes come from ERPNext's defaults via the mapper's own
# `set_missing_values`, and re-asking for them here would be rebuilding the
# Quotation form inside the CRM.
QUOTATION_FIELDS = {
    "valid_till",
    "order_type",
    "tc_name",
}

# Customer header fields. Everything else arrives through `carry_across`.
CUSTOMER_FIELDS = {
    "customer_group",
    "territory",
    "customer_type",
    # Mandatory on this site, and a Prospect carries no answer for either. The
    # dialog can supply them; `carry_across.fill_required` falls back to the
    # site's own settings when it does not.
    "default_currency",
    "default_price_list",
}

DATE_FIELDS = {"expected_closing", "valid_till"}

# What an item line may carry. Rate is optional; qty is not.
ITEM_FIELDS = ("item_code", "qty", "rate", "uom", "description")

MAX_ITEMS = 50


def _items(payload):
    """Validated item lines. Returns [] when none were supplied.

    An unknown `item_code` is rejected rather than dropped: silently discarding a
    variety the salesperson typed would make the demand card lie about what was
    asked for, which is the one thing it exists to report.
    """
    raw = payload.get("items") or []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            frappe.throw(_("Malformed item lines"))
    if not isinstance(raw, list):
        frappe.throw(_("Malformed item lines"))
    if len(raw) > MAX_ITEMS:
        frappe.throw(_("At most {0} item lines").format(MAX_ITEMS))

    out = []
    for i, row in enumerate(raw, start=1):
        if not isinstance(row, dict):
            frappe.throw(_("Malformed item line {0}").format(i))
        code = (row.get("item_code") or "").strip()
        if not code:
            frappe.throw(_("Item line {0} has no variety").format(i))
        if not frappe.db.exists("Item", code):
            frappe.throw(_("Item line {0}: {1} is not an item").format(i, code))
        qty = flt(row.get("qty"))
        if qty <= 0:
            frappe.throw(_("Item line {0}: quantity must be more than zero").format(i))
        line = {"item_code": code, "qty": qty}
        if row.get("rate") not in (None, ""):
            line["rate"] = flt(row.get("rate"))
        for extra in ("uom", "description"):
            if row.get(extra):
                line[extra] = row[extra]
        out.append(line)
    return out


# ---------------------------------------------------------------- preconditions
def _existing_customer(source_doctype, source):
    """The customer this record already became, if any."""
    field = {"Lead": "lead_name", "Prospect": "prospect_name",
             "Opportunity": "opportunity_name"}.get(source_doctype)
    if not field:
        return None
    try:
        return frappe.db.get_value("Customer", {field: source})
    except Exception:
        return None


def _no_customer_yet(source_doctype, source, payload):
    existing = _existing_customer(source_doctype, source)
    if existing:
        frappe.throw(
            _("{0} {1} is already customer {2}").format(_(source_doctype), source, existing)
        )


# ---------------------------------------------------------------- route table
class Hop:
    """One (source -> target) route.

    `mapper` is a dotted path resolved through `frappe.get_attr` at call time and
    only ever read from `HOPS`, so nothing a client sends can choose it.
    """

    def __init__(self, mapper, header=None, items=False, items_required=False,
                 precondition=None, inserts=False):
        self.mapper = mapper
        self.header = header or set()
        self.items = items
        self.items_required = items_required
        self.precondition = precondition
        self.inserts = inserts


HOPS = {
    ("Lead", "Opportunity"): Hop(
        "erpnext.crm.doctype.lead.lead.make_opportunity",
        header=OPPORTUNITY_FIELDS, items=True),
    ("Lead", "Quotation"): Hop(
        "erpnext.crm.doctype.lead.lead.make_quotation",
        header=QUOTATION_FIELDS, items=True, items_required=True),
    ("Lead", "Customer"): Hop(
        "erpnext.crm.doctype.lead.lead.make_customer",
        header=CUSTOMER_FIELDS, precondition=_no_customer_yet),
    ("Prospect", "Opportunity"): Hop(
        "erpnext.crm.doctype.prospect.prospect.make_opportunity",
        header=OPPORTUNITY_FIELDS, items=True),
    ("Prospect", "Customer"): Hop(
        "erpnext.crm.doctype.prospect.prospect.make_customer",
        header=CUSTOMER_FIELDS, precondition=_no_customer_yet),
    ("Opportunity", "Quotation"): Hop(
        "erpnext.crm.doctype.opportunity.opportunity.make_quotation",
        header=QUOTATION_FIELDS, items=True),
    ("Opportunity", "Customer"): Hop(
        "erpnext.crm.doctype.opportunity.opportunity.make_customer",
        header=CUSTOMER_FIELDS, precondition=_no_customer_yet),
    # A resolver, not a mapper. ERPNext's own
    # `quotation._make_customer` would insert the customer itself, which means
    # bypassing everything in `api/carry_across.py` — measured, that fails
    # outright here, because this site's mandatory Customer fields have no answer
    # unless the carry-across supplies one. So the quotation hop resolves the
    # party and re-enters `_advance` through the Lead or Prospect route instead.
    ("Quotation", "Customer"): Hop(
        "upande_crm.api.advance._resolve_quotation_customer",
        inserts=True),
}


# ---------------------------------------------------------------- the one path
def _title(doc):
    for field in ("customer_name", "party_name", "lead_name", "company_name", "title"):
        try:
            v = doc.get(field)
        except Exception:
            continue
        if v:
            return v
    return doc.name


def _envelope(doc, existing=False, extra=None):
    """The one shape every hop returns, so the UI has a single thing to render."""
    out = {
        "doctype": doc.doctype,
        "name": doc.name,
        "title": _title(doc),
        "items": len(doc.get("items") or []) if doc.meta.get_field("items") else 0,
        "amount": flt(doc.get("grand_total") or doc.get("opportunity_amount") or 0),
        "currency": doc.get("currency") or doc.get("default_currency") or "",
        "existing": bool(existing),
    }
    if extra:
        out.update(extra)
    return out


def _advance(source_doctype, source, target_doctype, payload=None, what="payload"):
    """Guard, permit, map, fill, insert. In that order, insert last.

    Insert being the last step is what makes a failed hop harmless: a bad item
    line throws while the target is still an in-memory document, and the source
    record is untouched.
    """
    _guard()
    source = (source or "").strip()
    if not source or not frappe.db.exists(source_doctype, source):
        frappe.throw(_("{0} not found").format(_(source_doctype)))

    hop = HOPS.get((source_doctype, target_doctype))
    if not hop:
        frappe.throw(_("Cannot turn a {0} into a {1}").format(_(source_doctype), _(target_doctype)))

    data = _payload(payload, what)

    _require(source_doctype, "read", source)
    _require(target_doctype, "create")
    if hop.precondition:
        hop.precondition(source_doctype, source, data)

    mapper = frappe.get_attr(hop.mapper)

    # The resolver hop owns its own document lifecycle and returns a finished
    # envelope; there is nothing here to fill in.
    if hop.inserts:
        return mapper(source)

    doc = mapper(source)

    header = _pick(data, hop.header)
    for field in DATE_FIELDS & set(header):
        if header.get(field):
            try:
                header[field] = str(getdate(header[field]))
            except Exception:
                frappe.throw(_("{0} is not a date").format(field.replace("_", " ").title()))
    doc.update(header)

    if hop.items:
        lines = _items(data)
        # Quotation.items is mandatory: say so in the dialog's language rather
        # than letting a raw MandatoryError through.
        if hop.items_required and not lines and not doc.get("items"):
            frappe.throw(_("A quotation needs at least one variety"))
        for line in lines:
            doc.append("items", line)

    source_doc = None
    if target_doctype == "Customer":
        source_doc = frappe.get_doc(source_doctype, source)
        carry_across.apply_to_customer(source_doc, doc)
        carry_across.apply_notes(source_doc, doc)
        # Last, so the source's own answer always wins over a site default.
        carry_across.fill_required(doc)

    doc.insert()

    extra = None
    if target_doctype == "Customer" and source_doc is not None:
        # Same transaction as the insert: a customer whose email was lost is the
        # outcome this exists to prevent, so a failure here fails the hop.
        extra = carry_across.carry(source_doc, doc)

    return _envelope(doc, extra=extra)


def _resolve_quotation_customer(quotation):
    """The Customer behind a Quotation, created through the normal route if absent.

    ERPNext's `quotation._make_customer` does this too, but it inserts the customer
    itself — which skips `api/carry_across.py` entirely, and measured on this site
    that means the insert fails on mandatory fields nothing has filled. Resolving
    the party and re-entering `_advance` gives a quotation-raised customer exactly
    the same contact, address and field carry-across as any other.
    """
    row = frappe.db.get_value(
        "Quotation", quotation, ["quotation_to", "party_name"], as_dict=True)
    if not row or not row.party_name:
        frappe.throw(_("Quotation {0} is not addressed to anyone").format(quotation))

    # Already a customer: say so rather than present a name as new.
    if row.quotation_to == "Customer":
        return _envelope(frappe.get_doc("Customer", row.party_name), existing=True)

    existing = _existing_customer(row.quotation_to, row.party_name)
    if existing:
        return _envelope(frappe.get_doc("Customer", existing), existing=True)

    if (row.quotation_to, "Customer") not in HOPS:
        frappe.throw(_("A quotation addressed to a {0} cannot become a customer").format(
            _(row.quotation_to)))

    return _advance(row.quotation_to, row.party_name, "Customer")


# ---------------------------------------------------------------- lead -> prospect
@frappe.whitelist()
def crm_lead_to_prospect(lead, prospect=None, company_name=None):
    """Attach a Lead to a Prospect, creating the Prospect when none is named.

    Not a `HOPS` route: `create_prospect` is a controller method that appends to a
    child table rather than a mapper that returns a document, and the
    already-on-this-prospect case is specific to it.
    """
    _guard()
    lead = (lead or "").strip()
    if not lead or not frappe.db.exists("Lead", lead):
        frappe.throw(_("Lead not found"))
    _require("Lead", "read", lead)

    prospect = (prospect or "").strip()
    if prospect:
        if not frappe.db.exists("Prospect", prospect):
            frappe.throw(_("Prospect not found"))
        _require("Prospect", "write", prospect)
        if frappe.db.exists("Prospect Lead", {"parent": prospect, "lead": lead}):
            frappe.throw(_("That lead is already on this prospect"))
        from erpnext.crm.doctype.lead.lead import add_lead_to_prospect

        add_lead_to_prospect(lead, prospect)
        return {"prospect": prospect, "created": False}

    _require("Prospect", "create")
    doc = frappe.get_doc("Lead", lead)
    title = (company_name or doc.company_name or doc.lead_name or "").strip()
    if not title:
        frappe.throw(_("A prospect needs a company name"))
    # Prospect is named by `company_name`, so a clash is a real collision the user
    # has to resolve — offer the existing record rather than a naming error.
    if frappe.db.exists("Prospect", title):
        frappe.throw(_("Prospect {0} already exists — add the lead to it instead").format(title))

    # The controller's own method: it carries employees, industry, territory,
    # owner and notes across, and appends the lead to the child table.
    doc.create_prospect(title)
    return {"prospect": title, "created": True}


# ---------------------------------------------------------------- the hops
@frappe.whitelist()
def crm_lead_to_opportunity(lead, opportunity=None):
    """Convert a Lead into an Opportunity, optionally with the flowers asked for."""
    return _advance("Lead", lead, "Opportunity", opportunity, "opportunity")


@frappe.whitelist()
def crm_prospect_to_opportunity(prospect, opportunity=None):
    """Convert a Prospect into an Opportunity, optionally with item lines."""
    return _advance("Prospect", prospect, "Opportunity", opportunity, "opportunity")


@frappe.whitelist()
def crm_lead_to_quotation(lead, quotation=None, with_opportunity=0):
    """Quote a Lead — before it is a customer, which ERPNext supports natively.

    `with_opportunity` runs the chain instead: Lead -> Opportunity carrying the
    same varieties, then Opportunity -> Quotation. Two `_advance` calls rather
    than a tenth route, so the quote comes back linked to the opportunity and the
    Opportunity->Quotation linkage that `api/pipeline.py` measures starts filling.
    """
    if not frappe.utils.cint(with_opportunity):
        return _advance("Lead", lead, "Quotation", quotation, "quotation")

    data = _payload(quotation, "quotation")
    opp = _advance("Lead", lead, "Opportunity", data, "quotation")
    # The mapper carries the opportunity's items onto the quote, so they are not
    # sent a second time.
    quote = _advance("Opportunity", opp["name"], "Quotation",
                     {k: v for k, v in data.items() if k != "items"}, "quotation")
    quote["opportunity"] = opp["name"]
    return quote


@frappe.whitelist()
def crm_opportunity_to_quotation(opportunity, quotation=None):
    """Raise a Quotation from an Opportunity, carrying its items across."""
    return _advance("Opportunity", opportunity, "Quotation", quotation, "quotation")


@frappe.whitelist()
def crm_lead_to_customer(lead, customer=None):
    """Turn a Lead into a Customer, carrying its contact details with it."""
    return _advance("Lead", lead, "Customer", customer, "customer")


@frappe.whitelist()
def crm_prospect_to_customer(prospect, customer=None):
    """Turn a Prospect into a Customer."""
    return _advance("Prospect", prospect, "Customer", customer, "customer")


@frappe.whitelist()
def crm_opportunity_to_customer(opportunity, customer=None):
    """Turn an Opportunity into a Customer."""
    return _advance("Opportunity", opportunity, "Customer", customer, "customer")


@frappe.whitelist()
def crm_quotation_to_customer(quotation):
    """Resolve the Customer behind a Quotation, creating it if there is none.

    Returns `existing: true` when the lead or prospect had already become a
    customer, so the dialog can say so rather than present a name as new.
    """
    return _advance("Quotation", quotation, "Customer")


# ---------------------------------------------------------------- preview
@frappe.whitelist()
def crm_advance_preview(source_doctype, source, target_doctype="Customer"):
    """What a hop to Customer would carry across, without writing anything.

    A read, so it degrades: a preview that cannot be built shows nothing rather
    than blocking the dialog it sits in.
    """
    _guard()
    source = (source or "").strip()
    if (source_doctype, target_doctype) not in HOPS:
        return {}
    if not source or not frappe.db.exists(source_doctype, source):
        return {}
    if not frappe.has_permission(source_doctype, "read", doc=source):
        return {}
    if target_doctype != "Customer" or source_doctype == "Quotation":
        return {}

    try:
        doc = frappe.get_doc(source_doctype, source)
    except Exception:
        return {}

    out = carry_across.preview(doc)
    out["already_customer"] = _existing_customer(source_doctype, source) or ""
    return out


@frappe.whitelist()
def crm_advance_routes():
    """Which hops this user may take, per source doctype — the dialog's mode strip.

    A read: it degrades to an empty map rather than an error on top of a dialog.
    """
    _guard()
    routes = {}
    for (src, target), _hop in HOPS.items():
        try:
            allowed = bool(frappe.has_permission(target, "create"))
        except Exception:
            allowed = False
        if allowed:
            routes.setdefault(src, []).append(target)
    try:
        if frappe.has_permission("Prospect", "create"):
            routes.setdefault("Lead", []).append("Prospect")
    except Exception:
        pass
    for src in routes:
        # A stable order, so the mode strip does not reshuffle between loads.
        order = ["Opportunity", "Quotation", "Prospect", "Customer"]
        routes[src] = sorted(set(routes[src]), key=lambda t: order.index(t) if t in order else 99)
    return routes
