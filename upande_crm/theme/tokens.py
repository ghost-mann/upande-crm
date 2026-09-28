"""Assemble the CRM's CSS variable overrides from the settings seeds.

Returns bare token names (no leading '--'); `get_theme_css` adds them. An empty
dict means nothing is configured, so no <style> block is emitted at all and the
page is byte-identical to the compiled bundle.

**Every fraction here was fitted against the shipped palette in
`frontend/src/index.css`** so that seeding the shipped values reproduces the
shipped look. `tests/test_theme.py` asserts that, token by token. Two findings
from that fitting are worth keeping in view:

* Lines and low surfaces mix the canvas toward **ink-mute**, not ink. Mixing a
  warm cream toward pure ink desaturates it, which visibly greys the hairlines;
  toward the muted grey it reproduces `--surface-3` exactly.
* Status "soft" fills mix toward **white**, which is right for three of the four.
  `--warn-soft` is the documented exception: see SOFT_MIX below.
"""

import colorsys
import re

from upande_crm.theme import color, fonts

# Seed fields on Upande CRM Settings. Owned here because this is what consumes
# them; transfer.py and the API import this rather than repeating the list.
SEED_FIELDS = (
    "theme_accent",
    "theme_accent_dark",
    "theme_accent_soft",
    "theme_ink",
    "theme_ink_muted",
    "theme_canvas",
    "theme_wash",
    "theme_border",
    "theme_border_strong",
    "theme_success",
    "theme_warning",
    "theme_danger",
    "theme_info",
)

# Seeds that pin one derived token family instead of feeding the derivation.
# Blank = worked out from the seeds above, exactly as before they existed.
PIN_FIELDS = ("theme_accent_dark", "theme_accent_soft", "theme_wash", "theme_border", "theme_border_strong")

RADIUS_FIELDS = (
    # (field, tokens it sets)
    ("theme_radius", ("radius", "r-sm")),
    ("theme_radius_card", ("r-card",)),
    ("theme_radius_panel", ("r-panel",)),
)
# A bare CSS length: 0, or a non-negative number with px/rem/em.
RADIUS_RE = re.compile(r"^(0|\d+(\.\d+)?(px|rem|em))$")

# Every theme field on Upande CRM Settings, in form order. The API, the reset
# and the tests all read this one list.
THEME_FIELDS = SEED_FIELDS + (
    "theme_accent_primary",
    "theme_font_sans", "theme_font_sans_name",
    "theme_font_display", "theme_font_display_name",
    "theme_font_mono", "theme_font_mono_name",
    "theme_google_fonts_url",
    "theme_radius", "theme_radius_card", "theme_radius_panel",
    "theme_custom_css",
)

# The shipped values of tokens the editor shows as "worked out for you" and the
# contrast report falls back on when nothing overrides them. Mirrors
# frontend/src/index.css; test_theme checks they agree.
SHIPPED = {
    "text": "#0a0a0a", "text-3": "#8a8780", "bg": "#f4f3ef", "surface": "#ffffff",
    "surface-3": "#efede9", "line": "#e6e3dc", "line-2": "#cdc9bf",
    "gold": "#d9a514", "gold-2": "#a87d0d", "gold-soft": "#f7edcd", "gold-text": "#8a6a10",
    "on-accent": "#000000",
    "good": "#3f8f4f", "good-soft": "#e7f1e9", "warn": "#96650f", "warn-soft": "#f7ecce",
    "bad": "#c4302b", "bad-soft": "#f8e4e2", "info": "#175cd3", "info-soft": "#e0eaff",
}

DEFAULT_CANVAS = (244, 243, 239)

# Accent ramp, fitted: gold #d9a514 -> gold-2 #a87d0d, gold-soft #f7edcd,
# gold-text #8a6a10.
ACCENT_DEEP_MIX = 0.227
ACCENT_SOFT_MIX = 0.785
ACCENT_TEXT_MIX = 0.357
# The gradient's light stop is lightened in HSL rather than mixed toward white:
# mixing desaturates, which turned the shipped #edc23c into a muddy #e0b53c.
ACCENT_LIGHT_LIFT = 0.12

# Surfaces, fitted against #faf9f5 / #efede9 / #e6e3dc / #cdc9bf.
SURFACE_2_MIX = 0.458   # canvas -> white
SURFACE_3_MIX = 0.051   # canvas -> ink-mute
LINE_MIX = 0.144        # canvas -> ink-mute
LINE_2_MIX = 0.384      # canvas -> ink-mute

