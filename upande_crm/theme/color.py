"""Pure colour maths for the CRM theme.

Imports nothing from Frappe, so every derivation here is testable as plain
functions.

**On the duplication with `upande_webstore/theme/color.py`:** this is a
deliberate copy, not an oversight. That module is dependency-free and would
import cleanly, but importing it would make `upande_crm` require an unrelated app
to be installed. These are a hundred lines of stable arithmetic; a hard
cross-app dependency for them is the worse trade. `to_hsl_channels` and
`accent_scale`'s CRM token names are new here.

`mix()` returns unrounded floats and only `to_hex()` rounds, so chained mixes do
not accumulate rounding error.
"""

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# Fractions along ink -> ink-mute at which each ink token sits, fitted to the
# shipped scale in frontend/src/index.css. INK_MUTE is where the muted seed
# itself sits on the ink -> canvas ramp.
INK_STEPS = (0.000, 0.068, 0.137, 0.205, 0.342)  # ink, ink-1 .. ink-4
INK_MUTE = 0.547
INK_FAINT = 0.744

# Alphas the shipped CSS used as literal rgba(10, 10, 10, N).
HOVER_ALPHA = 0.04
HAIRLINE_ALPHA = 0.06


def parse(value):
    """'#rrggbb' -> (r, g, b); anything else -> None. Shorthand is rejected.

    Returning None rather than raising is what lets a blank or malformed seed
    contribute no token instead of taking the page down.
    """
    if not isinstance(value, str):
        return None
    value = value.strip()
    if len(value) != 7 or not value.startswith("#"):
        return None
    try:
        return tuple(int(value[i : i + 2], 16) for i in (1, 3, 5))
    except ValueError:
        return None


def to_hex(rgb):
    """Round and clamp to a '#rrggbb' string."""
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c))) for c in rgb)


def mix(rgb, target, amount):
    """Linear blend toward target. amount 0 -> rgb, 1 -> target. Unrounded."""
    return tuple(c + (t - c) * amount for c, t in zip(rgb, target))


def rgba(rgb, alpha):
    r, g, b = (round(c) for c in rgb)
    return f"rgba({r}, {g}, {b}, {alpha})"


def relative_luminance(rgb):
    """WCAG 2.1 relative luminance."""
    channels = []
    for value in rgb:
        c = max(0.0, min(1.0, value / 255))
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """WCAG contrast ratio between two colours, 1.0 - 21.0."""
    la, lb = relative_luminance(a), relative_luminance(b)
    high, low = max(la, lb), min(la, lb)
    return (high + 0.05) / (low + 0.05)


def best_contrast(backgrounds, candidates):
    """The candidate that reads most legibly across ALL of `backgrounds`.

    Judged on the worst background rather than an average, because text over a
    gradient has to stay legible at both ends — picking against the midpoint
    alone lets one end fail. This is what allows a bright gold accent to take ink
    text and a dark maroon one white text with nobody maintaining the pairing per
    client.
    """
    return max(
        candidates,
        key=lambda candidate: min(contrast(bg, candidate) for bg in backgrounds),
    )


def to_hsl_channels(rgb):
    """(r, g, b) -> 'H S% L%', the channel triple shadcn's CSS vars expect.

    shadcn tokens are stored without the hsl() wrapper so they can be composed
    with an alpha (`hsl(var(--ring) / 0.5)`), which is why this returns bare
    channels rather than a colour string.
    """
    r, g, b = (c / 255 for c in rgb)
    high, low = max(r, g, b), min(r, g, b)
    lightness = (high + low) / 2
    delta = high - low

    if delta == 0:
        hue = saturation = 0.0
    else:
        saturation = delta / (2 - high - low if lightness > 0.5 else high + low)
        if high == r:
            hue = ((g - b) / delta) % 6
        elif high == g:
            hue = (b - r) / delta + 2
        else:
            hue = (r - g) / delta + 4
        hue *= 60

    return f"{round(hue)} {round(saturation * 100)}% {round(lightness * 100)}%"


def ink_scale(ink, muted, canvas):
    """The seven ink tokens.

    Two-segment interpolation: `muted` anchors position INK_MUTE so the
    temperature of the most-visible grey is set directly rather than falling out
    of the arithmetic. Without a muted seed the segments collapse algebraically
    to the single ink -> canvas ramp.
    """
    if not ink:
        return {}
    if muted is None:
        muted = mix(ink, canvas, INK_MUTE)
    scale = {}
    for name, step in zip(("ink", "ink-1", "ink-2", "ink-3", "ink-4"), INK_STEPS):
        scale[name] = to_hex(mix(ink, muted, step / INK_MUTE))
    scale["ink-mute"] = to_hex(muted)
    scale["ink-faint"] = to_hex(mix(muted, canvas, (INK_FAINT - INK_MUTE) / (1 - INK_MUTE)))
    return scale
