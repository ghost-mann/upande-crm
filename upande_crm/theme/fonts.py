"""Font family resolution for the CRM theme.

Ported from `upande_webstore/theme/fonts.py`. Bundled families are self-hosted
woff2 (`public/fonts/`, declared in `public/css/fonts.css`), so they work with no
internet connection. Anything else comes from a Google Fonts stylesheet whose
host is checked, so this field cannot put an arbitrary remote origin into every
page's <head>.
"""

import re
from urllib.parse import urlparse

ALLOWED_FONT_HOST = "fonts.googleapis.com"
CUSTOM = "Custom"

# Offered per role. The shipped look is Poppins body, Fraunces headings and
# Poppins figures, so Poppins stays available for numbers too.
BUNDLED = {
    "sans": ["Poppins", "Inter", "IBM Plex Sans", "Space Grotesk"],
    "display": ["Fraunces", "Poppins", "Inter", "Space Grotesk"],
    "mono": ["IBM Plex Mono", "Poppins", "Inter"],
}

FALLBACKS = {
    "sans": 'system-ui, -apple-system, "Segoe UI", sans-serif',
    "display": "Georgia, serif",
    "mono": "ui-monospace, monospace",
}

# (role, choice field, custom-name field, CSS token)
ROLES = (
    ("sans", "theme_font_sans", "theme_font_sans_name", "f"),
    ("display", "theme_font_display", "theme_font_display_name", "display"),
    ("mono", "theme_font_mono", "theme_font_mono_name", "mono"),
)

# A family name goes inside a CSS string: letters, digits, spaces and hyphens
# only, so it can never close the quote.
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{0,60}$")


def options():
    return {role: [""] + BUNDLED[role] + [CUSTOM] for role in BUNDLED}


# The URL is written into <link href="…"> on every CRM page. Only the characters
# a Google Fonts stylesheet URL actually uses are allowed, so nothing in it can
# close the attribute or the tag: no quotes, angle brackets, spaces or backslashes.
URL_CHARS_RE = re.compile(r"^[A-Za-z0-9:/?&=+,;@.%_~\-]+$")
ALLOWED_PATHS = ("/css", "/css2")


def is_allowed_url(url):
    """True only for an https fonts.googleapis.com stylesheet URL with no
    character that could break out of an HTML attribute."""
    if not isinstance(url, str) or not url.strip():
        return False
    url = url.strip()
    if not URL_CHARS_RE.match(url):
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return (parsed.scheme == "https" and parsed.netloc == ALLOWED_FONT_HOST
            and parsed.path in ALLOWED_PATHS)


def _family(role, choice, custom_name):
    if not choice:
        return None
    name = custom_name if choice == CUSTOM else choice
    if choice != CUSTOM and choice not in BUNDLED[role]:
        return None
    if not name or not NAME_RE.match(str(name).strip()):
        return None
    return f'"{str(name).strip()}", {FALLBACKS[role]}'


def resolve(settings):
    """-> {sans, display, mono, link}; each None when unconfigured."""
    out = {role: _family(role, settings.get(choice), settings.get(name)) for role, choice, name, _t in ROLES}
    url = settings.get("theme_google_fonts_url")
    out["link"] = url.strip() if is_allowed_url(url) else None
    return out
