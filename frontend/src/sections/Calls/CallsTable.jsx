import { fmtDateTime } from '@shared/utils';
import { useStore } from '../../store';
import DataTable from '../../components/DataTable';
import StatusBadge from '../../components/StatusBadge';
import Icon from '../../components/Icon';
import { shortUser, currentUser, openFrappe } from '@/lib/crm';
import { fmtDuration, MISSED_STATUSES } from '@/lib/calls';

export default function CallsTable({ mine }) {
  const data = useStore((s) => s.data.calls);
  const openCallDialog = useStore((s) => s.openCallDialog);
  const newTab = useStore((s) => s.settings.openInNewTab);
  const u = currentUser();
  const all = data?.rows || [];
  const rows = mine ? all.filter((r) => String(r.owner || '').toLowerCase() === u) : all;

  const columns = [
    {
      key: 'type',
      label: '',
      thStyle: { width: 34 },
      render: (r) => (
        <Icon
          name={r.type === 'Incoming' ? 'call_received' : 'call_made'}
          className={`text-[16px] ${MISSED_STATUSES.has(r.status) ? 'text-bad' : r.type === 'Incoming' ? 'text-bio' : 'text-ink-3'}`}
        />
      ),
    },
    {
      key: 'party',
      label: 'Number',
      cls: 'cell-id',
      render: (r) => r.to || r.from || '—',
    },
    { key: 'start_time', label: 'When', cls: 'cell-id', render: (r) => (r.start_time ? fmtDateTime(r.start_time) : '—') },
    { key: 'duration', label: 'Duration', cls: 'cell-id', render: (r) => fmtDuration(r.duration) },
    { key: 'status', label: 'Outcome', render: (r) => <StatusBadge value={r.status} /> },
    { key: 'type_of_call', label: 'Type', render: (r) => r.type_of_call || '—' },
    {
      key: 'reference',
      label: 'Linked to',
      render: (r) => (r.reference_doctype && r.reference_name ? (
        <button
          className="text-gold-text hover:underline text-left"
          onClick={(e) => { e.stopPropagation(); openFrappe(r.reference_doctype, r.reference_name, newTab); }}
          title={`${r.reference_doctype} · ${r.reference_name}`}
        >
          {r.reference_name}
        </button>
      ) : <span className="text-ink-mute text-[11px]">—</span>),
    },
    { key: 'summary', label: 'Summary', render: (r) => (r.summary || '').slice(0, 90) || '—' },
    { key: 'owner', label: 'Logged by', cls: 'cell-id', render: (r) => shortUser(r.owner) || '—' },
    {
      key: 'actions',
      label: '',
      render: (r) => (
        <button className="text-ink-3 hover:text-ink" title="Edit call"
          onClick={(e) => { e.stopPropagation(); openCallDialog(r); }}>
          <Icon name="edit" className="text-[16px]" />
        </button>
      ),
    },
  ];

  return (
    <DataTable
      title={mine ? 'My calls' : 'Call log'}
      columns={columns}
      rows={rows}
      searchFields={['to', 'from', 'summary', 'status', 'type_of_call', 'owner', 'reference_name']}
      emptyText={mine ? (u ? 'You have not logged any calls in this range' : 'Sign in to see your calls')
        : 'No calls logged in this range'}
    />
  );
}
