import { useState } from 'react';
import { fmtDate } from '@shared/utils';
import { useStore } from '../../store';
import DataTable from '../../components/DataTable';
import StatusBadge from '../../components/StatusBadge';
import Icon from '../../components/Icon';
import AssignControl from '../../components/AssignControl';
import { shortUser, isMine, MINE_FIELDS, currentUser } from '@/lib/crm';
import { parseAssign, stripHtml } from '@/lib/activity';

function CompleteToggle({ row, onError }) {
  const setTaskStatus = useStore((s) => s.setTaskStatus);
  const [busy, setBusy] = useState(false);
  const done = row.status === 'Closed';

  async function toggle(e) {
    e.stopPropagation();
    setBusy(true);
    try {
      await setTaskStatus(row.name, done ? 'Open' : 'Closed');
      onError('');
    } catch (err) {
      // The backend refuses when the user is neither assignee nor manager; the
      // store has already rolled the row back, so just surface why.
      onError(err.message || 'Could not update the task');
    } finally {
      setBusy(false);
    }
  }

  return (
    <input
      type="checkbox"
      checked={done}
      disabled={busy}
      onClick={(e) => e.stopPropagation()}
      onChange={toggle}
      title={done ? 'Reopen task' : 'Mark complete'}
      className="h-3.5 w-3.5 rounded border-input accent-[var(--good)] cursor-pointer"
    />
  );
}

export default function TasksTable({ mine }) {
  const E = useStore((s) => s.data.evt);
  const openTaskDialog = useStore((s) => s.openTaskDialog);
  const [err, setErr] = useState('');
  const u = currentUser();
  const all = E?.todos || [];
  const rows = mine ? all.filter((r) => isMine(r, u, MINE_FIELDS.todos)) : all;

  const columns = [
    { key: 'done', label: '', thStyle: { width: 34 }, render: (r) => <CompleteToggle row={r} onError={setErr} /> },
    {
      key: 'ref',
      label: 'Ref',
      cls: 'cell-id',
      render: (r) => (
        <>{r.reference_type || 'Task'}<br />
          <span className="text-ink-3 text-[9.5px]">{r.reference_name || r.name || ''}</span>
        </>
      ),
    },
    { key: 'description', label: 'Description', render: (r) => stripHtml(r.description).slice(0, 110) || '—' },
    { key: 'date', label: 'Due', cls: 'cell-id', render: (r) => (r.date ? fmtDate(r.date) : '—') },
    { key: 'priority', label: 'Priority', render: (r) => <StatusBadge value={r.priority} /> },
    { key: 'allocated_to', label: 'Assignee', cls: 'cell-id', render: (r) => shortUser(r.allocated_to) || '—' },
    { key: 'status', label: 'Status', render: (r) => <StatusBadge value={r.status} /> },
    {
      key: '_assign',
      label: 'Record assigned',
      // Assignment belongs to the *referenced* record, not the task itself — a
      // task's own assignee is its allocated_to field.
      render: (r) => (r.reference_type && r.reference_name
        ? <AssignControl doctype={r.reference_type} name={r.reference_name} assigned={parseAssign(r._assign)} />
        : <span className="text-ink-mute text-[11px]">—</span>),
    },
    {
      key: 'actions',
      label: '',
      render: (r) => (
        <button className="text-ink-3 hover:text-ink" title="Edit task"
          onClick={(e) => { e.stopPropagation(); openTaskDialog(r); }}>
          <Icon name="edit" className="text-[16px]" />
        </button>
      ),
    },
  ];

  return (
    <>
      {err && <div className="mb-3 text-[12px] text-bad">{err}</div>}
      <DataTable
        title={mine ? 'My Tasks' : 'CRM Tasks'}
        subOverride={undefined}
        columns={columns}
        rows={rows}
        doctype={(r) => (r.reference_type && r.reference_name ? r.reference_type : null)}
        rowName={(r) => (r.reference_type && r.reference_name ? r.reference_name : r.name)}
        searchFields={['name', 'description', 'priority', 'allocated_to', 'status', 'reference_type', 'reference_name']}
        emptyText={mine ? (u ? 'No tasks assigned to you' : 'Sign in to see your tasks') : 'No CRM tasks'}
      />
    </>
  );
}
