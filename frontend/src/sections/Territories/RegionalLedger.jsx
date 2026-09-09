import { useEffect, useState } from 'react';
import { BODY, DIM, FAINT, GOLD, HAIRLINE, TEXT, compact } from './atoms';

const MONEY = new Set(['revenue', 'opp_value', 'claim_cost']);

/**
 * What the map cannot show.
 *
 * Two separate holes, kept separate because they have different causes:
 *
 *  - **Regional.** Records tagged to a group Territory (Middle East, Europe,
 *    Africa) rather than a country. Real, attributed data that no polygon can
 *    hold — on this site nearly half the revenue.
 *  - **Unattributed.** Rows that reached no territory at all: claims naming a
 *    company that was never created as a Customer, consignees in a country with
 *    no Territory record.
 *
 * This panel is not decoration. Without it the map is a confident picture that
 * quietly omits a large part of the business.
 */
export default function RegionalLedger({ groups, totals, orphaned, currency, metric, metricLabel, collapsed }) {
  // Collapses itself when a territory is pinned, because the detail above it
  // then has a lot to say and this slab was taking half the panel. The headline
  // percentage stays visible either way — the whole point is that the number is
  // never out of sight.
  const [open, setOpen] = useState(!collapsed);
  useEffect(() => setOpen(!collapsed), [collapsed]);

  const hasGroups = groups?.length > 0;
  const orphanCount =
    metric === 'claims' || metric === 'claim_cost'
      ? orphaned?.claims
      : metric === 'consignees'
        ? orphaned?.consignees
        : 0;
  if (!hasGroups && !orphanCount) return null;

  const money = MONEY.has(metric) ? currency : '';
  const mapped = totals?.mapped?.[metric] || 0;
  const regional = totals?.regional?.[metric] || 0;
  const all = mapped + regional;
  const pct = all > 0 ? Math.round((regional / all) * 100) : 0;

  return (
    <div
      className="shrink-0 px-5 py-4"
      style={{ borderTop: `1px solid ${HAIRLINE}`, background: 'rgba(10, 10, 10, 0.96)' }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-baseline justify-between gap-3 text-left"
        aria-expanded={open}
      >
        <span className="text-[9px] uppercase tracking-[0.28em]" style={{ color: FAINT }}>
          Not on the map <span style={{ opacity: 0.7 }}>{open ? '−' : '+'}</span>
        </span>
        {hasGroups && (
          <span className="font-mono text-[10px] tabular-nums" style={{ color: GOLD }}>
            {pct}% of {metricLabel.toLowerCase()}
          </span>
        )}
      </button>

      {open && hasGroups && (
        <>
          <p className="mt-2 text-[11px] leading-relaxed" style={{ color: DIM }}>
            Tagged to a region, not a country — no polygon can hold it.
          </p>
          <div className="mt-2.5">
            {groups.map((g) => (
              <div key={g.territory} className="flex items-baseline justify-between gap-3 py-[3px]">
                <span className="truncate text-[11px]" style={{ color: BODY }}>
                  {g.territory}
                </span>
                <span className="shrink-0 font-mono text-[11px] tabular-nums" style={{ color: DIM }}>
                  {compact(g[metric], money)}
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
            <span className="font-mono text-[11px] tabular-nums" style={{ color: TEXT }}>
              {compact(mapped, money)}
              <span style={{ color: FAINT }}> / </span>
              {compact(all, money)}
            </span>
          </div>
        </>
      )}

      {open && orphanCount > 0 && (
        <div
          className="mt-3 pt-2 text-[10px] leading-relaxed"
          style={{ color: FAINT, borderTop: '1px dashed rgba(255,255,255,0.10)' }}
        >
          {metric === 'consignees'
            ? `${orphanCount} consignees name a country with no Territory record.`
            : `${orphanCount} claims name a company that is not a Customer, so they reach no country.`}
        </div>
      )}
    </div>
  );
}
