import { useStore } from '../store';
import { fmt, fmtDateTime } from '@shared/utils';
import { KpiRow } from '../components/Kpi';
import ChartCard from '../components/ChartCard';
import DataTable from '../components/DataTable';
import StatusBadge from '../components/StatusBadge';
import { HBarsChart, DoughnutChart } from '../charts/Charts';
import { shortUser } from '@/lib/crm';

const COLUMNS = [
  { key: 'activity_date', label: 'When', cls: 'cell-id', render: (r) => fmtDateTime(r.activity_date || r.communication_date) },
  { key: 'activity_type', label: 'Type', render: (r) => <span className="bdg bdg-open">{r.activity_type || r.communication_type || '—'}</span> },
  { key: 'subject', label: 'Subject', render: (r) => (r.subject || '—').slice(0, 70) },
  { key: 'reference', label: 'Reference', cls: 'cell-id', render: (r) => (r.reference_doctype && r.reference_name
    ? <>{r.reference_doctype}<br /><span className="text-ink-3 text-[9.5px]">{r.reference_name}</span></> : '—') },
  { key: 'customer', label: 'Customer', render: (r) => r.customer || '—' },
  { key: 'email_status', label: 'Status', render: (r) => <StatusBadge value={r.email_status} /> },
  { key: 'triggered_by', label: 'By', cls: 'cell-id', render: (r) => shortUser(r.triggered_by || r.sender) },
];

export default function Activity() {
  const { data, table } = useStore();
  const A = data.act;
  if (!A) return <div className="crm-empty">No data</div>;

  if (table === 'rows') {
    return <DataTable title="Recent Activity" columns={COLUMNS} rows={A.rows || []} doctype="CRM Activity Log"
      searchFields={['name', 'subject', 'activity_type', 'customer', 'triggered_by', 'email_status']} emptyText="No activity" />;
  }

  const k = A.kpis;
  const statusMix = [
    { label: 'Sent', count: k.sent }, { label: 'Failed', count: k.failed }, { label: 'Skipped', count: k.skipped },
  ].filter((r) => r.count > 0);
  return (
    <>
      <KpiRow items={[
        { lbl: 'Total', val: fmt(k.total) }, { lbl: 'Today', val: fmt(k.today) }, { lbl: 'Sent', val: fmt(k.sent) },
        { lbl: 'Failed', val: fmt(k.failed) }, { lbl: 'Skipped', val: fmt(k.skipped) }, { lbl: 'Types', val: fmt((A.by_type || []).length) },
      ]} />
      <div className="grid grid-cols-2 gap-2.5 mb-2.5">
        <ChartCard title="Activity by Type"><HBarsChart labels={(A.by_type || []).map((r) => r.label)} data={(A.by_type || []).map((r) => r.count)} /></ChartCard>
        <ChartCard title="Status Mix"><DoughnutChart items={statusMix} /></ChartCard>
      </div>
    </>
  );
}