# One fraction for all four status softs. It reproduces good/bad/info within
# 6/255 total, but NOT --warn-soft: the shipped #f7ecce is within two channels of
# --gold-soft (#f7edcd), i.e. it was hand-matched to the gold accent rather than
# derived from the warning seed. Deriving it gives a slightly greyer #eee6d7.
# That divergence is deliberate and preferred — on a maroon theme a warning fill
# that still tracked gold would be a leftover from a palette no longer in use.
SOFT_MIX = 0.87

# (seed field, base token, soft token)
STATUS_TOKENS = (
    ("theme_success", "good", "good-soft"),
    ("theme_warning", "warn", "warn-soft"),
    ("theme_danger", "bad", "bad-soft"),
    ("theme_info", "info", "info-soft"),
)


def _lighten(rgb, amount):
    """Raise HSL lightness, preserving hue and saturation."""
    r, g, b = (c / 255 for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return tuple(c * 255 for c in colorsys.hls_to_rgb(h, min(1.0, l + amount), s))


def _seed(settings, field):
    return color.parse(settings.get(field))


def get_tokens(settings):
    """seeds -> {token name: css value}. Never raises; a bad seed is skipped."""
    out = {}

    ink = _seed(settings, "theme_ink")
    canvas = _seed(settings, "theme_canvas")
    muted = _seed(settings, "theme_ink_muted")
    accent = _seed(settings, "theme_accent")

    scale = color.ink_scale(ink, muted, canvas or DEFAULT_CANVAS)
    out.update(scale)

    if scale:
        # The shipped CSS aliases the text roles onto the ink scale.
        out["text"] = scale["ink"]
        out["text-2"] = scale["ink-3"]
        out["text-3"] = scale["ink-mute"]
        out["grad-ink"] = f"linear-gradient(135deg, {scale['ink']} 0%, {scale['ink-3']} 100%)"
        out["hover"] = color.rgba(ink, color.HOVER_ALPHA)
        out["hairline"] = color.rgba(ink, color.HAIRLINE_ALPHA)
        # Shadows follow the ink seed, so a maroon-inked theme gets maroon-tinted
        # shadows instead of black ones.
        out["shadow-card"] = (
            f"0 1px 0 {color.rgba(ink, 0.04)}, 0 8px 32px -16px {color.rgba(ink, 0.1)}"
        )
        out["shadow-hover"] = (
            f"0 1px 0 {color.rgba(ink, 0.06)}, 0 24px 48px -24px {color.rgba(ink, 0.18)}"
        )

    if canvas:
        out["bg"] = color.to_hex(canvas)
        out["surface"] = "#ffffff"
        out["surface-2"] = color.to_hex(color.mix(canvas, color.WHITE, SURFACE_2_MIX))
        # Hairlines and low surfaces run toward the muted grey, not ink.
        toward = muted or color.mix(canvas, ink or (10, 10, 10), 0.5)
        out["surface-3"] = color.to_hex(color.mix(canvas, toward, SURFACE_3_MIX))
        out["line"] = color.to_hex(color.mix(canvas, toward, LINE_MIX))
        out["line-2"] = color.to_hex(color.mix(canvas, toward, LINE_2_MIX))

    if accent:
        deep = color.mix(accent, color.BLACK, ACCENT_DEEP_MIX)
        light = _lighten(accent, ACCENT_LIGHT_LIFT)
        soft = color.mix(accent, color.WHITE, ACCENT_SOFT_MIX)
        out["gold"] = color.to_hex(accent)
        out["gold-2"] = color.to_hex(deep)
        out["gold-soft"] = color.to_hex(soft)
        out["gold-text"] = color.to_hex(color.mix(accent, color.BLACK, ACCENT_TEXT_MIX))
        out["selected"] = out["gold-soft"]
        out["grad-gold"] = (
            f"linear-gradient(135deg, {out['gold-2']} 0%, {color.to_hex(light)} 100%)"
        )
        # Text over an accent fill, judged against both ends of the gradient so
        # neither fails. Pure black/white rather than the ink/canvas tones: on a
        # saturated fill those read as washed-out grey, and the pure values also
        # measure better. This is what lets bright gold take ink text and dark
        # maroon take white without anyone maintaining the pairing per client.
        out["on-accent"] = color.to_hex(
            color.best_contrast((deep, accent), (color.BLACK, color.WHITE))
        )

    for field, base, soft_token in STATUS_TOKENS:
        seed = _seed(settings, field)
        if not seed:
            continue
        out[base] = color.to_hex(seed)
        out[soft_token] = color.to_hex(color.mix(seed, color.WHITE, SOFT_MIX))

    out.update(_shadcn_channels(out, ink, canvas, _seed(settings, "theme_danger")))
    _apply_pins(out, settings, accent)
    _apply_fonts(out, settings)
    _apply_radius(out, settings)
    return out


# The seeds that reproduce the shipped palette (test_theme checks this), and the
# shipped values of tokens the seeds do not drive. Together they are the base a
# preview is painted over — see preview_tokens.
SHIPPED_SEEDS = {
    "theme_accent": "#d9a514", "theme_ink": "#0a0a0a", "theme_ink_muted": "#8a8780",
    "theme_canvas": "#f4f3ef", "theme_success": "#3f8f4f", "theme_warning": "#96650f",
    "theme_danger": "#c4302b", "theme_info": "#175cd3",
}
SHIPPED_EXTRA = {
    "f": "'Poppins', system-ui, sans-serif",
    "mono": "'Poppins', system-ui, sans-serif",
    "display": "'Fraunces', Georgia, serif",
    "radius": "12px", "r-sm": "var(--radius)", "r-card": "24px", "r-panel": "24px",
    # index.css resolves these once on :root; a preview must redeclare them so
    # they follow the draft's --r-card, --radius and ink.
    "r-card-in": "max(0px, calc(var(--r-card) - 10px))",
    "r-ctl": "max(0px, calc(var(--radius) - 3px))",
    "nav-active": "var(--grad-ink)", "nav-active-fg": "#ffffff",
}


def preview_tokens(settings):
    """A complete token set for the live preview.

    The preview wrapper sits inside a page that already carries the saved theme,
    so a draft that clears a field produces no token for it and would otherwise
    inherit the saved value — showing something Save will not produce. Painting
    the draft over the full shipped set shows exactly what Save will.
    """
    return {**get_tokens(SHIPPED_SEEDS), **SHIPPED_EXTRA, **get_tokens(settings)}


def _apply_pins(out, settings, accent):
    """Hand-picked colours that override one derived family each."""
    hsl = color.to_hsl_channels
    dark = _seed(settings, "theme_accent_dark")
    if dark:
        out["gold-2"] = out["gold-text"] = color.to_hex(dark)
        light = color.to_hex(_lighten(accent, ACCENT_LIGHT_LIFT)) if accent else "#edc23c"
        out["grad-gold"] = f"linear-gradient(135deg, {out['gold-2']} 0%, {light} 100%)"
    soft = _seed(settings, "theme_accent_soft")
    if soft:
        out["gold-soft"] = out["selected"] = color.to_hex(soft)
    wash = _seed(settings, "theme_wash")
    if wash:
        out["surface-3"] = color.to_hex(wash)
        out["secondary"] = out["muted"] = hsl(wash)
    border = _seed(settings, "theme_border")
    if border:
        out["line"] = color.to_hex(border)
        out["border"] = out["input"] = out["accent"] = hsl(border)
        out["hairline"] = color.rgba(border, 0.6)
    strong = _seed(settings, "theme_border_strong")
    if strong:
        out["line-2"] = color.to_hex(strong)

    # The brand colour as the action colour: main buttons, focus ring, the
    # active menu item. Needs an accent to act on.
    if accent and settings.get("theme_accent_primary") and str(settings.get("theme_accent_primary")) != "0":
        on = out.get("on-accent") or color.to_hex(
            color.best_contrast((accent,), (color.BLACK, color.WHITE)))
        out["primary"] = hsl(accent)
        out["ring"] = hsl(accent)
        out["primary-foreground"] = hsl(color.parse(on))
        out["nav-active"] = color.to_hex(accent)
        out["nav-active-fg"] = on


def _apply_fonts(out, settings):
    resolved = fonts.resolve(settings)
    for role, _choice, _name, token in fonts.ROLES:
        if resolved[role]:
            out[token] = resolved[role]


def _apply_radius(out, settings):
    for field, tokens in RADIUS_FIELDS:
        value = str(settings.get(field) or "").strip()
        if value and RADIUS_RE.match(value):
            for token in tokens:
                out[token] = value


# ---------------------------------------------------------------- contrast
# (key, plain-English label, foreground token, background token)
CONTRAST_PAIRS = (
    ("text_on_bg", "Main text on the page", "text", "bg"),
    ("muted_on_bg", "Muted text on the page", "text-3", "bg"),
    ("text_on_surface", "Main text on cards", "text", "surface"),
    ("on_accent", "Text on brand-coloured buttons", "on-accent", "gold"),
    ("accent_text_on_soft", "Brand text on its pale tint", "gold-text", "gold-soft"),
    ("good_badge", "Success badge", "good", "good-soft"),
    ("warn_badge", "Warning badge", "warn", "warn-soft"),
    ("bad_badge", "Danger badge", "bad", "bad-soft"),
    ("info_badge", "Info badge", "info", "info-soft"),
)


def contrast_report(tokens):
    """WCAG contrast for the pairs a non-designer is most likely to break.

    ok >= 4.5 (readable at any size), warn >= 3 (large text only), bad below.
    Tokens a theme does not set fall back to the shipped palette.
    """
    out = []
    for key, label, fg_t, bg_t in CONTRAST_PAIRS:
        fg = color.parse(tokens.get(fg_t) or SHIPPED[fg_t])
        bg = color.parse(tokens.get(bg_t) or SHIPPED[bg_t])
        if not fg or not bg:
            continue
        ratio = round(color.contrast(fg, bg), 2)
        level = "ok" if ratio >= 4.5 else "warn" if ratio >= 3 else "bad"
        out.append({"key": key, "label": label, "fg": color.to_hex(fg), "bg": color.to_hex(bg),
                    "ratio": ratio, "level": level})
    return out


def _shadcn_channels(tokens, ink, canvas, danger):
    """The shadcn semantic vars, as bare 'H S% L%' channel triples.

    These drive every shadcn primitive — Button variants, Input, Select,
    Textarea, Checkbox. Without them, inputs and focus rings would keep ink-grey
    borders while the rest of the app turned maroon.
    """
    out = {}
    hsl = color.to_hsl_channels

    def px(name):
        value = tokens.get(name)
        return color.parse(value) if value else None

    if ink:
        out["foreground"] = hsl(ink)
        out["primary"] = hsl(ink)
        out["accent-foreground"] = hsl(ink)
        out["card-foreground"] = hsl(ink)
        out["popover-foreground"] = hsl(ink)
        ink_1 = px("ink-1")
        if ink_1:
            out["ring"] = hsl(ink_1)
        ink_3 = px("ink-3")
        if ink_3:
            out["secondary-foreground"] = hsl(ink_3)
        mute = px("ink-mute")
        if mute:
            out["muted-foreground"] = hsl(mute)
    if canvas:
        out["background"] = hsl(canvas)
        out["card"] = "0 0% 100%"
        out["popover"] = "0 0% 100%"
        surface_2 = px("surface-2")
        if surface_2:
            out["primary-foreground"] = hsl(surface_2)
        surface_3 = px("surface-3")
        if surface_3:
            out["secondary"] = hsl(surface_3)
            out["muted"] = hsl(surface_3)
        line = px("line")
        if line:
            out["border"] = hsl(line)
            out["input"] = hsl(line)
            out["accent"] = hsl(line)
    if danger:
        out["destructive"] = hsl(danger)
        out["destructive-foreground"] = "0 0% 100%"
    return out


def get_theme_css(settings):
    """The full <style> body, or '' when nothing is configured.

    Custom CSS goes last, inside the same :root, so it overrides anything the
    derivation produced. The settings controller refuses any `<` in it, so it
    cannot close the <style> element it is rendered into.
    """
    tokens = get_tokens(settings)
    custom = str(settings.get("theme_custom_css") or "").strip()
    if not tokens and not custom:
        return ""
    lines = [f"  --{name}: {value};" for name, value in sorted(tokens.items())]
    if custom and "<" not in custom:
        lines += ["  " + line.strip() for line in custom.splitlines() if line.strip()]
    body = "\n".join(lines)
    return f":root {{\n{body}\n}}"


def get_font_link(settings):
    """The Google Fonts stylesheet URL to <link>, or None."""
    return fonts.resolve(settings)["link"]
