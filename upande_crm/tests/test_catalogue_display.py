"""Tests for the magazine display model (api/catalogue_display.py): how a
catalogue and its template become the groups, cards, wording, theme, mixes
and estimate the buyer's page renders."""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm import catalogue_templates as CT
from upande_crm.api import catalogue_display as D
from upande_crm.tests.test_catalogue_model import make_catalogue
from upande_crm.tests.test_catalogue_templates import copy_of

TEMPLATE = "CRM Catalogue Template"


def _items(n=2):
    return frappe.get_all("Item", filters={"disabled": 0}, pluck="name", limit=n)


def _image_or_none(url):
    return D._image_url(url)


def price(p, tier=None):
    out = {"price": p}
    if tier is not None:
        out["tier"] = tier
    return {"USD": out}


class DisplayCase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        CT.ensure_starters()
        frappe.db.commit()
        cls.flowers = frappe.get_doc(TEMPLATE, "Flowers almanac")

    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.db.rollback()

    def groups(self, doc, template=None):
        return D.build_display(doc, template or frappe.get_doc(TEMPLATE, doc.template))["groups"]


class TestColourGroups(DisplayCase):
    def test_colour_group_resolution(self):
        line = lambda **kw: frappe._dict({"color": "", "colour_group": None, **kw})  # noqa: E731
        self.assertEqual(D.resolve_colour_group(line(color="White"), self.flowers), "Whites")
        self.assertEqual(D.resolve_colour_group(line(color="Burgundy Red"), self.flowers), "Oranges & reds")
        self.assertEqual(D.resolve_colour_group(line(color="All"), self.flowers), "Mixed")
        self.assertEqual(D.resolve_colour_group(line(color=""), self.flowers), "Mixed")
        self.assertEqual(D.resolve_colour_group(line(color="White", colour_group="Pinks"), self.flowers), "Pinks")
        # whole words only: "Redwood" is not red
        self.assertEqual(D.resolve_colour_group(line(color="Redwood"), self.flowers), "Mixed")

    def test_product_repeats_across_groups(self):
        a, = _items(1)
        doc = make_catalogue(lines=[{"item": a, "grade": "60 cm", "color": "White", "prices": price(0.2)},
                                    {"item": a, "grade": "70 cm", "color": "Pink", "prices": price(0.3)}])
        groups = {g["label"]: g for g in self.groups(doc)}
        self.assertEqual([p["item"] for p in groups["Whites"]["products"]], [a])
        self.assertEqual([p["item"] for p in groups["Pinks"]["products"]], [a])
        self.assertEqual([l["grade"] for l in groups["Whites"]["products"][0]["lines"]], ["60 cm"])
        self.assertEqual([l["grade"] for l in groups["Pinks"]["products"][0]["lines"]], ["70 cm"])

    def test_group_order_follows_template(self):
        a, b = _items(2)
        doc = make_catalogue(lines=[{"item": a, "color": "Purple", "prices": price(0.2)},
                                    {"item": b, "color": "White", "prices": price(0.2)}])
        self.assertEqual([g["label"] for g in self.groups(doc)], ["Whites", "Purples"])
        whites = self.groups(doc)[0]
        self.assertEqual((whites["swatch"], whites["swatch_ink"]), ("#E8EEF3", "#10233A"))

    def test_group_photo(self):
        # A colour group can carry a photo; only a site file or http(s) URL is served.
        a, b = _items(2)
        t = frappe.get_doc(TEMPLATE, "Flowers almanac")
        for g in t.colour_groups:
            if g.label == "Whites":
                g.image = "/files/whites.jpg"
            if g.label == "Purples":
                g.image = "javascript:alert(1)"
        doc = make_catalogue(lines=[{"item": a, "color": "White", "prices": price(0.2)},
                                    {"item": b, "color": "Purple", "prices": price(0.2)}])
        groups = {g["label"]: g for g in self.groups(doc, t)}
        self.assertEqual(groups["Whites"]["image"], "/files/whites.jpg")
        self.assertIsNone(groups["Purples"]["image"])

    def test_product_photo_overrides_item_image(self):
        a, b = _items(2)
        doc = make_catalogue(lines=[{"item": a, "color": "White", "prices": price(0.2)},
                                    {"item": b, "color": "White", "prices": price(0.2)}])
        doc.products[0].image = "https://example.com/a.jpg"
        doc.products[1].image = "javascript:alert(1)"
        cards = {p["item"]: p for p in self.groups(doc)[0]["products"]}
        self.assertEqual(cards[a]["image"], "https://example.com/a.jpg")
        self.assertEqual(cards[b]["image"], _image_or_none(frappe.db.get_value("Item", b, "image")))

    def test_group_by_grade_and_item_group(self):
        a, b = _items(2)
        doc = make_catalogue(template="Coffee lots",
                             lines=[{"item": a, "grade": "AA", "prices": price(9.6)},
                                    {"item": a, "grade": "AB", "prices": price(8.1)},
                                    {"item": b, "grade": "AA", "prices": price(9.0)}])
        groups = self.groups(doc)
        self.assertEqual([g["label"] for g in groups], ["AA", "AB"])
        self.assertEqual([p["item"] for p in groups[0]["products"]], [a, b])
        doc2 = make_catalogue(template="Avocado export", lines=[{"item": a, "prices": price(12.4)}])
        self.assertEqual([g["label"] for g in self.groups(doc2)],
                         [frappe.db.get_value("Item", a, "item_group")])


