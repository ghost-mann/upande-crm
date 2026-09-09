import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiGet } from '@shared/api';
import { useStore } from '../../store';
import HubView from './HubView';
import IntelPanel from './IntelPanel';
import RegionalLedger from './RegionalLedger';
import WorldMap, { RAMP } from './WorldMap';
import { DIM, FAINT, GOLD, HAIRLINE, TEXT } from './atoms';

const METRICS = [
  { key: 'revenue', label: 'Revenue', money: true },
  { key: 'claims', label: 'Claims' },
  { key: 'claim_cost', label: 'Claim cost', money: true },
  { key: 'consignees', label: 'Consignees' },
  { key: 'opp_value', label: 'Pipeline', money: true },
  { key: 'opps', label: 'Opps' },
  { key: 'leads', label: 'Leads' },
  { key: 'customers', label: 'Customers' },
];

// The world map answers "where do our customers are"; the hub answers "how does
// it physically leave Kenya". Both are territory questions, but they have no
// shared geography — the handlers all sit on one airport — so they are two views
// rather than one map with a mode.
const VIEWS = [
  { key: 'world', label: 'World' },
  { key: 'hub', label: 'Nairobi hub' },
];

export default function Territories() {
  const dateFrom = useStore((s) => s.dateFrom);
  const dateTo = useStore((s) => s.dateTo);

  const [data, setData] = useState(null);
  const [state, setState] = useState('loading');
  const [view, setView] = useState('world');
  const [metric, setMetric] = useState('revenue');
  const [hovered, setHovered] = useState(null);
  const [pinned, setPinned] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setState('loading');
    apiGet('upande_crm.api.territory.crm_territory_map', { date_from: dateFrom, date_to: dateTo })
      .then((d) => {
        if (cancelled) return;
        setData(d || null);
        setState('ready');
      })
      .catch(() => {
        if (!cancelled) setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [dateFrom, dateTo]);

  // Esc releases the pin. Bound on the window rather than the panel so it works
  // wherever the cursor happens to be over the map.
  useEffect(() => {
    if (!pinned) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') setPinned(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [pinned]);

  const rows = data?.territories || [];
  const byName = useMemo(() => {
    const m = new Map();
    rows.forEach((r) => m.set(r.territory, r));
    return m;
  }, [rows]);

  const shown = pinned || hovered;
  const activeMetric = METRICS.find((m) => m.key === metric) || METRICS[0];
  const clearPin = useCallback(() => setPinned(null), []);

  if (state === 'error') {
    return (
      <div className="grid h-[70vh] place-items-center bg-canvas text-[13px] text-ink-mute">
        Could not load territory data.
      </div>
    );
  }

  return (
    <div className="relative h-[calc(100vh-64px)] overflow-hidden" style={{ background: '#0a0a0a' }}>
      <div className="absolute left-4 top-4 z-10 flex gap-1.5">
        {VIEWS.map((v) => {
          const on = v.key === view;
          return (
            <button
              key={v.key}
              type="button"
              onClick={() => setView(v.key)}
              className="px-2.5 py-1 text-[10px] uppercase tracking-[0.16em]"
              style={{
                color: on ? '#0a0a0a' : DIM,
                background: on ? GOLD : 'rgba(255,255,255,0.05)',
                border: `1px solid ${on ? GOLD : 'rgba(255,255,255,0.12)'}`,
              }}
            >
              {v.label}
            </button>
          );
        })}
      </div>

      {view === 'hub' ? (
        <HubView dateFrom={dateFrom} dateTo={dateTo} />
      ) : (
        <div className="grid h-full grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="relative min-h-[45vh]">
            {state === 'loading' ? (
              <div
                className="grid h-full place-items-center text-[10px] uppercase tracking-[0.28em]"
                style={{ color: FAINT }}
              >
                Acquiring map…
              </div>
            ) : (
              <WorldMap
                rows={rows}
                metric={metric}
                hovered={hovered}
                pinned={pinned}
                onHover={setHovered}
                onPick={setPinned}
                onClearPin={clearPin}
              />
            )}

            <div className="pointer-events-none absolute inset-x-0 top-0 p-4 pt-14">
              <div className="pointer-events-auto">
                <div className="text-[9px] uppercase tracking-[0.3em]" style={{ color: FAINT }}>
                  Territory activity
                </div>
                <div className="mt-1 font-display text-[22px] leading-none" style={{ color: TEXT }}>
                  {rows.length} countries live
                </div>
              </div>

              <div className="pointer-events-auto mt-3 flex flex-wrap gap-1.5">
                {METRICS.map((m) => {
                  const on = m.key === metric;
                  return (
                    <button
                      key={m.key}
                      type="button"
                      onClick={() => setMetric(m.key)}
                      className="px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] transition-colors"
                      style={{
                        color: on ? '#0a0a0a' : DIM,
                        background: on ? GOLD : 'rgba(255,255,255,0.05)',
                        border: `1px solid ${on ? GOLD : 'rgba(255,255,255,0.12)'}`,
                      }}
                    >
                      {m.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <Legend currency={data?.currency} metric={activeMetric} />
          </div>

          <div className="flex min-h-0 flex-col" style={{ borderLeft: `1px solid ${HAIRLINE}` }}>
            <div className="min-h-0 flex-1">
              <IntelPanel
                territory={shown}
                row={shown ? byName.get(shown) : null}
                currency={data?.currency}
                pinned={!!pinned}
                dateFrom={dateFrom}
                dateTo={dateTo}
                onClose={clearPin}
              />
            </div>
            <RegionalLedger
              groups={data?.groups}
              totals={data?.totals}
              orphaned={data?.orphaned}
              currency={data?.currency}
              metric={metric}
              metricLabel={activeMetric.label}
              collapsed={!!pinned}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function Legend({ currency, metric }) {
  return (
    <div className="pointer-events-none absolute bottom-4 left-4 flex items-center gap-2">
      <span className="text-[9px] uppercase tracking-[0.22em]" style={{ color: FAINT }}>
        Low
      </span>
      <div className="flex">
        {RAMP.map((c) => (
          <span key={c} className="h-2 w-6" style={{ background: c }} />
        ))}
      </div>
      <span className="text-[9px] uppercase tracking-[0.22em]" style={{ color: FAINT }}>
        High
      </span>
      <span className="ml-2 text-[9px] uppercase tracking-[0.22em]" style={{ color: DIM }}>
        {metric.label}
        {metric.money && currency ? ` · ${currency}` : ''}
      </span>
    </div>
  );
}
