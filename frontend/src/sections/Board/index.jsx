import { useCallback, useEffect, useState } from 'react';
import { fmt, fmtMoneyCompact } from '@shared/utils';
import { cn } from '@/lib/utils';
import { useStore } from '../../store';
import Icon from '../../components/Icon';
import { openFrappe, shortUser } from '@/lib/crm';
import { boardApi, setStageApi, qualifyLeadApi } from '@/lib/service';

// Every open prospect and where it stands: leads (with their qualification), each
// opportunity stage from CRM Settings, then the customers confirmed in the range.
// A card moves by its select — stage for an opportunity, qualification for a lead.
const QUAL_TONE = { Qualified: 'bdg-good', 'In Process': 'bdg-warn', Unqualified: 'bdg-other' };

function Card({ card, stages, qualification, onMoved, busy }) {
  const newTab = useStore((s) => s.settings.openInNewTab);
  const openCustomer = useStore((s) => s.openCustomer);
  const [err, setErr] = useState('');
  const openIt = () => (card.doctype === 'Customer' ? openCustomer(card.name) : openFrappe(card.doctype, card.name, newTab));

  const move = async (fn, value) => {
    setErr('');
    try { await fn(card.name, value); onMoved(); } catch (e) { setErr(e.message || 'Could not move'); }
  };

  return (
    <div className="rounded-card-in bg-surface border border-hairline p-3 shadow-card">
      <button type="button" onClick={openIt} className="text-left w-full">
        <div className="text-[13px] text-ink font-medium leading-snug break-words">{card.title}</div>
        {card.subtitle && <div className="text-[11.5px] text-ink-3 truncate">{card.subtitle}</div>}
      </button>
      <div className="flex items-center gap-1.5 flex-wrap mt-2 text-[11px] text-ink-mute">
        {card.doctype === 'Opportunity' && card.amount > 0 && <span className="text-ink-2 font-medium">{fmtMoneyCompact(card.amount, card.currency)}</span>}
        {card.source && card.source !== 'Unknown' && <span>{card.source}</span>}
        {card.age_days != null && <span>{card.age_days}d old</span>}
        {card.owner && <span>· {shortUser(card.owner)}</span>}
        {card.created && <span>since {card.created}</span>}
      </div>
      {card.doctype === 'Lead' && (
        <div className="mt-2 flex items-center gap-2">
          <span className={`bdg ${QUAL_TONE[card.qualification] || 'bdg-other'}`}>{card.qualification || 'Unqualified'}</span>
          <select aria-label="Qualification" disabled={busy} value={card.qualification || 'Unqualified'}
            onChange={(e) => move(qualifyLeadApi, e.target.value)}
            className="h-7 flex-1 min-w-0 rounded-md border border-input bg-transparent px-1.5 text-[11.5px]">
            {qualification.map((q) => <option key={q} value={q}>{q}</option>)}
          </select>
        </div>
      )}
      {card.doctype === 'Opportunity' && (
        <select aria-label="Stage" disabled={busy} value={stages.includes(card.stage) ? card.stage : ''}
          onChange={(e) => e.target.value && move(setStageApi, e.target.value)}
          className="mt-2 h-7 w-full rounded-md border border-input bg-transparent px-1.5 text-[11.5px]">
          {!stages.includes(card.stage) && <option value="">{card.stage || 'No stage'} — move to…</option>}
          {stages.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      )}
      {err && <div className="mt-1 text-[11px] text-bad">{err}</div>}
    </div>
  );
}

export default function Board() {
  const dateFrom = useStore((s) => s.dateFrom);
  const dateTo = useStore((s) => s.dateTo);
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setBusy(true);
    boardApi({ date_from: dateFrom, date_to: dateTo })
      .then((d) => { setData(d); setErr(''); })
      .catch((e) => setErr(e.message || 'Could not load the board'))
      .finally(() => setBusy(false));
  }, [dateFrom, dateTo]);
  useEffect(() => { load(); }, [load]);

  if (err && !data) return <div className="crm-empty">{err}</div>;
  if (!data) return <div className="p-12 text-center text-ink-mute text-[13px]">Loading…</div>;

  return (
    <>
      <div className="text-[12px] text-ink-mute mb-3">
        Stages come from CRM Settings → Pipeline Stages. Move an opportunity with its stage select; qualify a lead with its select.
      </div>
      <div className="flex gap-3 overflow-x-auto crm-scroll pb-3 items-start">
        {data.columns.map((col) => (
          <div key={col.key} className={cn('w-[260px] shrink-0 rounded-card bg-surface-2 border border-hairline p-3',
            col.key === 'customers' && 'bg-good-soft/40', col.key === 'other' && 'opacity-90')}>
            <div className="flex items-baseline justify-between gap-2 mb-1">
              <span className="text-[13px] font-semibold text-ink truncate">{col.label}</span>
              <span className="text-[12px] tabular-nums text-ink-3">{fmt(col.count)}</span>
            </div>
            {col.value > 0 && <div className="text-[11.5px] text-ink-3 mb-1" title="Summed in company currency">{fmtMoneyCompact(col.value, data.currency)} in play</div>}
            {col.note && <div className="text-[11px] text-ink-mute mb-2">{col.note}</div>}
            <div className="grid gap-2 mt-2 max-h-[calc(100vh-330px)] overflow-y-auto crm-scroll pr-0.5">
              {col.cards.map((c) => (
                <Card key={`${c.doctype}-${c.name}`} card={c} stages={data.stages} qualification={data.qualification}
                  onMoved={load} busy={busy} />
              ))}
              {!col.cards.length && <div className="text-[12px] text-ink-mute py-4 text-center">Nothing here</div>}
              {col.count > col.cards.length && (
                <div className="text-[11px] text-ink-mute text-center">+ {fmt(col.count - col.cards.length)} more</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
