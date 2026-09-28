import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { fmtDate, fmtMoney } from '@shared/utils';
import DataTable from '../../components/DataTable';
import { quotationColumns } from '../Quotations/index.jsx';
import { customerQuotationsApi } from '@/lib/service';
import useLoad from './useLoad';

// The customer's quotations, and every price quoted to them per item — the
// history a pricing discussion needs.
export default function Quotations({ name, currency }) {
  const { data, err } = useLoad(() => customerQuotationsApi(name), [name]);
  if (err) return <div className="crm-empty">{err}</div>;
  if (!data) return <div className="crm-empty">Loading…</div>;
  if (!data.available) return <div className="crm-empty">You don't have access to quotations.</div>;
  const ccy = data.currency || currency;
  return (
    <>
      <DataTable title="Quotations" subOverride={`${data.rows.length} on record`} columns={quotationColumns(ccy, false)}
        rows={data.rows} doctype="Quotation" emptyText="No quotations for this customer" />
      <Card className="mt-4">
        <CardHeader><div><CardTitle>Prices quoted over time</CardTitle><CardSub>Every rate this customer was offered, per item, oldest to newest</CardSub></div></CardHeader>
        <CardContent>
          {!data.price_history.length && <div className="crm-empty">No quoted items yet</div>}
          {data.price_history.map((h) => (
            <div key={h.item_code} className="py-3 border-b border-hairline last:border-b-0">
              <div className="flex items-baseline justify-between gap-4 flex-wrap">
                <span className="text-[13px] text-ink font-medium">{h.item_name || h.item_code}
                  {h.uom && <span className="text-ink-mute text-[11.5px] font-normal"> · per {h.uom}</span>}</span>
                <span className="text-[12px] text-ink-3">latest {fmtMoney(h.latest, h.points.at(-1)?.currency)} · range {fmtMoney(h.low, h.points[0]?.currency)}–{fmtMoney(h.high, h.points[0]?.currency)}</span>
              </div>
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {h.points.map((p) => (
                  <span key={`${p.quotation}-${p.date}-${p.rate}`} title={p.quotation}
                    className={`text-[11.5px] px-2 py-0.5 rounded-full border border-hairline ${p.draft ? 'text-ink-mute' : 'text-ink-2'}`}>
                    {fmtDate(p.date)} · {fmtMoney(p.rate, p.currency)}{p.draft ? ' (draft)' : ''}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </>
  );
}
