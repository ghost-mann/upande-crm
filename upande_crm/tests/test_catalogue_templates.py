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

    def test_unknown_badges_and_specs_dropped(self):
        a, _b = self._two_items()
        doc = make_catalogue(lines=[{"item": a, "specs": {"bogus": "1"}}])
        doc.products[0].badges = "Bestseller\nBogus"
        doc.save()
        self.assertEqual(doc.products[0].badges, "Bestseller")
        self.assertFalse(frappe.parse_json(doc.lines[0].specs or "{}"))

    def test_existing_catalogues_get_flowers_almanac(self):
        doc = make_catalogue()
        frappe.db.set_value("CRM Catalogue", doc.name, "template", None)
        self.assertGreaterEqual(CT.assign_default_template(), 1)
        self.assertEqual(frappe.db.get_value("CRM Catalogue", doc.name, "template"), "Flowers almanac")
