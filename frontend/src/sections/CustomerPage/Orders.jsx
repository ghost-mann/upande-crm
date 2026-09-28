import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { fmt, fmtDate, fmtMoney } from '@shared/utils';
import { cn } from '@/lib/utils';
import DataTable from '../../components/DataTable';
import ChartCard from '../../components/ChartCard';
import { BarsChart } from '../../charts/Charts';
import StatusBadge from '../../components/StatusBadge';
import { customerOrdersApi } from '../../lib/customer';
import useLoad from './useLoad';

// The customer's full order history from ERPNext, a page at a time.
const KINDS = ['Sales Order', 'Delivery Note', 'Sales Invoice'];
const PAGE = 25;

export default function Orders({ name, currency }) {
  const [kind, setKind] = useState('Sales Order');
  const [status, setStatus] = useState('');
  const [start, setStart] = useState(0);
  const { data, err, loading } = useLoad(
    () => customerOrdersApi(name, { kind, status: status || undefined, start, page_len: PAGE }),
    [name, kind, status, start],
  );

  const pick = (k) => { setKind(k); setStatus(''); setStart(0); };
  const columns = [
    { key: 'date', label: 'Date', cls: 'cell-id', render: (r) => fmtDate(r.date) },
    { key: 'name', label: 'Number', cls: 'cell-id' },
    { key: 'status', label: 'Status', render: (r) => <StatusBadge value={r.docstatus === 0 ? 'Draft' : r.status} /> },
    { key: 'grand_total', label: `Amount (${currency})`, cls: 'cell-num', render: (r) => fmtMoney(r.grand_total, currency) },
    ...(kind === 'Sales Invoice'
      ? [{ key: 'outstanding', label: 'Outstanding', cls: 'cell-num', render: (r) => (r.outstanding ? fmtMoney(r.outstanding, currency) : '—') }]
      : []),
  ];
  const total = data?.total || 0;
  const pager = (
    <div className="flex items-center justify-between gap-3 px-5 py-3 border-t border-hairline text-[12.5px] text-ink-3">
      <span>{total ? `${fmt(start + 1)}–${fmt(Math.min(start + PAGE, total))} of ${fmt(total)}` : 'None'}</span>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" className="rounded-full" disabled={loading || start === 0} onClick={() => setStart(Math.max(0, start - PAGE))}>Newer</Button>
        <Button size="sm" variant="outline" className="rounded-full" disabled={loading || start + PAGE >= total} onClick={() => setStart(start + PAGE)}>Older</Button>
      </div>
    </div>
  );

  return (
    <>
      <div className="flex items-center gap-3 flex-wrap mb-4">
        <div className="inline-flex gap-1 p-1 rounded-full bg-[var(--hover)]">
          {KINDS.map((k) => (
            <button key={k} type="button" onClick={() => pick(k)}
              className={cn('px-3.5 h-8 rounded-full text-[12.5px]', kind === k ? 'bg-ink text-white' : 'text-ink-3 hover:text-ink')}>
              {k}s
            </button>
          ))}
        </div>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setStart(0); }}
          className="h-8 rounded-full border border-input bg-transparent px-3 text-[12.5px]">
          <option value="">Any status</option>
          {(data?.statuses || []).map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        {data?.summary && (
          <span className="text-[12.5px] text-ink-3 ml-auto">
            Unpaid on invoices: <b className="text-ink">{fmtMoney(data.summary.outstanding, currency)}</b>
          </span>
        )}
      </div>
      {err && <div className="crm-empty">{err}</div>}
      {data?.summary && (
        <div className="mb-4">
          <ChartCard title={`${kind}s per month`} sub="Last 12 months" height="h-[180px]">
            <BarsChart labels={data.summary.per_month.map((r) => r.label)} data={data.summary.per_month.map((r) => r.count)} />
          </ChartCard>
        </div>
      )}
      <DataTable title={`${kind}s`} subOverride={loading ? 'Loading…' : `${fmt(total)} in total`} columns={columns}
        rows={data?.rows || []} doctype={kind} emptyText={loading ? 'Loading…' : `No ${kind.toLowerCase()}s for this customer`}
        footer={pager} />
    </>
  );
}
