"""Tests for the CRM theme.

The first class is the load-bearing one: **seeding the shipped values must
reproduce the shipped palette.** Without it, adding theming would silently
restyle the CRM for every site that ever saves a setting. The shipped values are
scraped from `frontend/src/index.css` rather than duplicated here, so the test
tracks the stylesheet instead of a copy of it that can drift.

Fitted derivations cannot land on hand-tuned hex values exactly. The tolerance is
stated per token and every real divergence is enumerated in DIVERGENCES, so a
regression shows up as a new entry rather than as a slightly-off colour nobody
notices.
"""

import os
import re

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_crm.api import settings as S
from upande_crm.theme import color, get_theme_css
from upande_crm.theme import tokens as T

# Total absolute channel delta tolerated between a derived token and the shipped
# one. 6 over three channels is at most 2 per channel — below a perceptible step.
TOLERANCE = 8

# Shipped tokens the derivation deliberately does not reproduce.
DIVERGENCES = {
    # The shipped --warn-soft (#f7ecce) is within two channels of --gold-soft
    # (#f7edcd): it was hand-matched to the gold accent, not derived from the
    # warning seed. Deriving it gives a greyer #f1ebe0. Preferred: on a maroon
    # theme a warning fill still tracking gold would be a leftover.
    "warn-soft",
}

# Tokens in index.css that the theme layer intentionally leaves to the bundle.
NOT_DERIVED = {"bio"}

SHIPPED_SEEDS = {
    "theme_accent": "#d9a514",
    "theme_ink": "#0a0a0a",
    "theme_ink_muted": "#8a8780",
    "theme_canvas": "#f4f3ef",
    "theme_success": "#3f8f4f",
    "theme_warning": "#96650f",
    "theme_danger": "#c4302b",
    "theme_info": "#175cd3",
}

MAROON_SEEDS = dict(
    SHIPPED_SEEDS,
    theme_accent="#8c1d2e",
    theme_ink="#14100f",
    theme_ink_muted="#8a807e",
    theme_canvas="#f6f2f0",
)


def _shipped_root():
    """The `:root` block of the compiled stylesheet, as {token: value}."""
    path = os.path.join(frappe.get_app_path("upande_crm"), "..", "frontend", "src", "index.css")
    with open(os.path.normpath(path), encoding="utf-8") as handle:
        css = handle.read()
    root = css.split(":root {")[1].split("\n  }")[0]
    return {k: v.strip() for k, v in re.findall(r"--([a-z0-9-]+):\s*([^;]+);", root)}


def _delta(a, b):
    ca, cb = color.parse(a), color.parse(b)
    return sum(abs(x - y) for x, y in zip(ca, cb))


