import { useEffect, useMemo, useState } from 'react';
import { apiGet } from '@shared/api';
import { BODY, Bar, Brackets, DIM, FAINT, GOLD, HAIRLINE, Note, SLAB, TEXT, TRACK, compact } from './atoms';

const VIEW = { w: 1000, h: 620 };
const CENTRE = { x: VIEW.w / 2, y: VIEW.h / 2 };

/**
 * Delivery points around Jomo Kenyatta International.
 *
 * These handlers have no coordinates anywhere in the system — no latitude, no
 * address — and every one of them sits at the same airport, so plotting them
 * geographically would be both impossible and pointless. The ring is a
 * **schematic**: angle is arbitrary, and only the radius and disc size carry
 * meaning (bigger and closer to the hub = more volume). The caption says so on
 * screen, because a diagram that looks like a map will be read as one.
 */
export default function HubView({ dateFrom, dateTo }) {
  const [data, setData] = useState(null);
  const [state, setState] = useState('loading');
  const [active, setActive] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailState, setDetailState] = useState('idle');

  useEffect(() => {
    let cancelled = false;
    setState('loading');
    apiGet('upande_crm.api.logistics.crm_delivery_points', { date_from: dateFrom, date_to: dateTo })
      .then((d) => {
        if (cancelled) return;
        setData(d || null);
        setState('ready');
      })
      .catch(() => !cancelled && setState('error'));
    return () => {
      cancelled = true;
    };
  }, [dateFrom, dateTo]);

  useEffect(() => {
    if (!active) {
      setDetail(null);
      setDetailState('idle');
      return undefined;
    }
    let cancelled = false;
    setDetailState('loading');
    apiGet('upande_crm.api.logistics.crm_delivery_point_detail', {
      point: active,
      date_from: dateFrom,
      date_to: dateTo,
    })
      .then((d) => {
        if (cancelled) return;
        setDetail(d || null);
        setDetailState('ready');
      })
      .catch(() => !cancelled && setDetailState('error'));
    return () => {
      cancelled = true;
    };
  }, [active, dateFrom, dateTo]);

  const points = data?.points || [];
  const maxOrders = Math.max(1, ...points.map((p) => p.orders || 0));

  // Volume decides radius and disc size; angle carries no meaning.
  //
  // Angles are deliberately not evenly spaced. Radius falls as volume rises, so
  // the two busiest handlers sit closest to the hub — and with even spacing they
  // landed adjacent and their discs merged into one blob. Each disc is instead
  // given an angular slot wide enough to contain it at its own radius, so a big
  // near disc claims more of the circle than a small far one and none can
  // collide.
  const placed = useMemo(() => {
    if (!points.length) return [];
    const geom = points.map((p) => {
      const share = (p.orders || 0) / maxOrders;
      const radius = 120 + (1 - share) * 175;
      const r = 7 + share * 26;
      // The angle this disc needs at its radius. Sized by the label, not the
      // disc: out at the rim the discs are tiny but the names are not, so
      // reserving disc width alone let "AGROTRONICS FREIGHT…" collide with its
      // neighbour. ~5.5px per character at font-size 11.
      const halfLabel = Math.min(String(p.label || '').length, 20) * 5.5 * 0.5;
      const need = Math.asin(Math.min(0.9, (Math.max(r, halfLabel) + 10) / radius)) * 2;
      return { p, radius, r, need };
    });
    const scale = (Math.PI * 2) / geom.reduce((a, g) => a + g.need, 0);
    let cursor = -Math.PI / 2;
    return geom.map(({ p, radius, r, need }) => {
      const slot = need * scale;
      const angle = cursor + slot / 2;
      cursor += slot;
      return {
        ...p,
        // x is stretched 1.45x: the side panel makes the plot wider than tall,
        // so a true circle would leave the flanks empty.
        x: CENTRE.x + Math.cos(angle) * radius * 1.45,
        y: CENTRE.y + Math.sin(angle) * radius,
        r,
      };
    });
  }, [points, maxOrders]);

  if (state === 'error') {
    return (
      <div className="grid h-full place-items-center text-[12px]" style={{ color: DIM }}>
        Could not load delivery points.
      </div>
    );
  }

  return (
    <div className="grid h-full grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px]" style={{ background: '#0a0a0a' }}>
      <div className="relative min-h-[45vh]">
        <div className="pointer-events-none absolute inset-x-0 top-0 p-4 pt-14">
          <div className="text-[9px] uppercase tracking-[0.3em]" style={{ color: FAINT }}>
            Origin logistics · Nairobi
          </div>
          <div className="mt-1 font-display text-[22px] leading-none" style={{ color: TEXT }}>
            {points.length} delivery points through JKIA
          </div>
        </div>

        {state === 'loading' ? (
          <div className="grid h-full place-items-center text-[10px] uppercase tracking-[0.28em]" style={{ color: FAINT }}>
            Acquiring…
          </div>
        ) : (
          <svg viewBox={`0 0 ${VIEW.w} ${VIEW.h}`} className="h-full w-full select-none" role="img"
               aria-label="Schematic of freight handlers around Jomo Kenyatta International Airport">
            <rect x={-VIEW.w} y={-VIEW.h} width={VIEW.w * 3} height={VIEW.h * 3} fill="#0a0a0a"
                  onClick={() => setActive(null)} />
            {[150, 250, 350, 450].map((r) => (
              <ellipse key={r} cx={CENTRE.x} cy={CENTRE.y} rx={r * 1.45} ry={r}
                       fill="none" stroke="rgba(255,255,255,0.05)" />
            ))}

            {placed.map((p) => (
              <line key={`l-${p.label}`} x1={CENTRE.x} y1={CENTRE.y} x2={p.x} y2={p.y}
                    stroke={p.label === active ? GOLD : 'rgba(255,255,255,0.10)'}
                    strokeWidth={p.label === active ? 1.4 : 0.6} />
            ))}

            {placed.map((p) => {
              const on = p.label === active;
              return (
                <g key={p.label} style={{ cursor: 'pointer' }}
                   onClick={(e) => { e.stopPropagation(); setActive(on ? null : p.label); }}>
                  <circle cx={p.x} cy={p.y} r={p.r}
                          fill={on ? GOLD : 'rgba(217,165,20,0.42)'}
                          stroke={on ? GOLD : 'rgba(217,165,20,0.65)'} strokeWidth="1" />
                  <text x={p.x} y={p.y + p.r + 13} textAnchor="middle"
                        style={{ fontSize: 11, fill: on ? TEXT : 'rgba(255,255,255,0.62)' }}>
                    {p.label.length > 20 ? `${p.label.slice(0, 19)}…` : p.label}
                  </text>
                </g>
              );
            })}

            <circle cx={CENTRE.x} cy={CENTRE.y} r="30" fill="#0a0a0a" stroke={GOLD} strokeWidth="1.6" />
            <text x={CENTRE.x} y={CENTRE.y + 1} textAnchor="middle"
                  style={{ fontSize: 15, fill: GOLD, letterSpacing: '0.1em' }}>NBO</text>
            <text x={CENTRE.x} y={CENTRE.y + 17} textAnchor="middle"
                  style={{ fontSize: 8.5, fill: 'rgba(255,255,255,0.45)', letterSpacing: '0.12em' }}>JKIA</text>
          </svg>
        )}

        <div className="pointer-events-none absolute bottom-3 left-4 right-4 text-[9px] leading-relaxed"
             style={{ color: FAINT }}>
          Schematic, not geography — these handlers all operate at JKIA and carry no
          coordinates in the system. Disc size and distance from the hub show order
          volume; the angle means nothing.
        </div>
      </div>

      <div className="relative flex min-h-0 flex-col overflow-hidden"
           style={{ background: SLAB, borderLeft: `1px solid ${HAIRLINE}` }}>
        <Brackets />
        <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5 pt-14">
          {!active && (
            <>
              <div className="text-[9px] uppercase tracking-[0.3em]" style={{ color: FAINT }}>
                Handlers by volume
              </div>
              <p className="mt-2 mb-3 text-[11px] leading-relaxed" style={{ color: DIM }}>
                Click a handler for the customers moving through it.
              </p>
              <table className="w-full">
                <thead>
                  <tr style={{ color: FAINT }}>
                    <th className="pb-1 text-left text-[9px] font-normal uppercase tracking-[0.18em]">Point</th>
                    <th className="pb-1 text-right text-[9px] font-normal uppercase tracking-[0.18em]">Ord</th>
                    <th className="pb-1 text-right text-[9px] font-normal uppercase tracking-[0.18em]">Cust</th>
                    <th className="pb-1 text-right text-[9px] font-normal uppercase tracking-[0.18em]">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {points.map((p) => (
                    <tr key={p.label} onClick={() => setActive(p.label)}
                        className="cursor-pointer"
                        style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                      <td className="max-w-[9rem] truncate py-1.5 text-[11px]" style={{ color: BODY }}>{p.label}</td>
                      <td className="py-1.5 text-right font-mono text-[11px] tabular-nums" style={{ color: DIM }}>{p.orders}</td>
                      <td className="py-1.5 text-right font-mono text-[11px] tabular-nums" style={{ color: DIM }}>{p.customers}</td>
                      <td className="py-1.5 text-right font-mono text-[11px] tabular-nums" style={{ color: TEXT }}>
                        {compact(p.value, data?.currency)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data?.unrouted > 0 && (
                <Note>{data.unrouted} submitted orders name no delivery point, so they are not in this ring.</Note>
              )}
            </>
          )}

          {active && (
            <>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-[9px] uppercase tracking-[0.3em]" style={{ color: FAINT }}>Handler</div>
                  <h2 className="mt-1.5 truncate font-display text-[22px] leading-tight" style={{ color: TEXT }}>{active}</h2>
                </div>
                <button type="button" onClick={() => setActive(null)}
                        className="shrink-0 px-2 py-1 text-[10px] uppercase tracking-[0.18em]"
                        style={{ color: DIM, border: `1px solid ${HAIRLINE}` }}>Back</button>
              </div>

              {detailState === 'loading' && (
                <div className="mt-4 text-[11px] uppercase tracking-[0.2em]" style={{ color: FAINT }}>Pulling…</div>
              )}
              {detailState === 'ready' && detail && (
                <div className="mt-4">
                  <SubSection title="Customers shipping through">
                    {detail.customers?.length ? detail.customers.map((c) => (
                      <Bar key={c.label} label={c.label} sub={c.territory || 'untagged'} value={c.value}
                           max={Math.max(1, ...detail.customers.map((x) => x.value || 0))} currency={detail.currency} />
                    )) : <div className="text-[11px]" style={{ color: FAINT }}>None in range.</div>}
                  </SubSection>
                  <SubSection title="Where it ends up">
                    {detail.destinations?.length ? detail.destinations.map((d) => (
                      <Bar key={d.label} label={d.label} value={d.value}
                           max={Math.max(1, ...detail.destinations.map((x) => x.value || 0))} currency={detail.currency} />
                    )) : <div className="text-[11px]" style={{ color: FAINT }}>Unknown.</div>}
                  </SubSection>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function SubSection({ title, children }) {
  return (
    <div className="mb-5">
      <div className="mb-2 pb-1 text-[9px] uppercase tracking-[0.28em]"
           style={{ color: FAINT, borderBottom: '1px solid rgba(255,255,255,0.08)' }}>{title}</div>
      {children}
    </div>
  );
}
