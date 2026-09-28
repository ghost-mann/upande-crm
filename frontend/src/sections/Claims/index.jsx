import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { fmt, fmtDate, fmtMoney } from '@shared/utils';
import { useStore } from '../../store';
import Icon from '../../components/Icon';
import { KpiRow } from '../../components/Kpi';
import ChartCard from '../../components/ChartCard';
import DataTable from '../../components/DataTable';
import ClaimDialog from '../../components/ClaimDialog';
import { HBarsChart, DoughnutChart } from '../../charts/Charts';
import { claimsDashboardApi, CLAIM_TONE } from '@/lib/service';

// Complaints and quality claims: what is open, what is overdue against the
// resolve-within target in Settings, and how fast claims close.
export function claimColumns(currency, withCustomer = true) {
  return [
    { key: 'name', label: 'Claim', cls: 'cell-id' },
    ...(withCustomer ? [{ key: 'customer', label: 'Customer' }] : []),
    { key: 'claim_type', label: 'Type' },
    { key: 'status', label: 'Status', render: (r) => (
      <span className="inline-flex items-center gap-1.5">
        <span className={`bdg ${CLAIM_TONE[r.status] || 'bdg-other'}`}>{r.status}</span>
        {r.overdue && <span className="bdg bdg-bad">Overdue</span>}
      </span>
    ) },
    { key: 'raised_on', label: 'Raised', cls: 'cell-id', render: (r) => fmtDate(r.raised_on) },
    { key: 'age_days', label: 'Age', cls: 'cell-num', render: (r) => (r.age_days == null ? '—' : `${r.age_days}d`) },
    { key: 'reference_name', label: 'Against', render: (r) => r.reference_name || '—' },
    { key: 'amount_claimed', label: `Claimed (${currency})`, cls: 'cell-num', render: (r) => (r.amount_claimed ? fmtMoney(r.amount_claimed, currency) : '—') },
    { key: 'amount_credited', label: 'Credited', cls: 'cell-num', render: (r) => (r.amount_credited ? fmtMoney(r.amount_credited, currency) : '—') },
  ];
}

export default function Claims() {
  const dateFrom = useStore((s) => s.dateFrom);
  const dateTo = useStore((s) => s.dateTo);
  const customer = useStore((s) => s.customerFilter);
  const table = useStore((s) => s.table);
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const [dialog, setDialog] = useState(null);

  const load = useCallback(() => {
    setErr('');
    claimsDashboardApi({ date_from: dateFrom, date_to: dateTo, customer: customer || undefined })
      .then(setData).catch((e) => setErr(e.message || 'Could not load claims'));
  }, [dateFrom, dateTo, customer]);
  useEffect(() => { load(); }, [load]);

  if (err) return <div className="crm-empty">{err}</div>;
  if (!data) return <div className="p-12 text-center text-ink-mute text-[13px]">Loading…</div>;
  if (!data.available) return <div className="crm-empty">Claims are not available — run bench migrate, or ask for access to CRM Claim.</div>;

  const k = data.kpis;
  const ccy = data.currency;
  const rows = table === 'open' ? data.rows.filter((r) => r.status === 'Open' || r.status === 'Under Review') : data.rows;
  const open = (r) => setDialog(r ? { ...r } : (customer ? { customer } : {}));

  return (
    <>
      <div className="flex items-center gap-2.5 mb-5 flex-wrap">
        <Button size="sm" onClick={() => open(null)}
          className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-4">
          <Icon name="report" className="text-[16px]" />Log a claim
        </Button>
        <span className="text-[12px] text-ink-mute">Open claims older than {data.sla_days} days are flagged overdue (CRM Settings → Claims).</span>
      </div>

      {table !== 'rows' && table !== 'open' && (
        <>
          <KpiRow items={[
            { lbl: 'Open', val: fmt(k.open) },
            { lbl: 'Under review', val: fmt(k.under_review) },
            { lbl: 'Overdue', val: fmt(k.overdue), chip: k.overdue ? 'needs action' : null, chipTone: k.overdue ? 'down' : '' },
            { lbl: 'Resolved in range', val: fmt(k.resolved), sub: k.rejected ? `${fmt(k.rejected)} rejected` : null },
            { lbl: 'Median days to close', val: k.median_days_to_close == null ? '—' : fmt(Math.round(k.median_days_to_close)) },
            { lbl: 'Claimed / credited', val: fmtMoney(k.claimed, ccy), sub: `${fmtMoney(k.credited, ccy)} credited` },
          ]} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <ChartCard title="Claims by type" sub="Raised in the selected range">
              <HBarsChart labels={data.by_type.map((r) => r.label)} data={data.by_type.map((r) => r.count)} />
            </ChartCard>
            <ChartCard title="By status" sub="Raised in the selected range">
              <DoughnutChart items={data.by_status} />
            </ChartCard>
          </div>
        </>
      )}

      <DataTable title={table === 'open' ? 'Open claims' : 'Claims'} subOverride={`${fmt(rows.length)} shown · overdue first`}
        columns={claimColumns(ccy)} rows={rows} onRowClick={open}
        searchFields={['name', 'customer', 'claim_type', 'status', 'reference_name']}
        emptyText="No claims — log one when a customer complains" />

      {dialog && <ClaimDialog claim={dialog} types={data.types} onClose={() => setDialog(null)} onSaved={load} />}
    </>
  );
}
