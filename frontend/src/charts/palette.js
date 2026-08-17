// Chart palette — UFD-modern. Marks lead with ink (#2a2a26, the reference's base
// fill), with gold + green/amber/red severity + bio teal as categorical accents.
export const PAL = [
  '#2a2a26', // ink (base mark)
  '#d9a514', // gold
  '#228883', // bio teal
  '#c4302b', // severity high (red)
  '#d9962e', // severity moderate (amber)
  '#3f8f4f', // severity low (green)
  '#8a8780', // ink mute
  '#a87d0d', // gold deep
];
// Track-record series identities — a *separate* ramp from PAL, for three reasons
// the validator and the page both insist on:
//
//  1. PAL's lead colour is ink (#2a2a26), which reads as grey rather than as a
//     hue (OKLab chroma 0.007) and sits below the readable lightness band. That
//     is right for a single bar fill and wrong for one line among six.
//  2. PAL slots 3–5 *are* the severity colours. The movers band directly beside
//     this chart spends red on decline and green on gain, so a red "Giselle"
//     line would collide with the one meaning the page has already assigned.
//  3. Six lines need six hues that survive colour-vision deficiency.
//
// Checked with the dataviz validator against the cream chart surface: lightness
// band, chroma floor, adjacent-pair CVD separation (worst deutan ΔE 13.3, tritan
// 12.2) and normal-vision floor (19.3) all pass. Gold sits at 2.72:1 against the
// surface, which the validator flags as needing relief — hence the legend's
// always-on totals and the direct end-labels on the chart. Assign in fixed order
// and never cycle: SERIES_LIMIT on the server is 6, so a seventh never appears.
export const SERIES = [
  '#3268c4', // azure
  '#c69210', // gold deep
  '#03958c', // teal
  '#b5501f', // rust
  '#8d4fa0', // plum
  '#5f8d33', // moss
];
export const BAR_FILL = '#2a2a26';
export const GRID = '#e6e3dc';
// Funnel: ink → gold highlight ramp.
export const FUNNEL_COLORS = ['#2a2a26', '#5a5a52', '#a87d0d', '#d9a514', '#edc23c'];
export const ORDER_COLOR = '#2a2a26'; // ink area
export const REVENUE_COLOR = '#d9a514'; // gold line
// Area gradient base (ink), matching the reference --grad-chart.
export const AREA_INK = '#0a0a0a';
