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
        """Keep one product row per item in the lines (values kept), default the
        template, and keep mixes pointing at this catalogue's own lines.

        Badges and specs the template does not (or no longer) list are kept in
        storage: a renamed badge, a spec moved between Column and Badge, or the
        wrong template picked and saved must not delete anything. The page shows
        only what the template defines (api/catalogue_display.py).
        """
        from upande_crm.catalogue_templates import DEFAULT_TEMPLATE, TEMPLATE

        if not self.template and frappe.db.exists(TEMPLATE, DEFAULT_TEMPLATE):
            self.template = DEFAULT_TEMPLATE
        for line in self.lines or []:
            specs = {k: v for k, v in _json(line.get("specs")).items() if v not in (None, "")}
            line.specs = json.dumps(specs) if specs else None

        items = list(dict.fromkeys(l.item for l in self.lines or [] if l.item))
        kept = {p.item: p for p in self.products or [] if p.item in items}
        # Reuse the row objects, not copies: a copy of a row added in this save
        # carries its fresh name without the new-row flag, so Frappe updates a
        # row that is not in the table yet and the row is silently lost.
        rows = []
        for item in items:
            row = kept.get(item)
            if row is None:
                rows.append({"item": item})
                continue
            specs = {k: v for k, v in _json(row.get("specs")).items() if v not in (None, "")}
            row.image = row.get("image") or None
            row.badges = row.get("badges") or None
            row.specs = json.dumps(specs) if specs else None
            rows.append(row)
        self.set("products", rows)
        self._remap_mixes()

    def _remap_mixes(self):
        """A mix stores line names. Duplicating a catalogue or re-importing its
        sheet gives every line a new name, so a reference that is no longer one
        of this catalogue's lines is matched again by item, grade and box type
        (from the reference itself, or the old line's row) — the same rule a
        buyer's submission uses."""
        for line in self.lines or []:
            if not line.name:
                line.name = frappe.generate_hash(length=10)
        by_name = {l.name: l for l in self.lines or []}
        by_key = {(l.item, l.grade or "", l.box_type or ""): l for l in self.lines or []}
        for mix in self.get("mixes") or []:
            out = []
            for it in _json_list(mix.get("items")):
                line = by_name.get(it.get("line"))
                if not line:
                    key = (it.get("item"), it.get("grade") or "", it.get("box_type") or "")
                    if not key[0] and it.get("line"):
                        old = frappe.db.get_value("CRM Catalogue Line", it["line"], ["item", "grade", "box_type"],
                                                  as_dict=True) or {}
                        key = (old.get("item"), old.get("grade") or "", old.get("box_type") or "")
                    line = by_key.get(key)
                if line:
                    out.append({"line": line.name, "boxes": max(flt(it.get("boxes")) or 1, 1), "item": line.item,
                                "grade": line.grade, "box_type": line.box_type})
            mix.items = json.dumps(out)

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


def _json_list(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    try:
        val = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [x for x in val if isinstance(x, dict)] if isinstance(val, list) else []


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
