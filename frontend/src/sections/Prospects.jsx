import { useStore } from '../store';
import { fmt, fmtDate } from '@shared/utils';
import { KpiRow } from '../components/Kpi';
import ChartCard from '../components/ChartCard';
import DataTable from '../components/DataTable';
import EmailsTable from '../components/EmailsTable';
import { DoughnutChart, HBarsChart } from '../charts/Charts';

const COLUMNS = [
  { key: 'company_name', label: 'Company', render: (r) => r.company_name || r.name },
  { key: 'industry', label: 'Industry', render: (r) => r.industry || '—' },
  { key: 'territory', label: 'Territory', render: (r) => r.territory || '—' },
  { key: 'no_of_employees', label: 'Size', render: (r) => r.no_of_employees || '—' },
  { key: 'opp_count', label: 'Opps', cls: 'cell-num', render: (r) => r.opp_count || 0 },
  { key: 'is_customer', label: '→ Cust', render: (r) => (r.is_customer ? <span className="bdg bdg-good">Yes</span> : <span className="bdg bdg-other">No</span>) },
  { key: 'creation', label: 'Created', cls: 'cell-id', render: (r) => fmtDate(r.creation) },
];

export default function Prospects() {
  const { data, table } = useStore();
  const P = data.prosp;
  if (!P) return <div className="crm-empty">No prospects data</div>;
  if (table === 'rows') {
    return <DataTable title="All Prospects" columns={COLUMNS} rows={P.rows || []} doctype="Prospect"
      searchFields={['name', 'company_name', 'industry', 'territory']} emptyText="No prospects" />;
  }
  if (table === 'emails') return <EmailsTable refType="Prospect" />;

  const k = P.kpis;
  return (
    <>
      <KpiRow items={[
        { lbl: 'Total', val: fmt(k.total) }, { lbl: 'With Opps', val: fmt(k.with_opp) }, { lbl: '→ Customer', val: fmt(k.to_customer) },
        { lbl: 'Conv. Rate', val: k.conv_rate, suffix: '%' }, { lbl: 'Territories', val: fmt(k.territories) }, { lbl: 'This Quarter', val: fmt(k.this_quarter) },
      ]} />
      <div className="grid grid-cols-3 gap-2.5 mb-2.5">
        <ChartCard title="By Territory" height="h-[200px]"><HBarsChart labels={P.territory_mix.map((r) => r.label)} data={P.territory_mix.map((r) => r.count)} /></ChartCard>
        <ChartCard title="Company Size" height="h-[200px]"><DoughnutChart items={P.size_mix} /></ChartCard>
        <ChartCard title="Industries" height="h-[200px]"><HBarsChart labels={(P.industry_mix || []).map((r) => r.label)} data={(P.industry_mix || []).map((r) => r.count)} /></ChartCard>
      </div>
    </>
  );
}
