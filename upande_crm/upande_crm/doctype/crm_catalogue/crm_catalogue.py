"""A price catalogue shared with buyers by link.

The controller owns what the buyer's page and every submission rely on: an
unguessable public token, currencies that exist, prices only in those
currencies, and whether the offer is open today. Line prices live in a JSON
map per line ({"USD": {"price": .., "tier": ..}}) so a catalogue can carry any
number of currencies, and a currency with no price stays absent rather than
reading as 0.
"""

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate


class CRMCatalogue(Document):
    def before_insert(self):
        self.public_token = frappe.generate_hash(length=24)
        self.views = 0

    def validate(self):
        self._validate_currencies()
        self._validate_dates()
        self._validate_prices()
        self._follow_template()

    def _follow_template(self):
        """Keep products, badges and specs in step with the lines and the
        template: one product row per item in the lines (values kept), badges
        only from the template's list, and each spec on the record its display
        kind belongs to — Column specs on lines, Badge/Subtitle on products."""
        from upande_crm.catalogue_templates import DEFAULT_TEMPLATE, TEMPLATE

        if not self.template and frappe.db.exists(TEMPLATE, DEFAULT_TEMPLATE):
            self.template = DEFAULT_TEMPLATE
        tpl = frappe.get_cached_doc(TEMPLATE, self.template) if self.template else None
        line_keys = {s.key for s in tpl.spec_columns if s.display == "Column"} if tpl else set()
        product_keys = {s.key for s in tpl.spec_columns if s.display != "Column"} if tpl else set()
        badges = {b.label for b in tpl.badges} if tpl else set()

        for line in self.lines or []:
            specs = _json(line.get("specs"))
            specs = {k: v for k, v in specs.items() if k in line_keys and v not in (None, "")}
            line.specs = json.dumps(specs) if specs else None

        items = list(dict.fromkeys(l.item for l in self.lines or [] if l.item))
        kept = {p.item: p for p in self.products or [] if p.item in items}
        rows = []
        for item in items:
            row = kept.get(item) or frappe._dict(item=item)
            picked = [b.strip() for b in (row.get("badges") or "").split("\n") if b.strip() in badges]
            specs = {k: v for k, v in _json(row.get("specs")).items() if k in product_keys and v not in (None, "")}
            rows.append({"item": item, "note": row.get("note"), "badges": "\n".join(picked) or None,
                         "specs": json.dumps(specs) if specs else None, "name": row.get("name")})
        self.set("products", [])
        for r in rows:
            self.append("products", {k: v for k, v in r.items() if v is not None})

    def currency_list(self):
        return [c.strip().upper() for c in (self.currencies or "").split(",") if c.strip()]

    def _validate_currencies(self):
        currencies = list(dict.fromkeys(self.currency_list()))
        if not currencies:
            frappe.throw(_("Give the catalogue at least one currency."))
        unknown = [c for c in currencies if not frappe.db.exists("Currency", c)]
        if unknown:
            frappe.throw(_("Unknown currency: {0}").format(", ".join(unknown)))
        self.currencies = ", ".join(currencies)

    def _validate_dates(self):
        if self.valid_from and self.valid_to and getdate(self.valid_to) < getdate(self.valid_from):
            frappe.throw(_("Valid To is before Valid From."))

    def _validate_prices(self):
        allowed = set(self.currency_list())
        for line in self.lines or []:
            # Shown to buyers as a link: only web addresses, never javascript: or data:.
            if line.info_url and not line.info_url.strip().lower().startswith(("http://", "https://")):
                line.info_url = None
            prices = _prices(line)
            clean = {}
            for cur, p in prices.items():
                cur = (cur or "").strip().upper()
                if cur not in allowed:
                    frappe.throw(_("Row {0}: {1} is not one of this catalogue's currencies ({2}).").format(
                        line.idx, cur, self.currencies))
                p = p or {}
                entry = {k: flt(p[k]) for k in ("price", "tier") if p.get(k) not in (None, "")}
                if any(v < 0 for v in entry.values()):
                    frappe.throw(_("Row {0}: prices cannot be negative.").format(line.idx))
                if entry:
                    clean[cur] = entry
            line.prices = json.dumps(clean) if clean else None

    def price_for(self, line, currency):
        """(price, tier) for `line` in `currency`; None where there is no price."""
        p = _prices(line).get((currency or "").upper()) or {}
        return (p.get("price"), p.get("tier"))

    def is_open(self, today=None):
        if self.status != "Live":
            return False
        today = getdate(today or nowdate())
        if self.valid_from and today < getdate(self.valid_from):
            return False
        if self.valid_to and today > getdate(self.valid_to):
            return False
        return True


def _json(raw):
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        val = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return val if isinstance(val, dict) else {}


def _prices(line):
    raw = line.get("prices")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        val = json.loads(raw)
    except (TypeError, ValueError):
        frappe.throw(_("Row {0}: prices are not valid JSON.").format(line.idx))
    return val if isinstance(val, dict) else {}