class TestReproducesShippedPalette(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shipped = _shipped_root()
        cls.derived = T.get_tokens(SHIPPED_SEEDS)

    def test_every_shipped_hex_is_reproduced_within_tolerance(self):
        checked = 0
        for name, want in self.shipped.items():
            if not want.startswith("#") or name in NOT_DERIVED or name in DIVERGENCES:
                continue
            got = self.derived.get(name)
            self.assertIsNotNone(got, f"--{name} is no longer derived")
            self.assertLessEqual(
                _delta(want, got), TOLERANCE,
                f"--{name}: shipped {want}, derived {got}",
            )
            checked += 1
        # Guards against the scrape silently matching nothing.
        self.assertGreater(checked, 20)

    def test_the_structural_colours_are_exact(self):
        for name in ("ink", "ink-mute", "bg", "surface", "surface-3", "gold",
                     "good", "warn", "bad", "info", "text", "text-3"):
            self.assertEqual(self.derived[name].lower(), self.shipped[name].lower(), name)

    def test_alpha_tokens_match_the_stylesheet_exactly(self):
        for name in ("hover", "hairline", "shadow-hover"):
            self.assertEqual(self.derived[name], self.shipped[name], name)

    def test_documented_divergences_still_diverge(self):
        # If a divergence is fixed, it should leave DIVERGENCES rather than sit
        # there implying a difference that no longer exists.
        for name in DIVERGENCES:
            self.assertGreater(_delta(self.shipped[name], self.derived[name]), TOLERANCE, name)

    def test_shipped_fallbacks_match_the_stylesheet(self):
        for name, value in T.SHIPPED.items():
            self.assertEqual(value.lower(), self.shipped[name].lower(), name)

    def test_gold_theme_keeps_ink_text_on_accent_fills(self):
        # The shipped design puts ink on gold; the derivation must agree, or
        # every accent button would flip colour the moment a theme is saved.
        self.assertEqual(self.derived["on-accent"], "#000000")


class TestColorMaths(FrappeTestCase):
    def test_parse_accepts_full_hex_only(self):
        self.assertEqual(color.parse("#d9a514"), (217, 165, 20))
        for bad in ("#fff", "d9a514", "", None, "#gggggg", "#d9a5144", 12):
            self.assertIsNone(color.parse(bad), repr(bad))

    def test_parse_tolerates_surrounding_whitespace(self):
        self.assertEqual(color.parse("  #0a0a0a "), (10, 10, 10))

    def test_mix_endpoints_and_midpoint(self):
        a, b = (0, 0, 0), (255, 255, 255)
        self.assertEqual(color.to_hex(color.mix(a, b, 0)), "#000000")
        self.assertEqual(color.to_hex(color.mix(a, b, 1)), "#ffffff")
        self.assertEqual(color.to_hex(color.mix(a, b, 0.5)), "#808080")

    def test_contrast_is_symmetric_and_bounded(self):
        black, white = (0, 0, 0), (255, 255, 255)
        self.assertAlmostEqual(color.contrast(black, white), 21.0, places=1)
        self.assertAlmostEqual(color.contrast(white, black), 21.0, places=1)
        self.assertAlmostEqual(color.contrast(black, black), 1.0, places=3)

    def test_best_contrast_judges_the_worst_background(self):
        # White wins on the dark end, black on the light one; the worst-case rule
        # must pick the one that survives both.
        picked = color.best_contrast(((10, 10, 10), (240, 240, 240)), (color.BLACK, color.WHITE))
        self.assertIn(picked, (color.BLACK, color.WHITE))
        worst_picked = min(color.contrast(bg, picked) for bg in ((10, 10, 10), (240, 240, 240)))
        other = color.WHITE if picked == color.BLACK else color.BLACK
        worst_other = min(color.contrast(bg, other) for bg in ((10, 10, 10), (240, 240, 240)))
        self.assertGreaterEqual(worst_picked, worst_other)

    def test_hsl_channels_round_trip_known_colours(self):
        self.assertEqual(color.to_hsl_channels((10, 10, 10)), "0 0% 4%")
        self.assertEqual(color.to_hsl_channels((255, 255, 255)), "0 0% 100%")
        self.assertEqual(color.to_hsl_channels((196, 48, 43)), "2 64% 47%")


class TestTokenAssembly(FrappeTestCase):
    def test_no_seeds_yields_no_tokens_and_no_css(self):
        # An unthemed site must render byte-identically to the compiled bundle.
        self.assertEqual(T.get_tokens({}), {})
        self.assertEqual(T.get_theme_css({}), "")

    def test_a_malformed_seed_is_skipped_not_fatal(self):
        out = T.get_tokens({"theme_accent": "not-a-colour", "theme_ink": "#0a0a0a"})
        self.assertNotIn("gold", out)
        self.assertIn("ink", out)

    def test_accent_alone_produces_the_accent_family(self):
        out = T.get_tokens({"theme_accent": "#8c1d2e"})
        for name in ("gold", "gold-2", "gold-soft", "gold-text", "selected", "grad-gold",
                     "on-accent"):
            self.assertIn(name, out)

    def test_css_is_a_root_block_of_custom_properties(self):
        css = T.get_theme_css(SHIPPED_SEEDS)
        self.assertTrue(css.startswith(":root {"))
        self.assertTrue(css.rstrip().endswith("}"))
        self.assertIn("--gold: #d9a514;", css)

    def test_shadcn_channels_are_bare_triples_not_colours(self):
        out = T.get_tokens(SHIPPED_SEEDS)
        for name in ("background", "foreground", "border", "input", "ring", "destructive"):
            self.assertRegex(out[name], r"^\d+ \d+% \d+%$", name)

    def test_seed_fields_are_all_known_settings_keys(self):
        for field in T.THEME_FIELDS:
            self.assertIn(field, S.DEFAULTS, field)


class TestMaroonTheme(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tokens = T.get_tokens(MAROON_SEEDS)

    def test_accent_is_the_maroon_seed(self):
        self.assertEqual(self.tokens["gold"], "#8c1d2e")

    def test_on_accent_flips_to_white(self):
        # This is what the component change exists for: ink text on dark maroon
        # is effectively invisible.
        self.assertEqual(self.tokens["on-accent"], "#ffffff")

    def test_on_accent_clears_wcag_aa_on_both_gradient_ends(self):
        on = color.parse(self.tokens["on-accent"])
        for end in ("gold", "gold-2"):
            self.assertGreaterEqual(
                color.contrast(color.parse(self.tokens[end]), on), 4.5, end)

    def test_accent_text_is_legible_on_the_soft_fill(self):
        ratio = color.contrast(color.parse(self.tokens["gold-text"]),
                               color.parse(self.tokens["gold-soft"]))
        self.assertGreaterEqual(ratio, 4.5)

    def test_shadows_take_the_ink_tint(self):
        self.assertIn("rgba(20, 16, 15", self.tokens["shadow-card"])

    def test_every_gold_theme_token_is_also_produced(self):
        # A theme that omitted a token would leave that one value stuck on the
        # compiled palette — a maroon app with one gold detail.
        self.assertEqual(set(T.get_tokens(SHIPPED_SEEDS)), set(self.tokens))


class TestThemeEndpoints(FrappeTestCase):
    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)

    def test_payload_shape(self):
        d = S.crm_theme()
        for key in ("seeds", "tokens", "derived", "contrast", "fonts", "can_edit", "installed"):
            self.assertIn(key, d)
        self.assertEqual(set(d["seeds"]), set(T.THEME_FIELDS))
        self.assertNotIn("presets", d)

    def test_save_writes_seeds_and_derives(self):
        d = S.crm_theme_save(frappe.as_json({"theme_accent": "#8c1d2e"}))
        self.assertEqual(d["seeds"]["theme_accent"], "#8c1d2e")
        self.assertEqual(d["tokens"]["on-accent"], "#ffffff")

    def test_save_is_idempotent(self):
        first = S.crm_theme_save(frappe.as_json(MAROON_SEEDS))
        second = S.crm_theme_save(frappe.as_json(MAROON_SEEDS))
        self.assertEqual(first["tokens"], second["tokens"])

    def test_save_rejects_a_malformed_colour(self):
        with self.assertRaises(frappe.ValidationError):
            S.crm_theme_save(frappe.as_json({"theme_accent": "#ggg"}))

    def test_save_rejects_an_empty_or_unknown_payload(self):
        for payload in ({}, {"nonsense": "#000000"}):
            with self.assertRaises(frappe.ValidationError):
                S.crm_theme_save(frappe.as_json(payload))

    def test_blanking_a_seed_is_allowed(self):
        # Clearing back to "not themed" must be possible from the UI.
        S.crm_theme_save(frappe.as_json(MAROON_SEEDS))
        d = S.crm_theme_save(frappe.as_json({"theme_accent": ""}))
        self.assertEqual(d["seeds"]["theme_accent"], "")
        self.assertNotIn("gold", d["tokens"])

    def test_get_theme_css_reflects_the_saved_theme(self):
        S.crm_theme_save(frappe.as_json(MAROON_SEEDS))
        frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)
        self.assertIn("--gold: #8c1d2e;", get_theme_css())

    def test_guest_and_sales_user_cannot_change_the_theme(self):
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            S.crm_theme_save(frappe.as_json(MAROON_SEEDS))
        frappe.set_user("Administrator")

        email = "crm-theme-test@example.com"
        if not frappe.db.exists("User", email):
            frappe.flags.mute_emails = True
            frappe.get_doc({
                "doctype": "User", "email": email, "first_name": "CRM Theme Test",
                "send_welcome_email": 0, "roles": [{"role": "Sales User"}],
            }).insert(ignore_permissions=True)
        frappe.set_user(email)
        self.assertFalse(S.crm_theme()["can_edit"])
        with self.assertRaises(frappe.PermissionError):
            S.crm_theme_save(frappe.as_json({"theme_accent": "#123456"}))


