# CRM Theming — Design

**Date:** 2026-07-29
**Status:** Approved design
**Scope:** Spec 5. Siblings: Events & Tasks (1, delivered), Sales analytics (2, delivered),
WhatsApp (3, delivered), CRM Settings (4, delivered). Calls section (6) is specified separately
and comes after this.

## Problem

The CRM's look is compiled in. Its design tokens are literal hex values in a `:root` block in
`frontend/src/index.css`, so changing the accent means editing CSS and running
`npm run build` — a developer task, on a per-deploy basis, for what is really a per-client
setting. Upande runs this CRM for several companies from one codebase (Kaitet Group, Karen
Roses, Lokitela Orchards, Westwood Dairies are all Companies on this site alone), and every one
of them gets Upande gold.

`upande_webstore` already solved this problem for the storefront: seed colours live on a
settings doctype, pure colour maths derives the full token set, a `<style>` block overrides the
compiled CSS at render time, and shipped presets are JSON files in the app. This spec ports
that approach to the CRM and adds a **Karen Roses maroon** preset.

## Goals

1. Theme seeds on `Upande CRM Settings`, edited from a Theme tab in the Settings section.
2. Shipped presets as JSON — `upande` (the current gold/ink look) and `karen_roses` (maroon).
3. **A theme change requires no frontend rebuild.** Every Tailwind colour in this app resolves a
   CSS variable at runtime, so overriding `:root` is sufficient.
4. **An unconfigured site renders exactly as it does today** — byte-identical, no `<style>` block.

### Non-goals

Per-user themes (this is one look per site), dark mode, font and radius configuration, a
custom-CSS escape hatch, and theme export/import between sites. The webstore has the last three;
they can be added later if a real need appears. Eight seeds cover the whole palette.

## Approach, and the two calls that shape it

**Derivation runs in Python at page render, not in the SPA.** The token `<style>` block is part
of the HTML response. Deriving in the browser from the settings API would flash the compiled
palette on every load and could not theme anything before JS boots.

**The colour maths is copied into this app, not imported from `upande_webstore`.**
`upande_webstore/theme/color.py` imports nothing from Frappe, so importing it would work on this
site — but it would make `upande_crm` depend on an unrelated app being installed. The ~100 lines
of pure maths are copied, with that reason recorded in the docstring. This is deliberate
duplication of a stable, dependency-free, well-tested function set.

## Modules

```
upande_crm/theme/__init__.py                 get_theme_css(settings=None) — one entry point
upande_crm/theme/color.py                    parse, to_hex, mix, rgba, contrast, best_contrast,
                                             ink_scale, to_hsl_channels
upande_crm/theme/tokens.py                   seeds -> the CRM token set; SEED_FIELDS lives here
upande_crm/theme/transfer.py                 list_presets, apply_preset, reset
upande_crm/theme/presets/upande.json         the shipped gold/ink look
upande_crm/theme/presets/karen_roses.json    maroon
```

`tokens.py` owns `SEED_FIELDS`; `transfer.py` and the API import it rather than repeating the
list. Same ownership rule the webstore uses for `THEME_FIELDS`.

## Seeds

Eight colours plus a bookkeeping field, added to `Upande CRM Settings` in a new Theme section:

| Field | Seeds |
|---|---|
| `theme_accent` | `--gold`, and everything derived from it |
| `theme_ink` | the ink scale, text roles, hairline, hover, shadows, `--grad-ink` |
| `theme_ink_muted` | anchors the middle of the ink scale, so the most-visible grey's temperature is set directly rather than falling out of arithmetic |
| `theme_canvas` | `--bg` and the surface lifts |
| `theme_success` | `--good`, `--good-soft` |
| `theme_warning` | `--warn`, `--warn-soft` |
| `theme_danger` | `--bad`, `--bad-soft` |
| `theme_info` | `--info`, `--info-soft` |
| `theme_preset` | Read-only Data: which preset was last applied, so the UI can show it as selected. Cleared when a seed is edited by hand. |

Blank means "not configured" — that seed contributes no tokens. All eight blank means no
`<style>` block at all.

