const GOLD = '#d9a514';
const HAIRLINE = 'rgba(217, 165, 20, 0.28)';
const DIM = 'rgba(255, 255, 255, 0.52)';
const FAINT = 'rgba(255, 255, 255, 0.28)';

function compact(n, currency) {
  const v = Number(n) || 0;
  const abs = Math.abs(v);
  const [scaled, suffix] =
    abs >= 1e9 ? [v / 1e9, 'B'] : abs >= 1e6 ? [v / 1e6, 'M'] : abs >= 1e3 ? [v / 1e3, 'K'] : [v, ''];
  const body = `${scaled.toFixed(suffix ? 1 : 0)}${suffix}`;
  return currency ? `${currency} ${body}` : body;
}

/**
 * What the map cannot show.
 *
 * Records are tagged against group territories (Middle East, Europe, Africa) as
 * freely as against countries — on this site that is a large share of all
 * revenue. Those rows belong to no polygon, and splitting them across member
 * countries would be inventing data, so they are accounted for here instead.
 *
 * This panel is not optional decoration. Without it the map is a confident
 * picture that quietly omits a third of the business.
 */
export default function RegionalLedger({ groups, totals, currency, metric, metricLabel }) {
  if (!groups?.length) return null;

  const mapped = totals?.mapped?.[metric] || 0;
  const regional = totals?.regional?.[metric] || 0;
  const all = mapped + regional;
  const pct = all > 0 ? Math.round((regional / all) * 100) : 0;

  return (
    <div
      className="shrink-0 px-5 py-4"
      style={{ borderTop: `1px solid ${HAIRLINE}`, background: 'rgba(10, 10, 10, 0.96)' }}
    >
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[9px] uppercase tracking-[0.28em]" style={{ color: FAINT }}>
          Not on the map
        </span>
        <span className="font-mono text-[10px] tabular-nums" style={{ color: GOLD }}>
          {pct}% of {metricLabel.toLowerCase()}
        </span>
      </div>

      <p className="mt-2 text-[11px] leading-relaxed" style={{ color: DIM }}>
        Tagged to a region, not a country — no polygon can hold it.
      </p>

      <div className="mt-2.5">
        {groups.map((g) => (
          <div key={g.territory} className="flex items-baseline justify-between gap-3 py-[3px]">
            <span className="truncate text-[11px]" style={{ color: 'rgba(255,255,255,0.78)' }}>
              {g.territory}
            </span>
            <span className="shrink-0 font-mono text-[11px] tabular-nums" style={{ color: DIM }}>
              {compact(g[metric], metric === 'revenue' || metric === 'opp_value' ? currency : '')}
            </span>
          </div>
        ))}
      </div>

      <div
        className="mt-2.5 flex items-baseline justify-between gap-3 pt-2"
        style={{ borderTop: '1px solid rgba(255,255,255,0.08)' }}
      >
        <span className="text-[10px] uppercase tracking-[0.18em]" style={{ color: DIM }}>
          On map / total
        </span>
        <span className="font-mono text-[11px] tabular-nums" style={{ color: '#f4f3ef' }}>
          {compact(mapped, metric === 'revenue' || metric === 'opp_value' ? currency : '')}
          <span style={{ color: FAINT }}> / </span>
          {compact(all, metric === 'revenue' || metric === 'opp_value' ? currency : '')}
        </span>
      </div>
    </div>
  );
}
