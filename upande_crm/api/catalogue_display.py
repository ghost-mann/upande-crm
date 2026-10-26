"""The magazine display model: a catalogue and its template, turned into
exactly what the buyer's page renders.

See docs/superpowers/specs/2026-10-26-crm-catalogue-magazine-design.md.
Everything here is data — the page escapes every string it shows — and the
template's values are resolved once, server-side, so the guest page never
reads a template and a half-filled template still renders with sensible
wording.

* Groups follow the template: colour groups (by the line's colour word, or an
  override), the Item's Item Group, or the line's grade. A product whose
  lines fall in different groups appears in each, with only that group's
  lines (user's decision).
* Badges, the note and Badge/Subtitle specs belong to the product and repeat
  on every copy of its card; Column specs belong to the line.
* `estimate` is the bar's figure, split by frequency; catalogue.js carries a
  port of it that must stay in step.
"""

import json
import re

import frappe
from frappe.utils import cint, flt, strip_html

from upande_crm.catalogue_templates import DEFAULT_TEMPLATE, FONT_PAIRS, STARTERS

FONT_CSS = "/assets/upande_crm/catalogue/fonts/{0}/fonts.css"
SECTIONS = ("cover", "letter", "tabs", "mixes", "badges", "notes", "estimate", "codes", "weight", "more_info")
_DEFAULTS = next(s for s in STARTERS if s["template_name"] == DEFAULT_TEMPLATE)


def _json(raw, empty):
    if not raw:
        return empty
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return empty


def _value(template, field):
    """The template's value, else the flowers almanac's — a blank field never
    leaves a hole on a live page."""
    v = template.get(field)
    return v if v not in (None, "") else _DEFAULTS.get(field)


def _keywords(text):
    return [k.strip().lower() for k in (text or "").split(",") if k.strip()]


def resolve_colour_group(line, template):
    if line.get("colour_group"):
        return line.colour_group
    words = set(re.findall(r"[a-z]+", (line.get("color") or "").lower()))
    for group in template.colour_groups or []:
        for kw in _keywords(group.keywords):
            if all(w in words for w in kw.split()):
                return group.label
    return template.fallback_group_label or "Mixed"


def group_key(line, item_group, template):
    if template.group_by == "Item Group":
        return item_group or template.fallback_group_label or "Other"
    if template.group_by == "Grade":
        return line.grade or template.fallback_group_label or "Other"
    return resolve_colour_group(line, template)


def template_text(template, tier_qty=None):
    unit, pack = _value(template, "unit_label"), _value(template, "pack_label")
    packs = template.get("pack_label_plural") or (_DEFAULTS["pack_label_plural"] if pack == _DEFAULTS["pack_label"]
                                                  else f"{pack}s")

    def fill(field):
        s = _value(template, field) or ""
        return (s.replace("{unit}", unit).replace("{packs}", packs).replace("{Packs}", packs[:1].upper() + packs[1:])
                .replace("{pack}", pack).replace("{n}", str(tier_qty or "")))

    return {
        "unit": unit, "pack": pack, "packs": packs, "grade": _value(template, "grade_label"),
        # A deliberately blank bunch label hides the bunch; it does not fall back.
        "bunch": template.get("bunch_label") or "", "weight": _value(template, "weight_label"),
        "price": fill("price_label"), "tier": fill("tier_label") if tier_qty else "", "qty": fill("qty_label"),
        "cta": fill("cta_label"), "thank_you": fill("thank_you_text"), "closed": fill("closed_text"),
        "issue": template.get("issue_title") or "", "headline": template.get("headline") or "",
        "dek": template.get("dek") or "", "letter_heading": _value(template, "letter_heading"),
        "letter_signoff": template.get("letter_signoff") or "",
    }


def _theme(doc, template, company_logo):
    pair = template.font_pair if template.font_pair in FONT_PAIRS else "almanac"
    fonts = {k: FONT_PAIRS[pair][k] for k in ("head", "text", "note")}
    fonts["css"] = FONT_CSS.format(pair)
    return {
        **{c: _value(template, c) for c in ("brand", "brand_ink", "paper", "ink", "accent", "accent_ink")},
        # A catalogue's own cover picture always wins, whatever the template's mode.
        "font_pair": pair, "fonts": fonts,
        "cover_mode": "Image" if doc.get("cover_image") else (template.cover_mode or "Collage"),
        "cover_image": doc.get("cover_image") or template.cover_image, "logo": template.logo or company_logo,
    }


