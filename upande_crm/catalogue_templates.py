"""Magazine templates for catalogues: the bundled font pairs, the shipped
starter templates, and the setup that keeps them present.

See docs/superpowers/specs/2026-10-26-crm-catalogue-magazine-design.md.

Starters are created here on after_install and after_migrate rather than
from patches.txt: install-app does not run patches, and before_migrate runs
before the template doctype exists. A starter is only ever created, never
overwritten — a site that has edited one keeps its edits.
"""

import frappe

TEMPLATE = "CRM Catalogue Template"
DEFAULT_TEMPLATE = "Flowers almanac"

# Bundled under public/catalogue/fonts/<key>/ (SIL OFL, Latin subset). `files`
# is what the font fetch downloads; the page links fonts/<key>/fonts.css.
FONT_PAIRS = {
    "almanac": {"label": "Almanac — Archivo / Archivo Narrow / Newsreader",
                "head": "Archivo", "text": "Archivo Narrow", "note": "Newsreader"},
    "orchard": {"label": "Orchard — Fraunces / Instrument Sans / Spectral",
                "head": "Fraunces", "text": "Instrument Sans", "note": "Spectral"},
    "roastery": {"label": "Roastery — Spectral / Instrument Sans",
                 "head": "Spectral", "text": "Instrument Sans", "note": "Spectral"},
    "fieldguide": {"label": "Field guide — Cormorant Garamond / IBM Plex Serif",
                   "head": "Cormorant Garamond", "text": "IBM Plex Serif", "note": "Cormorant Garamond"},
    "market": {"label": "Market sheet — Space Grotesk / Inter Tight",
               "head": "Space Grotesk", "text": "Inter Tight", "note": "Inter Tight"},
    "gazette": {"label": "Gazette — Bodoni Moda / Work Sans",
                "head": "Bodoni Moda", "text": "Work Sans", "note": "Bodoni Moda"},
}

_FLOWER_GROUPS = [
    ("Whites", "#E8EEF3", "#10233A", "white, cream, ivory, green-white"),
    ("Pinks", "#E8A0BF", "#3F0D24", "pink, rose, blush, salmon, fuchsia"),
    ("Purples", "#6B3F96", "#FFFFFF", "purple, lilac, lavender, violet, mauve"),
    ("Blues", "#4F6FB3", "#FFFFFF", "blue"),
    ("Yellows", "#E3AE3D", "#3D2A00", "yellow, gold, lemon"),
    ("Greens", "#8FA86A", "#18240A", "green, lime"),
    ("Oranges & reds", "#D9643A", "#FFFFFF", "orange, red, peach, coral, burgundy, apricot"),
]