class TestCards(DisplayCase):
    def test_product_fields_once_per_product(self):
        a, = _items(1)
        doc = make_catalogue(template="Coffee lots",
                             lines=[{"item": a, "grade": "AA", "prices": price(9.6), "specs": {"process": "Washed"}},
                                    {"item": a, "grade": "AB", "prices": price(8.1)}])
        doc.products[0].badges = "Microlot"
        doc.products[0].note = "Blackcurrant, bright acidity."
        doc.products[0].specs = json.dumps({"cup_score": "86", "variety": "SL28"})
        doc.save()
        for g in self.groups(doc):
            card = g["products"][0]
            self.assertEqual([b["label"] for b in card["badges"]], ["Microlot", "Cup score 86"])
            self.assertEqual(card["badges"][0]["background"], "#B5532E")
            self.assertEqual(card["note"], "Blackcurrant, bright acidity.")
            self.assertEqual(card["subtitle"], [{"label": "Variety", "value": "SL28"}])
        aa = self.groups(doc)[0]["products"][0]["lines"][0]
        self.assertEqual(aa["specs"], {"process": "Washed"})

    def test_blank_note_falls_back_to_item_description(self):
        a, = _items(1)
        frappe.db.set_value("Item", a, "description", "<p>From the item master</p>")
        doc = make_catalogue(lines=[{"item": a, "prices": price(0.2)}])
        self.assertEqual(self.groups(doc)[0]["products"][0]["note"], "From the item master")

    def test_hidden_sections_not_sent(self):
        a, = _items(1)
        tpl = copy_of(new="No codes", show_codes=0, show_weight=0).insert()
        doc = make_catalogue(template=tpl.name, lines=[{"item": a, "vbn": "114199", "weight": 11.3,
                                                         "prices": price(0.2)}])
        line = self.groups(doc, tpl)[0]["products"][0]["lines"][0]
        self.assertIsNone(line["vbn"])
        self.assertIsNone(line["weight"])


class TestTextThemeMixes(DisplayCase):
    def test_payload_text_falls_back_to_defaults(self):
        tpl = copy_of(new="Sparse", cta_label="", pack_label_plural="", tier_label="").insert()
        doc = make_catalogue(template=tpl.name, volume_tier_qty=4)
        text = D.build_display(doc, tpl)["text"]
        self.assertEqual(text["cta"], "Send my interest")
        self.assertEqual(text["packs"], "boxes")
        self.assertEqual(text["tier"], "Above 4 boxes")
        self.assertEqual(text["qty"], "Boxes")

    def test_theme_and_sections(self):
        doc = make_catalogue()
        out = D.build_display(doc, self.flowers)
        self.assertEqual(out["theme"]["brand"], "#1E4D3A")
        self.assertEqual(out["theme"]["fonts"]["css"], "/assets/upande_crm/catalogue/fonts/almanac/fonts.css")
        self.assertTrue(out["sections"]["cover"])
        self.assertFalse(out["sections"]["codes"])
        self.assertEqual([f["label"] for f in out["frequencies"]], ["One-off", "Weekly"])

    def test_mix_with_removed_line(self):
        a, b = _items(2)
        doc = make_catalogue(lines=[{"item": a, "color": "White", "prices": price(0.2)},
                                    {"item": b, "color": "Purple", "prices": price(0.2)}])
        keep = doc.lines[0].name
        doc.append("mixes", {"title": "Half stale", "items": json.dumps([{"line": keep, "boxes": 2},
                                                                         {"line": "gone", "boxes": 1}])})
        doc.append("mixes", {"title": "All stale", "items": json.dumps([{"line": "gone", "boxes": 1}])})
        doc.save()
        mixes = D.build_display(doc, self.flowers)["mixes"]
        self.assertEqual([m["title"] for m in mixes], ["Half stale"])
        self.assertEqual(mixes[0]["items"], [{"line": keep, "boxes": 2}])
        self.assertEqual(mixes[0]["colours"], ["#E8EEF3"])


