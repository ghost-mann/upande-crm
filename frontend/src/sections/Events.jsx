import { useStore } from '../store';
import { fmt, fmtDateTime } from '@shared/utils';
import { KpiRow } from '../components/Kpi';
import ChartCard from '../components/ChartCard';
import DataTable from '../components/DataTable';
import EmailsTable from '../components/EmailsTable';
import StatusBadge from '../components/StatusBadge';
import { BarsChart, DoughnutChart } from '../charts/Charts';
import { shortUser } from '@/lib/crm';

const EVENT_COLUMNS = [
  { key: 'name', label: 'ID', cls: 'cell-id' },
  { key: 'subject', label: 'Subject', render: (r) => r.subject || '—' },
  { key: 'event_category', label: 'Category', render: (r) => r.event_category || '—' },
  { key: 'starts_on', label: 'Starts', cls: 'cell-id', render: (r) => fmtDateTime(r.starts_on) },
  { key: 'status', label: 'Status', render: (r) => <StatusBadge value={r.status} /> },
  { key: 'owner', label: 'Owner', cls: 'cell-id', render: (r) => shortUser(r.owner) },
];

const TODO_COLUMNS = [
  { key: 'ref', label: 'Ref', cls: 'cell-id', render: (r) => (
    <>{r.reference_type || 'ToDo'}<br /><span className="text-ink-3 text-[9.5px]">{r.reference_name || r.name || ''}</span></>
  ) },
  { key: 'description', label: 'Description', render: (r) => stripHtml(r.description).slice(0, 110) || '—' },
  { key: 'priority', label: 'Priority', render: (r) => <StatusBadge value={r.priority} /> },
  { key: 'allocated_to', label: 'Assigned', cls: 'cell-id', render: (r) => shortUser(r.allocated_to) },
  { key: 'status', label: 'Status', render: (r) => <StatusBadge value={r.status} /> },
];

function stripHtml(s) { return String(s || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim(); }

export default function Events() {
  const { data, table } = useStore();
  const E = data.evt;
  if (!E) return <div className="crm-empty">No data</div>;

  if (table === 'events') {
    return <DataTable title="All Events" columns={EVENT_COLUMNS} rows={E.events || []} doctype="Event"
      searchFields={['name', 'subject', 'event_category', 'status', 'owner']} emptyText="No events" />;
  }
  if (table === 'todos') {
    return <DataTable title="ToDos" columns={TODO_COLUMNS} rows={E.todos || []}
      doctype={(r) => (r.reference_type && r.reference_name ? r.reference_type : 'ToDo')}
      rowName={(r) => (r.reference_type && r.reference_name ? r.reference_name : r.name)}
      searchFields={['name', 'description', 'priority', 'allocated_to', 'status', 'reference_type', 'reference_name']} emptyText="No tasks" />;
  }
  if (table === 'emails') return <EmailsTable refType={null} />;

  const k = E.kpis;
  return (
    <>
      <KpiRow items={[
        { lbl: 'Events', val: fmt(k.events_total) }, { lbl: 'Open Events', val: fmt(k.events_open) }, { lbl: 'Open Tasks', val: fmt(k.tasks_open) },
        { lbl: 'High Priority', val: fmt(k.tasks_high) }, { lbl: 'Sent', val: fmt(k.emails_sent || 0) }, { lbl: 'Received', val: fmt(k.emails_recv || 0) },
      ]} />
      <div className="grid grid-cols-3 gap-2.5 mb-2.5">
        <ChartCard title="Event Categories" height="h-[200px]"><BarsChart labels={E.event_categories.map((r) => r.label)} data={E.event_categories.map((r) => r.count)} /></ChartCard>
        <ChartCard title="Task Priorities" height="h-[200px]"><DoughnutChart items={E.task_priorities} /></ChartCard>
        <ChartCard title="Emails by Reference" height="h-[200px]"><DoughnutChart items={E.email_by_ref || []} /></ChartCard>
      </div>
    </>
  );
}
