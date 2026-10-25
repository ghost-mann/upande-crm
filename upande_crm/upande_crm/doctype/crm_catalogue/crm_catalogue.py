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
