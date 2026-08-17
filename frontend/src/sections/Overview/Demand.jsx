import { fmt, fmtMoneyCompact } from '@shared/utils';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { useStore } from '../../store';
import { openFrappe } from '@/lib/crm';

// What clients are asking for, as opposed to what they bought.
//
// The Top-5-sellers card beside this one reads Sales Order lines: revenue, and so
// history. This one reads the item lines on opportunities and quotations that are
// still open — wants that have not become orders. Together they answer "what sells"
// and "what is being asked for", which are not the same question and, on a farm
// planning what to plant, not the same decision.
//
// It is thin on purpose rather than by accident: see the note it renders when the
// sample is small.

export default function Demand() {
  const D = useStore((s) => s.data.demand);
  const newTab = useStore((s) => s.settings.openInNewTab);
  const openLead = useStore((s) => s.openLeadDialog);
  if (!D) return null;

  const rows = D.rows || [];
  const ccy = D.currency || 'KES';
  const src = D.sources || {};
  const lines = (src.opportunity_lines || 0) + (src.quotation_lines || 0);
  const max = Math.max(...rows.map((r) => r.qty), 1);

  const provenance = `${fmt(src.opportunity_lines)} opportunity ${
    src.opportunity_lines === 1 ? 'line' : 'lines'} · ${fmt(src.quotation_lines)} quotation ${
    src.quotation_lines === 1 ? 'line' : 'lines'} in range`;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Flowers in demand</CardTitle>
          <CardSub>
            Asked for on open opportunities and quotations — not yet ordered
          </CardSub>
        </div>
        {rows.length > 0 && (
          <div className="text-right shrink-0">
            <div className="text-[17px] font-semibold text-ink tabular-nums leading-tight">
              {fmt(Math.round(D.totals?.qty))}
            </div>
            <div className="text-[11px] text-ink-mute">stems across {fmt(D.totals?.varieties)} varieties</div>
          </div>
        )}
      </CardHeader>
      <CardContent>
        {rows.length ? (
          <div>
            {rows.map((r, i) => (
              <div key={r.key} className="py-3 border-b border-hairline last:border-0">
                <div className="flex items-baseline gap-2.5 mb-1.5">
                  <span className={`list__rank${i === 0 ? ' lead' : ''}`}>{i + 1}</span>
                  <button type="button" onClick={() => openFrappe('Item', r.key, newTab)}
                    className="text-[13.5px] font-semibold text-ink hover:underline truncate text-left"
                    title={r.key}>
                    {r.label}
                  </button>
                  <span className="text-[11.5px] text-ink-mute whitespace-nowrap">
                    {fmt(r.clients)} {r.clients === 1 ? 'client' : 'clients'}
                  </span>
                  <span className="ml-auto text-[13px] font-semibold text-ink tabular-nums whitespace-nowrap">
                    {fmt(Math.round(r.qty))} stems
                  </span>
                </div>
                <div className="pl-[42px]">
                  <span className="block h-[5px] rounded-full bg-surface-3 overflow-hidden">
                    <span className="block h-full rounded-full bg-gold"
                      style={{ width: `${Math.max((r.qty / max) * 100, 2)}%` }} />
                  </span>
                  <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1.5">
                    {r.top_clients.map((c) => (
                      <span key={c.client} className="text-[11.5px] text-ink-2">
                        {c.client}
                        <span className="text-ink-mute tabular-nums ml-1.5">
                          {fmt(Math.round(c.qty))}
                        </span>
                      </span>
                    ))}
                    <span className="ml-auto text-[11px] text-ink-mute tabular-nums">
                      {fmtMoneyCompact(r.amount, ccy)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="crm-empty">Nothing on the books being asked for in this range</div>
        )}

        {/* The sample size, always. Demand is read from lines that reps have to
            enter, and on this site almost nobody did — six opportunity lines
            against forty-three thousand order lines. Saying so is the difference
            between a thin card and a card that looks broken. */}
        <div className="text-[11px] text-ink-mute leading-relaxed border-t border-hairline pt-3 mt-2">
          Read from {provenance}.
          {lines < 25 && (
            <>
              {' '}That is a small sample: demand only appears here when a variety is
              put on the opportunity or quotation itself.{' '}
              <button type="button" onClick={() => openLead({})}
                className="text-gold-text underline hover:no-underline">
                Adding flowers when you convert a lead
              </button>{' '}
              is what fills this in.
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
