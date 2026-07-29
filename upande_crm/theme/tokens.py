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

from upande_crm.theme import color

# Seed fields on Upande CRM Settings. Owned here because this is what consumes
# them; transfer.py and the API import this rather than repeating the list.
SEED_FIELDS = (
    "theme_accent",
    "theme_ink",
    "theme_ink_muted",
    "theme_canvas",
    "theme_success",
    "theme_warning",
    "theme_danger",
    "theme_info",
)

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
    """The full <style> body, or '' when nothing is configured."""
    tokens = get_tokens(settings)
    if not tokens:
        return ""
    body = "\n".join(f"  --{name}: {value};" for name, value in sorted(tokens.items()))
    return f":root {{\n{body}\n}}"
