"""Tests for magazine templates (docs/superpowers/specs/
2026-10-26-crm-catalogue-magazine-design.md): the record, its checks, the
shipped starters, and what a catalogue keeps in step with its template."""

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm import catalogue_templates as CT
from upande_crm.tests.test_catalogue_model import _item, make_catalogue

TEMPLATE = "CRM Catalogue Template"


def copy_of(name="Flowers almanac", new="Test template", **kw):
    doc = frappe.copy_doc(frappe.get_doc(TEMPLATE, name))
    doc.template_name = new
    doc.is_standard = 0
    doc.update(kw)
    return doc


class TemplateCase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        CT.ensure_starters()
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()


class TestStarters(TemplateCase):
    def test_starters_created_once(self):
        CT.ensure_starters()
        self.assertTrue({"Flowers almanac", "Avocado export", "Coffee lots"}
                        <= set(frappe.get_all(TEMPLATE, pluck="name")))
        self.assertEqual(CT.ensure_starters(), [])

    def test_starter_edits_survive(self):
        frappe.db.set_value(TEMPLATE, "Flowers almanac", "headline", "Edited by the site")
        CT.ensure_starters()
        self.assertEqual(frappe.db.get_value(TEMPLATE, "Flowers almanac", "headline"), "Edited by the site")

    def test_starter_values(self):
        avo = frappe.get_doc(TEMPLATE, "Avocado export")
        self.assertEqual((avo.group_by, avo.pack_label, avo.grade_label), ("Item Group", "carton", "Count"))
        self.assertEqual(avo.frequency_labels(), ["Per shipment", "Monthly"])
        coffee = frappe.get_doc(TEMPLATE, "Coffee lots")
        self.assertEqual({s.key: s.display for s in coffee.spec_columns},
                         {"cup_score": "Badge", "process": "Column", "variety": "Subtitle"})


class TestValidation(TemplateCase):
    def test_bad_hex_refused(self):
        with self.assertRaises(frappe.ValidationError):
            copy_of(brand="green").insert()

    def test_spec_keys_unique_slugs(self):
        doc = copy_of(new="Spec test")
        doc.set("spec_columns", [{"key": "cup", "label": "Cup", "display": "Badge"},
                                 {"key": "cup", "label": "Cup 2", "display": "Column"}])
        with self.assertRaises(frappe.ValidationError):
            doc.insert()
        doc.set("spec_columns", [{"key": "Cup Score", "label": "Cup", "display": "Badge"}])
        with self.assertRaises(frappe.ValidationError):
            doc.insert()

    def test_needs_a_frequency(self):
        doc = copy_of(new="No frequency")
        doc.set("frequencies", [])
        with self.assertRaises(frappe.ValidationError):
            doc.insert()

    def test_delete_template_in_use_refused(self):
        doc = copy_of(new="In use").insert()
        make_catalogue(template=doc.name)
        with self.assertRaises(frappe.ValidationError) as ctx:
            frappe.delete_doc(TEMPLATE, doc.name)
        self.assertIn("1", str(ctx.exception))


class TestCatalogueFollowsTemplate(TemplateCase):
    def _two_items(self):
        items = frappe.get_all("Item", filters={"disabled": 0}, pluck="name", limit=2)
        return items[0], items[1]

    def test_catalogue_defaults_to_flowers_almanac(self):
        self.assertEqual(make_catalogue().template, "Flowers almanac")

    def test_catalogue_products_follow_lines(self):
        a, b = self._two_items()
        doc = make_catalogue(lines=[{"item": a, "grade": "50 cm"}, {"item": a, "grade": "60 cm"},
                                    {"item": b, "grade": "60 cm"}])
        self.assertEqual(sorted(p.item for p in doc.products), sorted([a, b]))
        next(p for p in doc.products if p.item == a).note = "Keeps two weeks"
        doc.set("lines", [l for l in doc.lines if l.item == a])
        doc.save()
        self.assertEqual([(p.item, p.note) for p in doc.products], [(a, "Keeps two weeks")])

    def test_template_changes_never_delete_catalogue_data(self):
        # Review fix: badges/specs the template no longer lists are kept in
        # storage (only the page filters them), so renaming a badge or picking
        # the wrong template and saving loses nothing.
        a, _b = self._two_items()
        doc = make_catalogue(lines=[{"item": a, "specs": {"process": "Washed"}}])
        doc.products[0].badges = "Bestseller\nMicrolot"
        doc.save()
        doc.template = "Avocado export"
        doc.save()
        doc.reload()
        self.assertEqual(doc.products[0].badges, "Bestseller\nMicrolot")
        self.assertEqual(frappe.parse_json(doc.lines[0].specs), {"process": "Washed"})

    def test_default_template_cannot_be_deleted(self):
        from upande_crm.api import catalogues as C

        for name in frappe.get_all("CRM Catalogue", filters={"template": "Flowers almanac"}, pluck="name"):
            frappe.db.set_value("CRM Catalogue", name, "template", "Coffee lots")
        with self.assertRaises(frappe.ValidationError):
            C.crm_catalogue_template_delete("Flowers almanac")

    def test_existing_catalogues_get_flowers_almanac(self):
        doc = make_catalogue()
        frappe.db.set_value("CRM Catalogue", doc.name, "template", None)
        self.assertGreaterEqual(CT.assign_default_template(), 1)
        self.assertEqual(frappe.db.get_value("CRM Catalogue", doc.name, "template"), "Flowers almanac")