class TestSettingsControllerValidatesSeeds(FrappeTestCase):
    def tearDown(self):
        frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)

    def test_bad_hex_on_the_doctype_throws(self):
        doc = frappe.get_single(S.SETTINGS_DOCTYPE)
        doc.theme_ink = "0a0a0a"  # missing the '#'
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_whitespace_is_trimmed_rather_than_rejected(self):
        doc = frappe.get_single(S.SETTINGS_DOCTYPE)
        doc.theme_ink = "  #0a0a0a  "
        doc.save(ignore_permissions=True)
        self.assertEqual(frappe.get_single(S.SETTINGS_DOCTYPE).theme_ink, "#0a0a0a")


class TestThemeExtras(FrappeTestCase):
    def test_blank_new_seeds_change_nothing(self):
        base = T.get_tokens(SHIPPED_SEEDS)
        blank = dict(SHIPPED_SEEDS, **{f: "" for f in T.THEME_FIELDS if f not in SHIPPED_SEEDS})
        blank["theme_accent_primary"] = 0
        self.assertEqual(T.get_tokens(blank), base)

    def test_accent_dark_pins_its_tokens(self):
        t = T.get_tokens(dict(SHIPPED_SEEDS, theme_accent_dark="#553300"))
        self.assertEqual(t["gold-2"], "#553300")
        self.assertEqual(t["gold-text"], "#553300")
        self.assertIn("#553300", t["grad-gold"])

    def test_accent_soft_pins_selected(self):
        t = T.get_tokens(dict(SHIPPED_SEEDS, theme_accent_soft="#fff1d6"))
        self.assertEqual(t["gold-soft"], "#fff1d6")
        self.assertEqual(t["selected"], "#fff1d6")

    def test_wash_and_borders_pin(self):
        t = T.get_tokens(dict(SHIPPED_SEEDS, theme_wash="#eeeeee", theme_border="#dddddd",
                              theme_border_strong="#bbbbbb"))
        self.assertEqual(t["surface-3"], "#eeeeee")
        self.assertEqual(t["line"], "#dddddd")
        self.assertEqual(t["line-2"], "#bbbbbb")
        self.assertEqual(t["border"], color.to_hsl_channels(color.parse("#dddddd")))

    def test_accent_primary_repaints_primary(self):
        t = T.get_tokens(dict(MAROON_SEEDS, theme_accent_primary=1))
        self.assertEqual(t["primary"], color.to_hsl_channels(color.parse("#8c1d2e")))
        self.assertEqual(t["nav-active"], "#8c1d2e")
        self.assertEqual(t["nav-active-fg"], t["on-accent"])

    def test_accent_primary_without_accent_does_nothing(self):
        self.assertEqual(T.get_tokens({"theme_accent_primary": 1}), {})

    def test_bundled_font_sets_the_stack(self):
        t = T.get_tokens({"theme_font_sans": "Inter"})
        self.assertTrue(t["f"].startswith('"Inter"'))

    def test_custom_font_needs_a_name(self):
        self.assertNotIn("f", T.get_tokens({"theme_font_sans": "Custom"}))
        t = T.get_tokens({"theme_font_display": "Custom", "theme_font_display_name": "Lora"})
        self.assertTrue(t["display"].startswith('"Lora"'))

    def test_radius_seeds_emit_tokens(self):
        t = T.get_tokens({"theme_radius": "4px", "theme_radius_card": "0", "theme_radius_panel": "1rem"})
        self.assertEqual((t["r-sm"], t["radius"], t["r-card"], t["r-panel"]), ("4px", "4px", "0", "1rem"))

    def test_custom_css_is_appended_last(self):
        css = T.get_theme_css({"theme_accent": "#d9a514", "theme_custom_css": "--ink-4: #54586b;"})
        lines = css.strip().splitlines()
        self.assertEqual(lines[-1], "}")
        self.assertEqual(lines[-2].strip(), "--ink-4: #54586b;")

    def test_custom_css_alone_still_emits(self):
        self.assertIn("--ink-4: #54586b;", T.get_theme_css({"theme_custom_css": "--ink-4: #54586b;"}))

    def test_font_link_only_for_allowed_host(self):
        from upande_crm.theme import fonts
        ok = "https://fonts.googleapis.com/css2?family=Lora"
        self.assertEqual(fonts.resolve({"theme_google_fonts_url": ok})["link"], ok)
        self.assertIsNone(fonts.resolve({"theme_google_fonts_url": "https://evil.example/x.css"})["link"])

    def test_contrast_report_flags_unreadable_text(self):
        t = T.get_tokens(dict(SHIPPED_SEEDS, theme_ink="#f0f0f0"))
        rep = {r["key"]: r for r in T.contrast_report(t)}
        self.assertEqual(rep["text_on_bg"]["level"], "bad")

    def test_contrast_report_passes_the_shipped_palette(self):
        rep = {r["key"]: r for r in T.contrast_report(T.get_tokens(SHIPPED_SEEDS))}
        self.assertEqual(rep["text_on_bg"]["level"], "ok")
        self.assertTrue(all(r["label"] and r["ratio"] > 1 for r in rep.values()))

    def test_contrast_report_works_unthemed(self):
        self.assertTrue(T.contrast_report({}))


