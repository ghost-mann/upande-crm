import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { fmt, fmtDate, fmtMoney } from '@shared/utils';
import DataTable from '../../components/DataTable';
import Icon from '../../components/Icon';
import { customerPricingApi } from '../../lib/customer';
import useLoad from './useLoad';

// Agreed prices, beside what was actually charged. On this site prices live on
// price lists, not per customer, so the banner names the list being shown.
const PAGE = 50;

export default function Pricing({ name }) {
  const [q, setQ] = useState('');
  const [search, setSearch] = useState('');
  const [start, setStart] = useState(0);
  useEffect(() => { const t = setTimeout(() => { setSearch(q.trim()); setStart(0); }, 300); return () => clearTimeout(t); }, [q]);
  const { data, err, loading } = useLoad(
    () => customerPricingApi(name, { search: search || undefined, start, page_len: PAGE }),
    [name, search, start],
  );

  if (err) return <div className="crm-empty">{err}</div>;
  if (!data) return <div className="crm-empty">Loading…</div>;
  if (data.no_access) return <div className="crm-empty">You don't have access to price lists, so agreed prices are not shown here.</div>;
  if (!data.price_list) {
    return (
      <div className="crm-empty">
        No price list is set on this customer or its customer group, so there are no agreed prices to show.
        Set a Default Price List on the customer in the desk.
      </div>
    );
  }

  const columns = [
    { key: 'item_code', label: 'Item', render: (r) => (
      <div><div className="text-ink">{r.item_name || r.item_code}</div>{r.item_name && r.item_name !== r.item_code && <div className="text-[11px] text-ink-mute">{r.item_code}</div>}</div>
    ) },
    { key: 'uom', label: 'Unit', render: (r) => r.uom || '—' },
    { key: 'rate', label: 'List price', cls: 'cell-num', render: (r) => fmtMoney(r.rate, r.currency) },
    { key: 'last_rate', label: 'Last charged', cls: 'cell-num', render: (r) => {
      if (r.last_rate == null) return <span className="text-ink-mute">Never bought</span>;
      const differs = r.rate && Math.abs(r.last_rate - r.rate) / r.rate > 0.005;
      return (
        <span className="inline-flex items-center gap-1.5" title={differs ? 'Charged differently from the list price' : undefined}>
          {differs && <span className="bdg bdg-warn">≠ list</span>}
          {fmtMoney(r.last_rate, r.last_currency || r.currency)}
        </span>
      );
    } },
    { key: 'last_date', label: 'On', cls: 'cell-id', render: (r) => (r.last_date ? fmtDate(r.last_date) : '—') },
  ];
  const total = data.total || 0;
  const pager = (
    <div className="flex items-center justify-between gap-3 px-5 py-3 border-t border-hairline text-[12.5px] text-ink-3">
      <span>{total ? `${fmt(start + 1)}–${fmt(Math.min(start + PAGE, total))} of ${fmt(total)}` : 'None'}</span>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" className="rounded-full" disabled={loading || start === 0} onClick={() => setStart(Math.max(0, start - PAGE))}>Previous</Button>
        <Button size="sm" variant="outline" className="rounded-full" disabled={loading || start + PAGE >= total} onClick={() => setStart(start + PAGE)}>Next</Button>
      </div>
    </div>
  );

  return (
    <>
      <div className="flex items-start gap-2.5 rounded-xl bg-info-soft text-info px-4 py-3 mb-4 text-[12.5px]">
        <Icon name="info" className="text-[16px] mt-px" />
        <span>
          Prices from price list <b>{data.price_list}</b>
          {data.source === 'customer_group' ? ", inherited from the customer's group" : ", set on this customer"}.
          {' '}“Last charged” is the rate on their most recent invoice for that item.
        </span>
      </div>
      <div className="mb-3 max-w-[320px]">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search items…" className="h-9" />
      </div>
      <DataTable title="Prices" subOverride={loading ? 'Loading…' : `${fmt(total)} items`} columns={columns}
        rows={data.rows} doctype="Item" rowName={(r) => r.item_code} emptyText="No items match" footer={pager} />
    </>
  );
}