class TestTemplateApi(TemplateCase):
    def test_contrast_ratio_known_values(self):
        from upande_crm.api import catalogues as C

        self.assertAlmostEqual(C.contrast_ratio("#000000", "#FFFFFF"), 21.0, places=1)
        self.assertAlmostEqual(C.contrast_ratio("#777777", "#FFFFFF"), 4.48, places=2)

    def test_template_save_warns_low_contrast(self):
        from upande_crm.api import catalogues as C

        data = frappe.get_doc(TEMPLATE, "Flowers almanac").as_dict()
        data.update({"name": None, "template_name": "Low contrast", "ink": "#777777", "paper": "#888888"})
        out = C.crm_catalogue_template_save(frappe.as_json(data))
        self.assertTrue(any("text on paper" in w for w in out["warnings"]))
        self.assertEqual(out["template"]["ink"], "#777777")

    def test_template_save_needs_writer_role(self):
        from upande_crm.api import catalogues as C
        from upande_crm.tests.test_catalogues import SALES, sales_user

        sales_user()
        frappe.set_user(SALES)
        data = frappe.get_doc(TEMPLATE, "Flowers almanac").as_dict()
        with self.assertRaises(frappe.PermissionError):
            C.crm_catalogue_template_save(frappe.as_json(data))

    def test_copy_template(self):
        from upande_crm.api import catalogues as C

        name = C.crm_catalogue_template_copy("Coffee lots", "Coffee lots (Kaitet)")["name"]
        doc = frappe.get_doc(TEMPLATE, name)
        self.assertEqual(doc.is_standard, 0)
        self.assertEqual([s.key for s in doc.spec_columns], ["cup_score", "process", "variety"])

    def test_template_list_counts_use(self):
        from upande_crm.api import catalogues as C

        make_catalogue(template="Coffee lots")
        row = next(r for r in C.crm_catalogue_templates()["rows"] if r["name"] == "Coffee lots")
        self.assertGreaterEqual(row["catalogues_using"], 1)
        self.assertIn("almanac", C.crm_catalogue_templates()["font_pairs"])

    def test_catalogue_save_products_and_mixes(self):
        from upande_crm.api import catalogues as C

        a, = frappe.get_all("Item", filters={"disabled": 0}, pluck="name", limit=1)
        out = C.crm_catalogue_save(frappe.as_json({
            "title": "Coffee", "company": frappe.db.get_value("Company", {}, "name"), "currencies": "USD",
            "template": "Coffee lots",
            "lines": [{"item": a, "grade": "AA", "specs": {"process": "Washed"}, "prices": {"USD": {"price": 9.6}}}],
            "products": [{"item": a, "badges": ["Microlot"], "note": "Bright", "specs": {"cup_score": "86"}}],
        }))["catalogue"]
        line = out["lines"][0]["name"]
        out = C.crm_catalogue_save(frappe.as_json({**out, "mixes": [{"title": "Lot pair",
                                                                    "items": [{"line": line, "boxes": 2}]}]}))["catalogue"]
        got = C.crm_catalogue_get(out["name"])["catalogue"]
        self.assertEqual(got["products"], [{"item": a, "badges": ["Microlot"], "note": "Bright",
                                            "specs": {"cup_score": "86"}}])
        self.assertEqual([(i["line"], i["boxes"]) for i in got["mixes"][0]["items"]], [(line, 2)])
        self.assertEqual(got["lines"][0]["specs"], {"process": "Washed"})
        self.assertEqual(got["lines"][0]["group"], "AA")

    def test_template_delete_endpoint_refuses_in_use(self):
        from upande_crm.api import catalogues as C

        make_catalogue(template="Avocado export")
        with self.assertRaises(frappe.ValidationError):
            C.crm_catalogue_template_delete("Avocado export")


class TestMixesSurvive(TemplateCase):
    def _lines(self):
        a, b = frappe.get_all("Item", filters={"disabled": 0}, pluck="name", limit=2)
        return [{"item": a, "grade": "60 cm", "box_type": "Standard", "color": "White"},
                {"item": b, "grade": "70 cm", "box_type": "Standard", "color": "Pink"}]

    def test_duplicate_keeps_mixes_pointing_at_its_own_lines(self):
        from upande_crm.api import catalogues as C

        doc = make_catalogue(lines=self._lines())
        doc.append("mixes", {"title": "Pair", "items": frappe.as_json([{"line": doc.lines[0].name, "boxes": 2},
                                                                        {"line": doc.lines[1].name, "boxes": 1}])})
        doc.save()
        new = frappe.get_doc("CRM Catalogue", C.crm_catalogue_duplicate(doc.name)["name"])
        refs = [i["line"] for i in frappe.parse_json(new.mixes[0].items)]
        self.assertEqual(refs, [l.name for l in new.lines])
        self.assertEqual([i["boxes"] for i in frappe.parse_json(new.mixes[0].items)], [2, 1])

    def test_reimport_keeps_mixes(self):
        from upande_crm.api import catalogues as C

        doc = make_catalogue(lines=self._lines())
        doc.append("mixes", {"title": "Pair", "items": frappe.as_json([{"line": doc.lines[0].name, "boxes": 2}])})
        doc.save()
        got = C.crm_catalogue_get(doc.name)["catalogue"]
        fresh = [{k: l[k] for k in ("item", "grade", "box_type", "color")} for l in got["lines"]]  # no names: an import
        out = C.crm_catalogue_save(frappe.as_json({**got, "lines": fresh}))["catalogue"]
        ref = out["mixes"][0]["items"][0]["line"]
        self.assertIn(ref, [l["name"] for l in out["lines"]])
        self.assertEqual(next(l for l in out["lines"] if l["name"] == ref)["grade"], "60 cm")
