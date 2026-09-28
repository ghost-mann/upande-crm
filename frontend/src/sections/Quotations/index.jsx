import { useEffect, useState } from 'react';
import { fmt, fmtDate, fmtMoney } from '@shared/utils';
import { useStore } from '../../store';
import { KpiRow } from '../../components/Kpi';
import ChartCard from '../../components/ChartCard';
import DataTable from '../../components/DataTable';
import StatusBadge from '../../components/StatusBadge';
import { BarsChart, HBarsChart } from '../../charts/Charts';
import { quotationsDashboardApi } from '@/lib/service';

// Quotations from ERPNext: how many were sent, how many became orders, which
// are waiting on a follow-up, and what was offered. Creating the order stays in
// the desk (Quotation → Create → Sales Order), which is ERPNext's own mapping.
export function quotationColumns(currency, withParty = true) {
  return [
    { key: 'name', label: 'Quotation', cls: 'cell-id' },
    ...(withParty ? [{ key: 'party', label: 'For', render: (r) => (
      <span>{r.party || r.party_name}{r.quotation_to !== 'Customer' && <span className="text-ink-mute text-[11px]"> · {r.quotation_to}</span>}</span>
    ) }] : []),
    { key: 'transaction_date', label: 'Date', cls: 'cell-id', render: (r) => fmtDate(r.transaction_date) },
    { key: 'valid_till', label: 'Valid till', cls: 'cell-id', render: (r) => (r.valid_till ? fmtDate(r.valid_till) : '—') },
    { key: 'status', label: 'Status', render: (r) => (
      <span className="inline-flex items-center gap-1.5">
        <StatusBadge value={Number(r.docstatus) === 0 ? 'Draft' : r.status} />
        {r.followup && <span className="bdg bdg-warn">Follow up</span>}
      </span>
    ) },
    { key: 'base_grand_total', label: `Value (${currency})`, cls: 'cell-num', render: (r) => fmtMoney(r.base_grand_total, currency) },
    { key: 'orders', label: 'Became order', render: (r) => (r.orders?.length ? <span className="bdg bdg-good">{r.orders.join(', ')}</span> : '—') },
  ];
}

export default function Quotations() {
  const dateFrom = useStore((s) => s.dateFrom);
  const dateTo = useStore((s) => s.dateTo);
  const customer = useStore((s) => s.customerFilter);
  const table = useStore((s) => s.table);
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    let dead = false;
    setErr('');
    quotationsDashboardApi({ date_from: dateFrom, date_to: dateTo, customer: customer || undefined })
      .then((d) => { if (!dead) setData(d); }).catch((e) => { if (!dead) setErr(e.message || 'Could not load quotations'); });
    return () => { dead = true; };
  }, [dateFrom, dateTo, customer]);

  if (err) return <div className="crm-empty">{err}</div>;
  if (!data) return <div className="p-12 text-center text-ink-mute text-[13px]">Loading…</div>;
  if (!data.available) return <div className="crm-empty">You don't have access to quotations.</div>;
  const k = data.kpis;
  const ccy = data.currency;
  const rows = table === 'followup' ? data.rows.filter((r) => r.followup) : data.rows;

  if (table === 'rows' || table === 'followup') {
    return (
      <DataTable title={table === 'followup' ? 'Needs a follow-up' : 'Quotations'}
        subOverride={table === 'followup' ? `Open and older than ${data.followup_days} days, with no order yet` : `${fmt(rows.length)} in range`}
        columns={quotationColumns(ccy)} rows={rows} doctype="Quotation"
        searchFields={['name', 'party', 'party_name', 'status']} emptyText="No quotations here" />
    );
  }

  return (
    <>
      <KpiRow items={[
        { lbl: 'Sent', val: fmt(k.submitted), sub: k.drafts ? `${fmt(k.drafts)} still draft` : null },
        { lbl: 'Became orders', val: fmt(k.converted) },
        { lbl: 'Conversion', val: k.conversion_rate == null ? '—' : `${k.conversion_rate}%`,
          sub: k.conversion_rate === 0 ? 'no order points back at a quotation yet' : null },
        { lbl: 'Needs follow-up', val: fmt(k.needs_followup), chip: k.needs_followup ? `> ${data.followup_days} days` : null, chipTone: k.needs_followup ? 'down' : '' },
        { lbl: 'Average value', val: fmtMoney(k.avg_value, ccy) },
        { lbl: 'Median days to order', val: k.median_days_to_order == null ? '—' : fmt(Math.round(k.median_days_to_order)) },
      ]} />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <ChartCard title="Quotations sent per month" sub="Last 12 months">
          <BarsChart labels={data.trend.map((r) => r.label)} data={data.trend.map((r) => r.count)} />
        </ChartCard>
        <ChartCard title="Most quoted items" sub={`By quoted value · ${ccy}`}>
          <HBarsChart labels={data.top_items.map((r) => r.item_name || r.item_code)} data={data.top_items.map((r) => r.value)} money ccy={ccy} />
        </ChartCard>
      </div>
      <DataTable title="Recent quotations" subOverride="Click to open in the desk — create the sales order from there"
        columns={quotationColumns(ccy)} rows={data.rows.slice(0, 50)} doctype="Quotation"
        searchFields={['name', 'party', 'status']} emptyText="No quotations in this range" />
    </>
  );
}