class TestEstimate(DisplayCase):
    LINES = [{"line": "a", "pack_qty": 300, "prices": {"USD": {"price": 0.232, "tier": 0.2204}}},
             {"line": "b", "pack_qty": 320, "prices": {"USD": {"price": 0.186}}},
             {"line": "c", "pack_qty": 100, "prices": {"USD": {"price": None}}},
             {"line": "d", "pack_qty": None, "prices": {"USD": {"price": 1.0}}}]
    FREQ = [{"label": "One-off", "period_text": "", "recurring": 0},
            {"label": "Weekly", "period_text": "a week", "recurring": 1}]

    def test_estimate_split_by_frequency(self):
        out = D.estimate(self.LINES, [{"line": "a", "qty": 2, "frequency": "Weekly"},
                                      {"line": "b", "qty": 1, "frequency": "One-off"}], "USD", 4, self.FREQ)
        self.assertEqual(out, [{"frequency": "One-off", "period_text": "once", "amount": 59.52},
                               {"frequency": "Weekly", "period_text": "a week", "amount": 139.2}])

    def test_estimate_uses_tier_above_threshold_and_skips_unpriced(self):
        out = D.estimate(self.LINES, [{"line": "a", "qty": 5, "frequency": "Weekly"},
                                      {"line": "c", "qty": 3, "frequency": "Weekly"},
                                      {"line": "d", "qty": 3, "frequency": "One-off"}], "USD", 4, self.FREQ)
        self.assertEqual(out, [{"frequency": "Weekly", "period_text": "a week", "amount": 330.6}])


class TestReviewFixes(DisplayCase):
    def test_catalogue_cover_wins_over_template_mode(self):
        doc = make_catalogue(cover_image="/files/season-cover.jpg")
        theme = D.build_display(doc, self.flowers)["theme"]
        self.assertEqual((theme["cover_mode"], theme["cover_image"]), ("Image", "/files/season-cover.jpg"))

    def test_spec_shown_after_display_kind_changes(self):
        # A Column spec switched to Subtitle still shows, read from the lines.
        a, = _items(1)
        doc = make_catalogue(template="Coffee lots", lines=[{"item": a, "grade": "AA", "prices": price(9.6),
                                                              "specs": {"process": "Washed"}}])
        tpl = frappe.get_doc(TEMPLATE, "Coffee lots")
        next(s for s in tpl.spec_columns if s.key == "process").display = "Subtitle"
        card = D.build_display(doc, tpl)["groups"][0]["products"][0]
        self.assertIn({"label": "Process", "value": "Washed"}, card["subtitle"])

    def test_line_keeps_its_colour_word(self):
        a, = _items(1)
        doc = make_catalogue(lines=[{"item": a, "color": "Burgundy Red", "prices": price(0.2)}])
        line = self.groups(doc)[0]["products"][0]["lines"][0]
        self.assertEqual(line["color"], "Burgundy Red")


class TestEditableEverything(DisplayCase):
    """Every visible phrase, the block order, the layout and the fonts come
    from the template (follow-up to the magazine design, 2026-10-26)."""

    def test_page_text_defaults_and_overrides(self):
        tpl = copy_of(new="Words", page_text={"mixes_heading": "Our bundles", "field_name": "  ",
                                               "nonsense_key": "x"}).insert()
        page = D.build_display(make_catalogue(template=tpl.name), tpl)["text"]["page"]
        self.assertEqual(page["mixes_heading"], "Our bundles")
        self.assertEqual(page["field_name"], "Your name")  # blank keeps the default
        self.assertEqual(page["form_title"], "Your details")
        self.assertNotIn("nonsense_key", page)
        self.assertEqual(set(page), set(D.PAGE_TEXT))

    def test_page_text_placeholders_filled(self):
        doc = make_catalogue(volume_tier_qty=4)
        page = D.build_display(doc, self.flowers)["text"]["page"]
        self.assertEqual(page["bar_empty"], "Enter boxes on the lines you want")

    def test_layout_and_order_reach_the_page(self):
        tpl = copy_of(new="Compact", card_style="Photo top", density="Compact", heading_size="Large",
                      section_order="products,letter,mixes").insert()
        layout = D.build_display(make_catalogue(template=tpl.name), tpl)["layout"]
        self.assertEqual(layout, {"card_style": "Photo top", "density": "Compact", "heading_size": "Large",
                                  "order": ["products", "letter", "mixes"]})

    def test_layout_defaults(self):
        layout = D.build_display(make_catalogue(), self.flowers)["layout"]
        self.assertEqual(layout, {"card_style": "Photo left", "density": "Airy", "heading_size": "Medium",
                                  "order": ["letter", "mixes", "products"]})

    def test_uploaded_fonts_override_the_pair_per_role(self):
        tpl = copy_of(new="Own fonts", font_head_file="/files/brand-head.woff2").insert()
        fonts = D.build_display(make_catalogue(template=tpl.name), tpl)["theme"]["fonts"]
        self.assertEqual(fonts["head_url"], "/files/brand-head.woff2")
        self.assertIsNone(fonts["text_url"])
        self.assertEqual(fonts["text"], "Archivo Narrow")
