import { useStore } from '../store';
import { fmt, fmtDate } from '@shared/utils';
import { KpiRow } from '../components/Kpi';
import ChartCard from '../components/ChartCard';
import DataTable from '../components/DataTable';
import EmailsTable from '../components/EmailsTable';
import StatusBadge from '../components/StatusBadge';
import { BarsChart, DoughnutChart, HBarsChart } from '../charts/Charts';
import { shortUser, isMine, MINE_FIELDS, currentUser } from '@/lib/crm';

const COLUMNS = [
  { key: 'name', label: 'ID', cls: 'cell-id' },
  { key: 'lead_name', label: 'Name', render: (r) => r.lead_name || '—' },
  { key: 'company_name', label: 'Company', render: (r) => r.company_name || '—' },
  { key: 'status', label: 'Status', render: (r) => <StatusBadge value={r.status} /> },
  { key: 'qualification_status', label: 'Qual.', render: (r) => <StatusBadge value={r.qualification_status} /> },
  { key: 'territory', label: 'Territory', render: (r) => r.territory || '—' },
  { key: 'source', label: 'Source', render: (r) => r.source || '—' },
  { key: 'lead_owner', label: 'Owner', cls: 'cell-id', render: (r) => shortUser(r.lead_owner) },
  { key: 'creation', label: 'Created', cls: 'cell-id', render: (r) => fmtDate(r.creation) },
];

export default function Leads() {
  const { data, table } = useStore();
  const L = data.leads;
  if (!L) return <div className="crm-empty">No leads data</div>;
  if (table === 'rows' || table === 'mine') {
    const u = currentUser();
    const mine = table === 'mine';
    const rows = mine ? (L.rows || []).filter((r) => isMine(r, u, MINE_FIELDS.leads)) : (L.rows || []);
    return <DataTable title={mine ? 'My Leads' : 'All Leads'} columns={COLUMNS} rows={rows} doctype="Lead"
      searchFields={['name', 'lead_name', 'company_name', 'territory', 'source', 'status']}
      emptyText={mine ? (u ? 'No leads owned by or assigned to you' : 'Sign in to see your leads') : 'No leads'} />;
  }
  if (table === 'emails') return <EmailsTable refType="Lead" />;

  const k = L.kpis;
  return (
    <>
      <KpiRow items={[
        { lbl: 'Total', val: fmt(k.total) }, { lbl: 'Open', val: fmt(k.open) }, { lbl: '→ Opp', val: fmt(k.to_opp) },
        { lbl: '→ Quotation', val: fmt(k.to_quot) }, { lbl: 'Converted', val: fmt(k.converted) },
        { lbl: 'Conv. Rate', val: k.conv_rate, suffix: '%' },
      ]} />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <ChartCard title="Status"><BarsChart labels={(L.status_mix || []).map((r) => r.label)} data={(L.status_mix || []).map((r) => r.count)} /></ChartCard>
        <ChartCard title="Qualification"><DoughnutChart items={L.qual_mix} /></ChartCard>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <ChartCard title="Owner Workload"><HBarsChart labels={(L.owner_workload || []).map((r) => r.label)} data={(L.owner_workload || []).map((r) => r.count)} /></ChartCard>
        <ChartCard title="Geography"><HBarsChart labels={(L.geography || []).map((r) => r.label)} data={(L.geography || []).map((r) => r.count)} /></ChartCard>
      </div>
    </>
  );
}