STARTERS = [
    {
        "template_name": "Flowers almanac", "preset": "Almanac", "group_by": "Colour", "font_pair": "almanac",
        "brand": "#1E4D3A", "brand_ink": "#F3F6EF", "paper": "#F6F6F1", "ink": "#18181A",
        "accent": "#F2E3B6", "accent_ink": "#6A4A06", "cover_mode": "Collage",
        "issue_title": "The colour almanac", "headline": "Colour, by the box.",
        "dek": "Summer flowers grown on the equator, cut to order and flown from Nairobi.",
        "letter_heading": "From the farm", "letter_signoff": "The sales team",
        "unit_label": "stem", "pack_label": "box", "pack_label_plural": "boxes", "grade_label": "Length",
        "bunch_label": "Bunch", "weight_label": "kg", "price_label": "Per {unit}",
        "tier_label": "Above {n} {packs}", "qty_label": "{Packs}", "cta_label": "Send my interest",
        "thank_you_text": "Thank you — we have your interest and will be in touch soon.",
        "closed_text": "This offer has closed, so it can no longer take interest. You can still look through it.",
        "fallback_group_label": "Mixed",
        "frequencies": [{"label": "One-off", "period_text": "", "recurring": 0},
                        {"label": "Weekly", "period_text": "a week", "recurring": 1}],
        "colour_groups": [{"label": l, "swatch": s, "swatch_ink": i, "keywords": k} for l, s, i, k in _FLOWER_GROUPS],
        "spec_columns": [],
        "badges": [{"label": "Bestseller", "background": "#1E4D3A", "ink": "#F3F6EF"},
                   {"label": "New this season", "background": "#F2E3B6", "ink": "#6A4A06"},
                   {"label": "Limited", "background": "#D9643A", "ink": "#FFFFFF"}],
        "show_estimate": 1, "show_codes": 0,
    },
    {
        "template_name": "Avocado export", "preset": "Almanac", "group_by": "Item Group", "font_pair": "orchard",
        "brand": "#2E4A23", "brand_ink": "#F4F1DF", "paper": "#F1F0E8", "ink": "#1E2A1B",
        "accent": "#C9A227", "accent_ink": "#2E2400", "cover_mode": "Collage",
        "issue_title": "Export catalogue", "headline": "The export season",
        "dek": "Class 1 fruit, packed on the farm and shipped from Mombasa.",
        "letter_heading": "From the orchard", "letter_signoff": "The export team",
        "unit_label": "carton", "pack_label": "carton", "pack_label_plural": "cartons", "grade_label": "Count",
        "bunch_label": "Fruits per carton", "weight_label": "kg", "price_label": "Per {unit}",
        "tier_label": "Above {n} {packs}", "qty_label": "{Packs}", "cta_label": "Request a quote",
        "thank_you_text": "Thank you — our export team will come back to you with a quote.",
        "closed_text": "This season's offer has closed. You can still look through it.",
        "fallback_group_label": "Other",
        "frequencies": [{"label": "Per shipment", "period_text": "per shipment", "recurring": 0},
                        {"label": "Monthly", "period_text": "a month", "recurring": 1}],
        "colour_groups": [],
        "spec_columns": [{"key": "dry_matter", "label": "Dry matter", "display": "Subtitle", "import_headers": "Dry matter, DM"},
                         {"key": "certification", "label": "Certification", "display": "Badge", "import_headers": "Certification"}],
        "badges": [{"label": "GlobalG.A.P.", "background": "#C9A227", "ink": "#2E2400"},
                   {"label": "Organic", "background": "#4F6B2E", "ink": "#F4F1DF"}],
        "show_estimate": 0, "show_codes": 0,
    },
    {
        "template_name": "Coffee lots", "preset": "Almanac", "group_by": "Grade", "font_pair": "roastery",
        "brand": "#3B2418", "brand_ink": "#F4E7DA", "paper": "#F4EFE9", "ink": "#2A1D15",
        "accent": "#B5532E", "accent_ink": "#FFFFFF", "cover_mode": "Collage",
        "issue_title": "Estate catalogue", "headline": "This year's lots",
        "dek": "Washed Arabica, grown, processed and graded on the estate.",
        "letter_heading": "From the estate", "letter_signoff": "The coffee team",
        "unit_label": "kg", "pack_label": "bag", "pack_label_plural": "bags", "grade_label": "Screen",
        "bunch_label": "", "weight_label": "kg", "price_label": "Per {unit}",
        "tier_label": "Above {n} {packs}", "qty_label": "{Packs}", "cta_label": "Send my interest",
        "thank_you_text": "Thank you — we will be in touch about these lots.",
        "closed_text": "These lots are no longer on offer. You can still look through them.",
        "fallback_group_label": "Other",
        "frequencies": [{"label": "One-off", "period_text": "", "recurring": 0}],
        "colour_groups": [],
        "spec_columns": [{"key": "cup_score", "label": "Cup score", "display": "Badge", "import_headers": "Cup score, Score"},
                         {"key": "process", "label": "Process", "display": "Column", "import_headers": "Process"},
                         {"key": "variety", "label": "Variety", "display": "Subtitle", "import_headers": "Variety"}],
        "badges": [{"label": "Microlot", "background": "#B5532E", "ink": "#FFFFFF"},
                   {"label": "Top lot", "background": "#3B2418", "ink": "#F4E7DA"}],
        "show_estimate": 1, "show_codes": 0,
    },
]


def ensure_starters():
    """Create any missing starter; returns the names created."""
    if not frappe.db.exists("DocType", TEMPLATE):
        return []
    made = []
    for spec in STARTERS:
        if frappe.db.exists(TEMPLATE, spec["template_name"]):
            continue
        doc = frappe.get_doc({"doctype": TEMPLATE, "is_standard": 1, **spec})
        doc.insert(ignore_permissions=True)
        made.append(doc.name)
    return made


def assign_default_template():
    """Give catalogues without a template the flowers almanac; returns how many."""
    if not (frappe.db.exists("DocType", TEMPLATE) and frappe.db.exists(TEMPLATE, DEFAULT_TEMPLATE)):
        return 0
    names = frappe.get_all("CRM Catalogue", filters={"template": ["in", ["", None]]}, pluck="name")
    for name in names:
        frappe.db.set_value("CRM Catalogue", name, "template", DEFAULT_TEMPLATE, update_modified=False)
    return len(names)


def after_migrate():
    ensure_starters()
    assign_default_template()
    frappe.db.commit()
