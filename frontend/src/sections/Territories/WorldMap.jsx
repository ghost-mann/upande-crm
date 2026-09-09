import { useMemo, useRef } from 'react';
import { feature } from 'topojson-client';
import topo from '../../assets/countries-110m.json';
import { ISO_BY_TERRITORY, MICRO_CENTROIDS, TERRITORY_BY_ISO } from '../../lib/territory_iso';
import {
  IDENTITY,
  VIEW,
  binOf,
  makePath,
  makeProjection,
  project,
  quantileBins,
  toTransform,
  zoomToFeature,
  zoomToPoint,
} from '../../lib/geo';

// Choropleth ramp: the ink surface up through gold. Written as explicit rgba
// rather than Tailwind opacity utilities — `bg-x/55` renders invisible against
// this app's CSS-var tokens, so every translucent fill on this map is inline.
const RAMP = [
  'rgba(217, 165, 20, 0.22)',
  'rgba(217, 165, 20, 0.38)',
  'rgba(217, 165, 20, 0.56)',
  'rgba(217, 165, 20, 0.76)',
  'rgba(217, 165, 20, 0.96)',
];
const EMPTY_FILL = 'rgba(255, 255, 255, 0.045)';
const BORDER = 'rgba(255, 255, 255, 0.14)';
const GOLD = '#d9a514';

// The atlas is static, so parse it once at module scope rather than per mount.
//
// Antarctica (ISO 010) is dropped. It is never a sales territory, and because
// Natural Earth carries it down to the pole it dominates the land bounds the
// projection is fitted to — leaving it in shrinks every populated continent and
// spends the bottom fifth of the canvas on an ice shelf nobody can click.
const ANTARCTICA = '010';
const ALL = feature(topo, topo.objects.countries);
const COUNTRIES = {
  type: 'FeatureCollection',
  features: ALL.features.filter((f) => String(f.id).padStart(3, '0') !== ANTARCTICA),
};

export default function WorldMap({
  rows,
  metric,
  hovered,
  pinned,
  onHover,
  onPick,
  onClearPin,
}) {
  const svgRef = useRef(null);

  const { projection, path } = useMemo(() => {
    const p = makeProjection(COUNTRIES);
    return { projection: p, path: makePath(p) };
  }, []);

  // territory name -> row, for painting a feature from its ISO id.
  const byTerritory = useMemo(() => {
    const m = new Map();
    rows.forEach((r) => m.set(r.territory, r));
    return m;
  }, [rows]);

  const bins = useMemo(
    () => quantileBins(rows.map((r) => r[metric] || 0)),
    [rows, metric]
  );

  const valueOf = (name) => (name && byTerritory.get(name)?.[metric]) || 0;

  const fillFor = (name) => {
    const i = binOf(valueOf(name), bins);
    return i < 0 ? EMPTY_FILL : RAMP[Math.min(i, RAMP.length - 1)];
  };

  // Micro-states carry no polygon at 110m, so they are drawn as centroid dots.
  // Only those with data are rendered: 30 permanent dots over empty ocean would
  // read as noise, and the ledger already accounts for the silent ones.
  const dots = useMemo(
    () =>
      Object.entries(MICRO_CENTROIDS)
        .map(([name, lonLat]) => ({ name, xy: project(projection, lonLat), value: valueOf(name) }))
        .filter((d) => d.xy && d.value > 0),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [projection, byTerritory, metric, bins]
  );

  const active = pinned || hovered;

  const transform = useMemo(() => {
    if (!pinned) return IDENTITY;
    const iso = ISO_BY_TERRITORY[pinned];
    const f = iso && COUNTRIES.features.find((x) => String(x.id).padStart(3, '0') === iso);
    if (f) return zoomToFeature(path, f);
    const lonLat = MICRO_CENTROIDS[pinned];
    const xy = lonLat && project(projection, lonLat);
    return xy ? zoomToPoint(xy) : IDENTITY;
  }, [pinned, path, projection]);

  // Strokes are drawn in screen space, so every width is divided by the zoom —
  // otherwise borders thicken into slabs as you zoom into a country.
  const k = transform.scale;

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${VIEW.w} ${VIEW.h}`}
      preserveAspectRatio="xMidYMid meet"
      className="h-full w-full select-none"
      role="img"
      aria-label="World map of CRM activity by territory"
      onMouseLeave={() => onHover(null)}
    >
      <defs>
        <radialGradient id="tm-vignette" cx="50%" cy="50%" r="42%">
          <stop offset="0%" stopColor="rgba(255,255,255,0.05)" />
          <stop offset="100%" stopColor="rgba(0,0,0,0.45)" />
        </radialGradient>
      </defs>

      {/* Ocean, and the click target that releases a pin. Oversized on purpose:
          the viewBox letterboxes inside a taller container, and a rect cut to
          VIEW would leave a visible seam where the vignette stops. */}
      <rect
        x={-VIEW.w}
        y={-VIEW.h}
        width={VIEW.w * 3}
        height={VIEW.h * 3}
        fill="#0a0a0a"
        onClick={onClearPin}
      />

      <g
        transform={toTransform(transform)}
        style={{ transition: 'transform 620ms cubic-bezier(0.22, 0.61, 0.36, 1)' }}
      >
        {COUNTRIES.features.map((f, i) => {
          // A handful of atlas features carry no id at all (Kosovo, N. Cyprus,
          // Somaliland — disputed, so Natural Earth assigns no ISO code). They
          // match no territory and are drawn as inert background, but they still
          // need distinct React keys, hence the index fallback.
          const iso = f.id == null ? null : String(f.id).padStart(3, '0');
          const name = iso ? TERRITORY_BY_ISO[iso] : undefined;
          const isActive = name && name === active;
          return (
            <path
              key={iso ?? `x${i}`}
              data-territory={name || undefined}
              d={path(f)}
              fill={fillFor(name)}
              stroke={isActive ? GOLD : BORDER}
              strokeWidth={(isActive ? 1.4 : 0.4) / k}
              vectorEffect="non-scaling-stroke"
              style={{ cursor: name ? 'pointer' : 'default', transition: 'fill 180ms linear' }}
              onMouseEnter={() => onHover(name || null)}
              onClick={(e) => {
                e.stopPropagation();
                if (name) onPick(name);
              }}
            />
          );
        })}

        {dots.map((d) => {
          const isActive = d.name === active;
          return (
            <g key={d.name} data-territory={d.name} transform={`translate(${d.xy[0]} ${d.xy[1]})`}>
              <circle
                r={(isActive ? 6 : 4) / k}
                fill={GOLD}
                fillOpacity={isActive ? 1 : 0.85}
                stroke="#0a0a0a"
                strokeWidth={1 / k}
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => onHover(d.name)}
                onClick={(e) => {
                  e.stopPropagation();
                  onPick(d.name);
                }}
              />
              {/* A wider invisible target: a 4px dot is hard to hit precisely. */}
              <circle
                r={10 / k}
                fill="transparent"
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => onHover(d.name)}
                onClick={(e) => {
                  e.stopPropagation();
                  onPick(d.name);
                }}
              />
            </g>
          );
        })}
      </g>

      <rect
        x={-VIEW.w}
        y={-VIEW.h}
        width={VIEW.w * 3}
        height={VIEW.h * 3}
        fill="url(#tm-vignette)"
        pointerEvents="none"
      />
    </svg>
  );
}

export { RAMP };
