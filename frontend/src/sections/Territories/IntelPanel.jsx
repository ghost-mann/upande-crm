import { useEffect, useState } from 'react';
import { apiGet } from '@shared/api';
import { isMicro } from '../../lib/territory_iso';

const GOLD = '#d9a514';

// Every translucent value here is inline rgba on purpose: Tailwind's `/opacity`
// modifier resolves to nothing against this app's CSS-var colour tokens.
const HAIRLINE = 'rgba(217, 165, 20, 0.28)';
const SLAB = 'rgba(14, 14, 13, 0.92)';
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

function Row({ label, value, accent }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-[7px]">
      <span
        className="text-[10px] uppercase tracking-[0.18em]"
        style={{ color: DIM }}
      >
        {label}
      </span>
      <span
        className="font-mono text-[15px] tabular-nums"
        style={{ color: accent ? GOLD : '#f4f3ef' }}
      >
        {value}
      </span>
    </div>
  );
}

function Bar({ label, value, max, currency }) {
  const pct = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0;
  return (
    <div className="py-[5px]">
      <div className="flex items-baseline justify-between gap-3">
        <span className="truncate text-[11px]" style={{ color: 'rgba(255,255,255,0.78)' }}>
          {label}
        </span>
        <span className="shrink-0 font-mono text-[11px] tabular-nums" style={{ color: DIM }}>
          {compact(value, currency)}
        </span>
      </div>
      <div className="mt-1 h-[3px] w-full" style={{ background: 'rgba(255,255,255,0.07)' }}>
        <div className="h-full" style={{ width: `${pct}%`, background: GOLD }} />
      </div>
    </div>
  );
}

/** Corner brackets — the one piece of pure theatre, and it costs four divs. */
function Brackets() {
  const base = 'absolute h-3 w-3 pointer-events-none';
  const s = { borderColor: HAIRLINE };
  return (
    <>
      <div className={`${base} left-0 top-0 border-l border-t`} style={s} />
      <div className={`${base} right-0 top-0 border-r border-t`} style={s} />
      <div className={`${base} bottom-0 left-0 border-b border-l`} style={s} />
      <div className={`${base} bottom-0 right-0 border-b border-r`} style={s} />
    </>
  );
}

export default function IntelPanel({ territory, row, currency, pinned, dateFrom, dateTo, onClose }) {
  const [detail, setDetail] = useState(null);
  const [state, setState] = useState('idle');

  // Detail is fetched only for a pinned territory. Hover reads the rollup the
  // map already holds, so sweeping the cursor across the world costs no requests.
  useEffect(() => {
    if (!pinned || !territory) {
      setDetail(null);
      setState('idle');
      return;
    }
    let cancelled = false;
    setState('loading');
    apiGet('upande_crm.api.territory.crm_territory_detail', {
      territory,
      date_from: dateFrom,
      date_to: dateTo,
    })
      .then((d) => {
        if (cancelled) return;
        setDetail(d || null);
        setState('ready');
      })
      .catch(() => {
        if (!cancelled) setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [pinned, territory, dateFrom, dateTo]);

  if (!territory) {
    return (
      <div
        className="relative flex h-full flex-col items-center justify-center px-6 text-center"
        style={{ background: SLAB, borderLeft: `1px solid ${HAIRLINE}` }}
      >
        <Brackets />
        <div className="text-[10px] uppercase tracking-[0.28em]" style={{ color: FAINT }}>
          No territory selected
        </div>
        <p className="mt-3 max-w-[16rem] text-[12px] leading-relaxed" style={{ color: DIM }}>
          Hover a country to read it. Click to lock on and pull the full file.
        </p>
      </div>
    );
  }

  const r = row || {};
  const topMax = Math.max(1, ...(detail?.top_accounts || []).map((a) => a.amount || 0));
  const stageMax = Math.max(1, ...(detail?.stages || []).map((s) => s.count || 0));

  return (
    <div
      className="relative flex h-full flex-col overflow-hidden"
      style={{ background: SLAB, borderLeft: `1px solid ${HAIRLINE}` }}
    >
      <Brackets />

      <div className="shrink-0 px-5 pt-5" style={{ borderBottom: `1px solid ${HAIRLINE}` }}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[9px] uppercase tracking-[0.3em]" style={{ color: FAINT }}>
              {pinned ? 'Locked' : 'Preview'}
              {isMicro(territory) ? ' · no polygon' : ''}
            </div>
            <h2
              className="mt-1.5 truncate font-display text-[26px] leading-tight"
              style={{ color: '#f4f3ef' }}
              title={territory}
            >
              {territory}
            </h2>
          </div>
          {pinned && (
            <button
              type="button"
              onClick={onClose}
              className="shrink-0 px-2 py-1 text-[10px] uppercase tracking-[0.18em]"
              style={{ color: DIM, border: `1px solid ${HAIRLINE}` }}
            >
              Esc
            </button>
          )}
        </div>

        <div className="mt-3 pb-4">
          <Row label="Leads" value={compact(r.leads)} />
          <Row label="Opportunities" value={compact(r.opps)} />
          <Row label="Pipeline" value={compact(r.opp_value, currency)} />
          <Row label="Customers" value={compact(r.customers)} />
          <Row label="Revenue" value={compact(r.revenue, currency)} accent />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {!pinned && (
          <p className="text-[11px] leading-relaxed" style={{ color: FAINT }}>
            Click to lock on — top accounts, stage split and recent activity load
            with the full file.
          </p>
        )}

        {pinned && state === 'loading' && (
          <div className="text-[11px] uppercase tracking-[0.2em]" style={{ color: FAINT }}>
            Pulling file…
          </div>
        )}

        {pinned && state === 'error' && (
          <div className="text-[11px] leading-relaxed" style={{ color: DIM }}>
            Could not reach the detail feed. The figures above still hold.
          </div>
        )}

        {pinned && state === 'ready' && detail && (
          <>
            <Section title="Top accounts">
              {detail.top_accounts?.length ? (
                detail.top_accounts.map((a) => (
                  <Bar key={a.label} label={a.label} value={a.amount} max={topMax} currency={currency} />
                ))
              ) : (
                <Empty>No billed revenue in range.</Empty>
              )}
            </Section>

            <Section title="Stage split">
              {detail.stages?.length ? (
                detail.stages.map((s) => (
                  <Bar key={s.label} label={`${s.label} · ${s.count}`} value={s.count} max={stageMax} />
                ))
              ) : (
                <Empty>No open opportunities.</Empty>
              )}
            </Section>

            <Section title="Recent activity">
              {detail.recent?.length ? (
                detail.recent.map((x) => (
                  <div key={`${x.doctype}-${x.name}`} className="flex items-baseline justify-between gap-3 py-1">
                    <span className="truncate text-[11px]" style={{ color: 'rgba(255,255,255,0.78)' }}>
                      {x.title || x.name}
                    </span>
                    <span className="shrink-0 font-mono text-[10px] uppercase" style={{ color: FAINT }}>
                      {x.doctype === 'Lead' ? 'LEAD' : 'OPP'}
                    </span>
                  </div>
                ))
              ) : (
                <Empty>Nothing logged.</Empty>
              )}
            </Section>
          </>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="mb-5">
      <div
        className="mb-2 pb-1 text-[9px] uppercase tracking-[0.28em]"
        style={{ color: FAINT, borderBottom: `1px solid rgba(255,255,255,0.08)` }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

const Empty = ({ children }) => (
  <div className="py-1 text-[11px]" style={{ color: FAINT }}>
    {children}
  </div>
);
