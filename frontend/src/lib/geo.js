// Projection, zoom-to-feature maths and choropleth bins for the territory map.
//
// Rendering is plain SVG paths from d3-geo. d3-zoom is deliberately not a
// dependency: the only zoom this map performs is "frame this one country", which
// is a transform computed from the feature's bounds and animated by CSS. Adding
// a pan/zoom behaviour would mean reconciling its internal transform state with
// the pinned-country state, for no interaction anyone asked for.

import { geoNaturalEarth1, geoPath } from 'd3-geo';

// The viewBox every projection below is fitted to. Fixed rather than measured,
// so the projection is computed once instead of on every container resize; the
// SVG scales itself to the element via preserveAspectRatio.
export const VIEW = { w: 1000, h: 500 };

// Natural Earth I: compromise projection, no polar distortion of the kind that
// makes Mercator's Greenland dwarf Africa. Territory data here is mostly
// equatorial and mid-latitude, so an area-honest projection matters.
export function makeProjection(land) {
  const projection = geoNaturalEarth1();
  projection.fitExtent(
    [
      [8, 8],
      [VIEW.w - 8, VIEW.h - 8],
    ],
    land
  );
  return projection;
}

export const makePath = (projection) => geoPath(projection);

/** Screen-space [x, y] for a [lon, lat] pair, or null if it does not project. */
export function project(projection, lonLat) {
  const p = projection(lonLat);
  return p && Number.isFinite(p[0]) && Number.isFinite(p[1]) ? p : null;
}

/**
 * Transform that frames `feature` in the viewport.
 *
 * Returned as scale/translate rather than an SVG string so the caller can
 * animate it and read the scale back — stroke widths are divided by it, or
 * borders would fatten as you zoom in.
 */
export function zoomToFeature(path, feature, { padding = 2.4, max = 12 } = {}) {
  const [[x0, y0], [x1, y1]] = path.bounds(feature);
  const w = Math.max(x1 - x0, 1e-6);
  const h = Math.max(y1 - y0, 1e-6);
  const scale = Math.min(max, Math.max(1, Math.min(VIEW.w / (w * padding), VIEW.h / (h * padding))));
  const cx = (x0 + x1) / 2;
  const cy = (y0 + y1) / 2;
  return { scale, x: VIEW.w / 2 - scale * cx, y: VIEW.h / 2 - scale * cy };
}

/** Transform that frames a single point — micro-states have no usable bounds. */
export function zoomToPoint([px, py], scale = 6) {
  return { scale, x: VIEW.w / 2 - scale * px, y: VIEW.h / 2 - scale * py };
}

export const IDENTITY = { scale: 1, x: 0, y: 0 };

export const toTransform = (t) => `translate(${t.x} ${t.y}) scale(${t.scale})`;

/**
 * Thresholds that split the non-zero values across `steps` shades.
 *
 * Quantile, not linear: one territory holds 234M here while the median holds a
 * few thousand, so linear bins would paint all but two countries identically.
 * Zeros are excluded before ranking — "no activity" is its own visual state,
 * not the bottom bin.
 *
 * Ranking runs over the **distinct** values, not the raw list. Count metrics are
 * small integers with heavy ties (41 territories hold one or two leads), and
 * quantiles over the raw list put every tied value above the same thresholds:
 * measured on this data, leads used only 3 of 5 shades and never the lightest
 * two, so the map glowed uniformly bright. Ranking the distinct values spends
 * the whole ramp on the range that actually exists.
 */
export function quantileBins(values, steps = 5) {
  const distinct = [...new Set(values.filter((v) => v > 0))].sort((a, b) => a - b);
  if (distinct.length < 2) return [];
  if (distinct.length <= steps) return distinct.slice(1);
  const at = (q) => distinct[Math.min(distinct.length - 1, Math.floor(q * distinct.length))];
  return [...new Set(Array.from({ length: steps - 1 }, (_, i) => at((i + 1) / steps)))];
}

/** Bin index for `value`, or -1 when there is nothing to shade. */
export function binOf(value, bins) {
  if (!(value > 0)) return -1;
  let i = 0;
  while (i < bins.length && value >= bins[i]) i += 1;
  return i;
}
