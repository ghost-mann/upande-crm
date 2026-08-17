import { useState } from 'react';
import { fmt, fmtMoneyCompact } from '@shared/utils';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { useStore } from '../../store';
import { openFrappe } from '@/lib/crm';
import { CardTabs, Delta } from './parts';

// The five best-selling varieties, read three ways.
//
// The matrix answers "who carries each variety", the per-customer list answers
// "what does this account actually buy" — a small account's mix is not the house
// mix — and the rep view answers "who sold it".

const TABS = [
  { value: 'matrix', label: 'Matrix' },
  { value: 'per_customer', label: 'Per customer' },
  { value: 'by_rep', label: 'By rep' },
];

function Cell({ cell, ccy }) {
  // No cell at all means this account has never bought the variety in either
  // window — a different fact from "bought none this period", and the reason this
  // renders as a dash rather than as a zero.
  if (!cell) return <td className="text-center text-ink-faint">—</td>;
  return (
    <td className="text-right whitespace-nowrap">
      <div className="tabular-nums text-ink font-medium">{fmtMoneyCompact(cell.amount, ccy)}</div>
      <div className="text-[11px]">
        {cell.stopped
          ? <span className="text-bad font-medium">stopped</span>
          : <Delta pct={cell.delta_pct} prev={cell.prev} />}
      </div>
    </td>
  );
}

function Matrix({ varieties, rows, ccy }) {
  const newTab = useStore((s) => s.settings.openInNewTab);
  const openMover = useStore((s) => s.openMover);
  if (!rows?.length) return <div className="crm-empty">No sales in range</div>;
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Customer</th>
            {varieties.map((v) => (
              <th key={v.key} className="!text-right">
                <button type="button" onClick={() => openMover('flower', v.key, v.label)}
                  className="hover:underline">{v.label}</button>
              </th>
            ))}
            <th className="!text-right">Total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.customer} className="clickable"
              onClick={() => openFrappe('Customer', r.customer, newTab)}>
              <td className="max-w-[240px]">
                <div className="truncate text-ink font-medium" title={r.customer}>{r.customer}</div>
              </td>
              {varieties.map((v) => <Cell key={v.key} cell={r.cells[v.key]} ccy={ccy} />)}
              <td className="text-right whitespace-nowrap">
                <div className="tabular-nums text-ink font-semibold">{fmtMoneyCompact(r.total, ccy)}</div>
                <div className="text-[11px]"><Delta pct={r.delta_pct} prev={r.prev_total} /></div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PerCustomer({ rows, ccy }) {
  const newTab = useStore((s) => s.settings.openInNewTab);
  const openMover = useStore((s) => s.openMover);
  if (!rows?.length) return <div className="crm-empty">No sales in range</div>;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
      {rows.map((r, i) => {
        const max = Math.max(...r.top.map((t) => t.amount), 1);
        return (
          <div key={r.customer} className="py-3.5 border-b border-hairline">
            <div className="flex items-baseline gap-2 mb-2.5">
              <span className="text-[12px] text-ink-mute tabular-nums w-[18px]">{i + 1}</span>
              <button type="button" onClick={() => openFrappe('Customer', r.customer, newTab)}
                className="text-[14px] font-semibold text-ink truncate hover:underline text-left flex-1"
                title={r.customer}>{r.customer}</button>
              <span className="text-[13px] font-semibold text-ink tabular-nums shrink-0">
                {fmtMoneyCompact(r.total, ccy)}
              </span>
            </div>
            <div className="pl-[26px]">
              {r.top.map((t) => (
                <button key={t.key} type="button" onClick={() => openMover('flower', t.key, t.label)}
                  className="w-full grid grid-cols-[1fr_58px] gap-2.5 items-center py-[3px] group">
                  <span className="min-w-0">
                    <span className="flex items-baseline justify-between gap-2">
                      <span className="text-[12px] text-ink-2 truncate group-hover:underline">{t.label}</span>
                      <span className="text-[11px] text-ink-mute tabular-nums shrink-0">
                        {fmt(Math.round(t.qty))} stems
                      </span>
                    </span>
                    <span className="block h-[5px] rounded-full bg-surface-3 mt-1 overflow-hidden">
                      <span className="block h-full rounded-full bg-gold"
                        style={{ width: `${Math.max((t.amount / max) * 100, 2)}%` }} />
                    </span>
                  </span>
                  <span className="text-[11.5px] text-ink font-medium tabular-nums text-right">
                    {fmtMoneyCompact(t.amount, ccy)}
                  </span>
                </button>
              ))}
              <div className="text-[11px] text-ink-mute mt-1.5">
                {fmt(r.varieties)} varieties bought in range
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ByRep({ rows, ccy }) {
  const newTab = useStore((s) => s.settings.openInNewTab);
  const openMover = useStore((s) => s.openMover);
  if (!rows?.length) return <div className="crm-empty">No rep data in range</div>;
  return (
    <div>
      {rows.map((r, i) => (
        <div key={r.key} className="py-3.5 border-b border-hairline last:border-0">
          <div className="flex items-baseline gap-2.5 mb-2">
            <span className={`list__rank${i === 0 ? ' lead' : ''}`}>{i + 1}</span>
            <button type="button" onClick={() => openMover('rep', r.key, r.label)}
              className="text-[14px] font-semibold text-ink hover:underline">{r.label}</button>
            <span className="text-[11.5px] text-ink-mute">
              {fmt(r.orders)} orders · {fmt(r.account_count)} accounts
            </span>
            <span className="ml-auto text-[14px] font-semibold text-ink tabular-nums">
              {fmtMoneyCompact(r.amount, ccy)}
            </span>
          </div>
          <div className="pl-[42px] flex flex-wrap gap-x-5 gap-y-1">
            {r.accounts.map((a) => (
              <button key={a.customer} type="button"
                onClick={() => openFrappe('Customer', a.customer, newTab)}
                className="text-[12px] text-ink-2 hover:underline">
                {a.customer}
                <span className="text-ink-mute tabular-nums ml-1.5">{fmtMoneyCompact(a.amount, ccy)}</span>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function TopSellers() {
  const T = useStore((s) => s.data.track);
  const [tab, setTab] = useState('matrix');
  const S = T?.top_sellers;
  if (!S) return null;
  const ccy = T?.currency || 'KES';

  const SUB = {
    matrix: 'Rows are accounts, columns are the five best sellers · ± against the prior period',
    per_customer: "Each account's own top five — a small account's mix is not the house mix",
    by_rep: 'Top salespeople and the accounts behind their number',
  };

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Top 5 sellers</CardTitle>
          <CardSub>{SUB[tab]}</CardSub>
        </div>
        <CardTabs value={tab} onChange={setTab} tabs={TABS} />
      </CardHeader>
      {tab === 'matrix'
        ? <Matrix varieties={S.varieties || []} rows={S.matrix} ccy={ccy} />
        : (
          <CardContent>
            {tab === 'per_customer'
              ? <PerCustomer rows={S.per_customer} ccy={ccy} />
              : <ByRep rows={S.by_rep} ccy={ccy} />}
          </CardContent>
        )}
    </Card>
  );
}
