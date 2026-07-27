import { useStore } from '../store';

import { fmt, fmtDate, fmtMoney } from '@shared/utils';
import { KpiRow } from '../components/Kpi';
import ChartCard from '../components/ChartCard';
import DataTable from '../components/DataTable';
import EmailsTable from '../components/EmailsTable';
import { DoughnutChart, HBarsChart, AreaTrendChart } from '../charts/Charts';
import { isMine, MINE_FIELDS, currentUser } from '@/lib/crm';

const COLUMNS = [
  { key: 'customer_name', label: 'Name', render: (r) => r.customer_name || r.name },
  { key: 'customer_type', label: 'Type', render: (r) => r.customer_type || '—' },
  { key: 'customer_group', label: 'Group', render: (r) => r.customer_group || '—' },
  { key: 'territory', label: 'Territory', render: (r) => r.territory || '—' },
  { key: 'disabled', label: 'Status', render: (r) => (r.disabled ? <span className="bdg bdg-bad">Disabled</span> : <span className="bdg bdg-good">Active</span>) },
  { key: 'creation', label: 'Created', cls: 'cell-id', render: (r) => fmtDate(r.creation) },
];

// Revenue comes from `base_grand_total`, which is in the Company's default
// currency (KES here) — never assume USD.
const topColumns = (ccy) => [
  { key: 'rank', label: 'Rank', cls: 'cell-id', thStyle: { width: 60 }, render: (r) => r._rank },
  { key: 'customer', label: 'Customer' },
  { key: 'amount', label: `Revenue (${ccy})`, cls: 'cell-num', render: (r) => fmtMoney(r.amount, ccy) },
];

export default function Customers() {
  const { data, table } = useStore();
  const C = data.cust;
  if (!C) return <div className="crm-empty">No customers data</div>;

  if (table === 'rows' || table === 'mine') {
    const u = currentUser();
    const mine = table === 'mine';
    const rows = mine ? (C.rows || []).filter((r) => isMine(r, u, MINE_FIELDS.cust)) : (C.rows || []);
    return <DataTable title={mine ? 'My Customers' : 'All Customers'} columns={COLUMNS} rows={rows} doctype="Customer"
      searchFields={['name', 'customer_name', 'customer_type', 'customer_group', 'territory']}
      emptyText={mine ? (u ? 'No customers owned by or assigned to you' : 'Sign in to see your customers') : 'No customers'} />;
  }
  if (table === 'top') {
    const ccy = C.currency || 'KES';
    const rows = (C.top_revenue || []).map((r, i) => ({ ...r, _rank: String(i + 1).padStart(2, '0') }));
    return <DataTable title="Top Customers by Revenue" subOverride={`In selected range · ${ccy}`} columns={topColumns(ccy)}
      rows={rows} doctype="Customer" rowName={(r) => r.customer} emptyText="No invoice data in range" />;
  }
  if (table === 'emails') return <EmailsTable refType="Customer" />;

  const k = C.kpis;
  return (
    <>
      <KpiRow items={[
        { lbl: 'Total', val: fmt(k.total) }, { lbl: 'Active', val: fmt(k.active) }, { lbl: 'Disabled', val: fmt(k.disabled) },
        { lbl: 'Companies', val: fmt(k.companies) }, { lbl: 'Individuals', val: fmt(k.individuals) }, { lbl: 'New 30d', val: fmt(k.new_30d) },
      ]} />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <ChartCard title="Type Mix"><DoughnutChart items={C.type_mix} /></ChartCard>
        <ChartCard title="By Territory"><HBarsChart labels={(C.territory_mix || []).map((r) => r.label)} data={(C.territory_mix || []).map((r) => r.count)} /></ChartCard>
      </div>
      <ChartCard title="Acquisition Trend" sub="In selected range">
        <AreaTrendChart labels={(C.acquisition_trend || []).map((r) => r.label)} data={(C.acquisition_trend || []).map((r) => r.count)} />
      </ChartCard>
    </>
  );
}