`--bio` (#228883, one chart series) is left out of the seed set. It is a fixed brand colour, not
part of the semantic scale, and deriving it from `info` would change existing charts.

## Derived tokens

**Ink** — `--ink`, `--ink-1` … `--ink-4`, `--ink-mute`, `--ink-faint`, plus `--text`, `--text-2`,
`--text-3` which are aliases of `ink`, `ink-3`, `ink-mute` in the shipped CSS. Two-segment
interpolation anchored on `theme_ink_muted`, as in the webstore.

**Accent** — `--gold` (accent), `--gold-2` (deep, the hover/active tone), `--gold-soft`,
`--gold-text` (the accent darkened far enough to read as text on `--gold-soft`), `--selected`
(= `--gold-soft`; the shipped values are the same hex), and `--grad-gold` running deep → light.

**Surfaces** — `--surface` stays `#ffffff`. `--surface-2` and `--surface-3` are lifts and drops
from the canvas; `--line` and `--line-2` are the canvas mixed toward ink. `--hover` and
`--hairline` are the ink seed at the alphas the CSS hardcodes (0.04, 0.06), and both shadow
strings are rebuilt from the ink seed, so a maroon-inked theme gets maroon-tinted shadows
instead of black ones.

**Status** — four pairs: base, and a soft fill at ~12% toward white.

**shadcn HSL channels** — `--background`, `--foreground`, `--primary`,
`--primary-foreground`, `--secondary`, `--secondary-foreground`, `--muted`,
`--muted-foreground`, `--accent`, `--accent-foreground`, `--border`, `--input`, `--ring`,
`--destructive` are emitted as `H S% L%` channel triples, derived from the same seeds. These
drive every shadcn primitive (Button variants, Input, Select, Textarea, Checkbox). Without them
inputs and selects would keep ink-grey borders and focus rings while everything around them
turned maroon.

### `--on-accent`, and the component change it forces

New token: pure black or pure white, whichever reads better across **both** ends of the accent
gradient (`--gold-2` → `--gold`), judged on the worse end.

This matters because of a decision already recorded in the CRM's design notes: accent-filled
buttons hardcode `text-ink`, since white on bright gold reads badly. Ink text on dark maroon is
worse — it is close to invisible. So the accent-filled controls move from `text-ink` to
`text-[var(--on-accent)]`:

- `Sidebar` Compose button
- `SaveBar` save button (Settings)
- `TaskDialog` / `EventDialog` submit buttons
- `ComposeDialog` send button
- `WaComposer` send button
- `PageTools` "Apply range" (ink-filled, verify)

`--on-accent` defaults to `#0a0a0a` when no accent is configured, so today's gold buttons keep
ink text unchanged.

## Wiring

`www/customer_relationship_management.py` gains `context.theme_css = get_theme_css()`.

`frontend/scripts/build-html.mjs` injects, immediately before `</head>` and therefore after the
inlined bundle CSS:

```jinja
{% if theme_css %}<style id="crm-theme">{{ theme_css }}</style>{% endif %}
```

Same specificity as the bundle's `:root`, later in the document, so it wins. The injection lives
in the build script rather than being hand-edited into the generated HTML, so it survives every
rebuild.

### API

Added to `upande_crm/api/settings.py`, reusing its existing role gate:

| Endpoint | Returns |
|---|---|
| `crm_theme()` | `{seeds, tokens, presets: [{name, label, swatches}], applied}` |
| `crm_theme_save(seeds)` | `{seeds, tokens}` — validates hex, throws on anything else |
| `crm_theme_apply_preset(name)` | `{seeds, tokens, applied}` |
| `crm_theme_reset()` | applies the `upande` preset |

Every write returns the derived token map so the Theme tab can write it onto
`document.documentElement.style` and reskin the running app immediately — no reload. Later page
loads get the same tokens from the server-rendered `<style>` block.

Preset names are matched against `^[a-z0-9_]+$` before touching the filesystem, so no path can
escape the preset directory.

## Frontend

New tab `sections/Settings/Theme.jsx`, sixth in the Settings tab strip (before Integrations):

- **Preset cards** — one per shipped preset, each showing accent/ink/canvas swatches, the
  applied one marked. Plus "Reset to Upande gold".
- **Eight colour rows** — native `<input type="color">` beside a hex text field, so a brand hex
  can be pasted rather than eyedropped.
- **Live preview strip** — a KPI tile, a filled button, a badge and a nav item rendered with the
  current tokens, so the effect is visible without hunting through the app.
- Read-only for anyone outside the settings write roles, exactly as the other tabs behave.

## Presets

`upande.json` records today's shipped values, which makes "reset" meaningful and gives the
reproduction test its fixture:

```json
{"schema": 1, "label": "Upande gold", "seeds": {
  "theme_accent": "#d9a514", "theme_ink": "#0a0a0a", "theme_ink_muted": "#8a8780",
  "theme_canvas": "#f4f3ef", "theme_success": "#3f8f4f", "theme_warning": "#96650f",
  "theme_danger": "#c4302b", "theme_info": "#175cd3"}}
```

`karen_roses.json` is maroon on a warmer cream. **The exact brand hex is a guess** —
`#8c1d2e` is a starting point to be replaced with the real value when it is to hand. Its
`--on-accent` resolves to white, which is what makes the button change above load-bearing.

## Testing

`upande_crm/tests/test_theme.py`. The first test is the one that matters:

- **Seeding the shipped values reproduces the shipped palette.** Every hex in `index.css`'s
  `:root` today is asserted against the derived token of the same name, with any divergence
  listed explicitly in the test rather than tolerated silently. This is what stops theming from
  quietly restyling the CRM.
- `--on-accent` clears 4.5:1 against both `--gold` and `--gold-2`, for the gold preset and the
  maroon one.
- `parse` rejects shorthand, non-strings and junk; a bad seed contributes no token instead of
  raising.
- No seeds → `get_theme_css()` returns `""` → the template emits no `<style>`.
- `to_hsl_channels` round-trips known colours (`#0a0a0a` → `0 0% 4%`, within rounding).
- `list_presets` finds both shipped files; `apply_preset` writes the seeds, is idempotent, and
  refuses `../etc/passwd`, `a/b` and `a.b`.
- `karen_roses` produces a maroon accent, a legible `on-accent`, and a complete token set.
- `crm_theme_save` throws for a malformed hex and for a Sales User.
- Existing suites still pass, and `crm_settings()` still returns every `DEFAULTS` key.

## Verification

`bench --site kaitet.local run-tests --app upande_crm`, `cd frontend && npm run build`, then in
the browser: Settings → Theme → apply Karen Roses. The whole app should turn maroon without a
reload, accent-filled buttons should stay legible, and a page refresh should come back maroon
from the server-rendered block. Reset returns it to gold.
