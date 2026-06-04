import { useStore } from '../store';
import { fmt, fmtDate } from '@shared/utils';
import { KpiRow } from '../components/Kpi';
import ChartCard from '../components/ChartCard';
import Stages from '../components/Stages';
import DataTable from '../components/DataTable';
import EmailsTable from '../components/EmailsTable';
import StatusBadge from '../components/StatusBadge';
import { DoughnutChart, HBarsChart } from '../charts/Charts';
import { isMine, MINE_FIELDS, currentUser } from '@/lib/crm';

const COLUMNS = [
  { key: 'name', label: 'ID', cls: 'cell-id' },
  { key: 'customer', label: 'Customer', render: (r) => r.customer_name || r.party_name || '—' },
  { key: 'opportunity_from', label: 'From', render: (r) => r.opportunity_from || '—' },
  { key: 'status', label: 'Status', render: (r) => <StatusBadge value={r.status} /> },
  { key: 'sales_stage', label: 'Stage', render: (r) => r.sales_stage || '—' },
  { key: 'probability', label: 'Prob.', cls: 'cell-num', render: (r) => `${r.probability || 0}%` },
  { key: 'territory', label: 'Territory', render: (r) => r.territory || '—' },
  { key: 'source', label: 'Source', render: (r) => r.source || '—' },
  { key: 'created', label: 'Created', cls: 'cell-id', render: (r) => fmtDate(r.transaction_date || r.creation) },
];

export default function Opportunities() {
  const { data, table } = useStore();
  const O = data.opps;
  if (!O) return <div className="crm-empty">No opportunities data</div>;
  if (table === 'rows' || table === 'mine') {
    const u = currentUser();
    const mine = table === 'mine';
    const rows = mine ? (O.rows || []).filter((r) => isMine(r, u, MINE_FIELDS.opps)) : (O.rows || []);
    return <DataTable title={mine ? 'My Opportunities' : 'All Opportunities'} columns={COLUMNS} rows={rows} doctype="Opportunity"
      searchFields={['name', 'customer_name', 'party_name', 'territory', 'source', 'status', 'sales_stage']}
      emptyText={mine ? (u ? 'No opportunities owned by or assigned to you' : 'Sign in to see your opportunities') : 'No opportunities'} />;
  }
  if (table === 'emails') return <EmailsTable refType="Opportunity" />;

  const k = O.kpis;
  return (
    <>
      <KpiRow items={[
        { lbl: 'Total', val: fmt(k.total) }, { lbl: 'Open', val: fmt(k.open) }, { lbl: 'Converted', val: fmt(k.converted) },
        { lbl: 'Lost', val: fmt(k.lost) }, { lbl: 'Win Rate', val: k.win_rate, suffix: '%' }, { lbl: 'From Prospect', val: fmt(k.from_prospect) },
      ]} />
      <div className="mb-2.5"><Stages stages={O.pipeline || []} total={k.total} /></div>
      <div className="grid grid-cols-2 gap-2.5 mb-2.5">
        <ChartCard title="Status Mix"><DoughnutChart items={O.status_mix} /></ChartCard>
        <ChartCard title="By Territory"><HBarsChart labels={O.territory_mix.map((r) => r.label)} data={O.territory_mix.map((r) => r.count)} /></ChartCard>
      </div>
    </>
  );
}