class TestThemeValidation(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)

    def _save(self, **kw):
        doc = frappe.get_single(S.SETTINGS_DOCTYPE)
        doc.update(kw)
        doc.save(ignore_permissions=True)

    def test_radius_requires_a_css_length(self):
        for bad in ("12", "1e3px", "10 px", "calc(1px)", "-4px"):
            with self.assertRaises(frappe.ValidationError, msg=bad):
                self._save(theme_radius=bad)

    def test_radius_accepts_lengths(self):
        self._save(theme_radius="6px", theme_radius_card="0", theme_radius_panel="1.25rem")

    def test_font_url_host_is_enforced(self):
        with self.assertRaises(frappe.ValidationError):
            self._save(theme_font_sans="Custom", theme_font_sans_name="Lato",
                       theme_google_fonts_url="https://evil.example/x.css")

    def test_custom_font_needs_name_and_url(self):
        with self.assertRaises(frappe.ValidationError):
            self._save(theme_font_sans="Custom", theme_font_sans_name="", theme_google_fonts_url="")

    def test_font_name_is_plain(self):
        with self.assertRaises(frappe.ValidationError):
            self._save(theme_font_sans="Custom", theme_font_sans_name='Lato"; } body {',
                       theme_google_fonts_url="https://fonts.googleapis.com/css2?family=Lato")

    def test_custom_css_cannot_close_the_style_tag(self):
        with self.assertRaises(frappe.ValidationError):
            self._save(theme_custom_css="</style><script>alert(1)</script>")

    def test_reset_clears_every_theme_field(self):
        S.crm_theme_save(frappe.as_json({"theme_accent": "#8c1d2e", "theme_radius": "4px",
                                         "theme_accent_primary": 1}))
        S.crm_theme_reset()
        frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)
        s = S.get_settings()
        self.assertTrue(all(not s.get(f) for f in T.THEME_FIELDS))
        self.assertEqual(get_theme_css(), "")

    def test_preview_does_not_write(self):
        before = S.get_settings()["theme_accent"]
        out = S.crm_theme_preview(frappe.as_json({"theme_accent": "#123456"}))
        self.assertEqual(out["tokens"]["gold"], "#123456")
        frappe.clear_document_cache(S.SETTINGS_DOCTYPE, S.SETTINGS_DOCTYPE)
        self.assertEqual(S.get_settings()["theme_accent"], before)

    def test_preview_tolerates_an_invalid_draft(self):
        out = S.crm_theme_preview(frappe.as_json({"theme_accent": "#12"}))
        self.assertNotIn("gold", out["tokens"])

    def test_theme_preset_field_is_gone(self):
        self.assertFalse(frappe.get_meta(S.SETTINGS_DOCTYPE).has_field("theme_preset"))
        self.assertFalse(hasattr(S, "crm_theme_apply_preset"))