def build_display(doc, template, preview=False):
    """Everything the buyer's page renders, as plain data."""
    tier_qty = cint(doc.volume_tier_qty) or None
    sections = {k: bool(cint(template.get(f"show_{k}"))) for k in SECTIONS}
    specs = [{"key": s.key, "label": s.label, "display": s.display} for s in template.spec_columns or []]
    spec_label = {s["key"]: s["label"] for s in specs}
    badge_style = {b.label: {"background": b.background or _value(template, "brand"),
                             "ink": b.ink or _value(template, "brand_ink")} for b in template.badges or []}
    accent = {"background": _value(template, "accent"), "ink": _value(template, "accent_ink")}
    swatches = {g.label: (g.swatch, g.swatch_ink) for g in template.colour_groups or []}
    order = [g.label for g in template.colour_groups or []]

    items = {i.name: i for i in frappe.get_all(
        "Item", filters={"name": ["in", list({l.item for l in doc.lines}) or [""]]},
        fields=["name", "item_name", "image", "description", "item_group"])}
    products = {p.item: p for p in doc.get("products") or []}
    company = frappe.db.get_value("Company", doc.company, ["company_name", "company_logo"], as_dict=True) or {}

    # Spec values may sit on the line or the product (a spec whose display kind
    # changed keeps its values where they were); product first, then any line.
    line_specs_by_item = {}
    for l in doc.lines:
        for k, v in _json(l.get("specs"), {}).items():
            if v not in (None, ""):
                line_specs_by_item.setdefault(l.item, {}).setdefault(k, v)

    def card(item):
        it = items.get(item) or frappe._dict(item_name=item)
        prod = products.get(item) or frappe._dict()
        pspecs = {**line_specs_by_item.get(item, {}), **_json(prod.get("specs"), {})}
        badges = []
        if sections["badges"]:
            badges = [{"label": b, **badge_style[b]} for b in (prod.get("badges") or "").split("\n")
                      if b in badge_style]
            badges += [{"label": f"{spec_label[s['key']]} {pspecs[s['key']]}", **accent}
                       for s in specs if s["display"] == "Badge" and pspecs.get(s["key"]) not in (None, "")]
        desc = strip_html(it.description or "").strip()
        note = (prod.get("note") or (desc if desc and desc != it.item_name else "")) if sections["notes"] else ""
        return {"item": item, "item_name": it.item_name or item, "image": it.image, "note": note, "badges": badges,
                "subtitle": [{"label": s["label"], "value": pspecs[s["key"]]} for s in specs
                             if s["display"] == "Subtitle" and pspecs.get(s["key"]) not in (None, "")],
                "lines": []}

    groups, line_group = {}, {}
    for line in doc.lines:
        it = items.get(line.item) or frappe._dict()
        key = group_key(line, it.get("item_group"), template)
        line_group[line.name] = key
        if key not in groups:
            sw = swatches.get(key, (None, None))
            groups[key] = {"key": key, "label": key, "swatch": sw[0], "swatch_ink": sw[1], "products": {}}
        cards = groups[key]["products"]
        if line.item not in cards:
            cards[line.item] = card(line.item)
        lspecs = {**_json((products.get(line.item) or {}).get("specs"), {}), **_json(line.get("specs"), {})}
        cards[line.item]["lines"].append({
            "line": line.name, "grade": line.grade, "box_type": line.box_type, "color": line.color,
            "pack_qty": line.pack_qty, "bunch": line.bunch if (template.get("bunch_label") or "") else None,
            "weight": line.weight if sections["weight"] else None,
            "vbn": line.vbn if sections["codes"] else None,
            "info_url": line.info_url if sections["more_info"] else None, "group": key,
            "specs": {s["key"]: lspecs[s["key"]] for s in specs
                      if s["display"] == "Column" and lspecs.get(s["key"]) not in (None, "")},
            "prices": {c: dict(zip(("price", "tier"), doc.price_for(line, c))) for c in doc.currency_list()},
        })
    ordered = sorted(groups.values(), key=lambda g: (order.index(g["key"]) if g["key"] in order else len(order)))
    out_groups = [{**g, "products": list(g["products"].values())} for g in ordered]

    mixes = []
    if sections["mixes"]:
        for m in doc.get("mixes") or []:
            picks = [p for p in _json(m.get("items"), []) if isinstance(p, dict) and p.get("line") in line_group]
            if not picks:
                continue
            colours = list(dict.fromkeys(swatches.get(line_group[p["line"]], (None,))[0] or _value(template, "accent")
                                         for p in picks))
            names = list(dict.fromkeys((items.get(l.item) or frappe._dict(item_name=l.item)).item_name
                                       for l in doc.lines if l.name in {p["line"] for p in picks}))
            mixes.append({"title": m.title, "colours": colours,
                          "summary": m.get("summary") or ", ".join(names),
                          "items": [{"line": p["line"], "boxes": flt(p.get("boxes")) or 1} for p in picks]})

    return {
        "title": doc.title, "company": company.get("company_name") or doc.company, "terms": doc.terms or "",
        "currencies": doc.currency_list(), "tier_qty": tier_qty, "open": doc.is_open() or preview,
        "valid_from": str(doc.valid_from) if doc.valid_from else None,
        "valid_to": str(doc.valid_to) if doc.valid_to else None, "preview": bool(preview),
        "theme": _theme(doc, template, company.get("company_logo")), "text": template_text(template, tier_qty),
        "sections": sections, "specs": specs,
        "frequencies": [{"label": f.label, "period_text": f.period_text or "", "recurring": cint(f.recurring)}
                        for f in template.frequencies or []],
        "groups": out_groups, "mixes": mixes,
    }


def estimate(lines, picks, currency, tier_qty, frequencies):
    """The bar's estimate, one amount per frequency in use, in template order.
    Per pick: boxes × pack qty × price, the tier price when the boxes exceed
    the tier threshold. Picks without a price or a pack qty are left out."""
    by_line = {l["line"]: l for l in lines}
    totals = {}
    for p in picks:
        line = by_line.get(p.get("line"))
        qty = flt(p.get("qty"))
        if not line or qty <= 0 or not line.get("pack_qty"):
            continue
        pr = (line.get("prices") or {}).get(currency) or {}
        rate = pr.get("tier") if tier_qty and qty > tier_qty and pr.get("tier") is not None else pr.get("price")
        if rate is None:
            continue
        totals[p.get("frequency")] = totals.get(p.get("frequency"), 0) + qty * flt(line["pack_qty"]) * flt(rate)
    out = []
    for f in frequencies:
        amount = round(totals.get(f["label"], 0), 2)
        if amount:
            out.append({"frequency": f["label"], "period_text": f.get("period_text") or "once", "amount": amount})
    return out
