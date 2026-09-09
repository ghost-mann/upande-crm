import { useEffect, useState } from 'react';
import { apiGet } from '@shared/api';
import { isMicro } from '../../lib/territory_iso';
import PinnedDetail from './PinnedDetail';
import { Brackets, DIM, FAINT, HAIRLINE, SLAB, Stat, TEXT, compact } from './atoms';

export default function IntelPanel({ territory, row, currency, pinned, dateFrom, dateTo, onClose }) {
  const [detail, setDetail] = useState(null);
  const [state, setState] = useState('idle');

  // Detail is fetched only for a pinned territory. Hover reads the rollup the
  // map already holds, so sweeping the cursor across the world costs no requests.
  useEffect(() => {
    if (!pinned || !territory) {
      setDetail(null);
      setState('idle');
      return undefined;
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
              style={{ color: TEXT }}
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

        <div className="mt-3 grid grid-cols-2 gap-x-4 pb-4">
          <Stat label="Revenue" value={compact(r.revenue, currency)} accent />
          <Stat label="Claims" value={compact(r.claims)} />
          <Stat label="Customers" value={compact(r.customers)} />
          <Stat label="Claim cost" value={compact(r.claim_cost, currency)} />
          <Stat label="Consignees" value={compact(r.consignees)} />
          <Stat label="Pipeline" value={compact(r.opp_value, currency)} />
          <Stat label="Leads" value={compact(r.leads)} />
          <Stat label="Opportunities" value={compact(r.opps)} />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {!pinned && (
          <p className="text-[11px] leading-relaxed" style={{ color: FAINT }}>
            Click to lock on — varieties, claims, correspondents and accounts load
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

        {pinned && state === 'ready' && <PinnedDetail detail={detail} currency={currency} />}
      </div>
    </div>
  );
}
