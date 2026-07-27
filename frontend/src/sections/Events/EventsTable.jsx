import { useState } from 'react';
import { fmtDateTime } from '@shared/utils';
import { useStore } from '../../store';
import DataTable from '../../components/DataTable';
import StatusBadge from '../../components/StatusBadge';
import Icon from '../../components/Icon';
import AssignControl from '../../components/AssignControl';
import { shortUser, isMine, MINE_FIELDS, currentUser } from '@/lib/crm';
import { parseAssign } from '@/lib/activity';

const DONE = new Set(['Completed', 'Closed', 'Cancelled']);

function RowActions({ row, onError }) {
  const openEventDialog = useStore((s) => s.openEventDialog);
  const setEventStatus = useStore((s) => s.setEventStatus);
  const [busy, setBusy] = useState(false);

  async function complete(e) {
    e.stopPropagation();
    setBusy(true);
    try { await setEventStatus(row.name, 'Completed'); onError(''); }
    catch (err) { onError(err.message || 'Could not update the event'); }
    finally { setBusy(false); }
  }

  return (
    <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
      <button className="text-ink-3 hover:text-ink" title="Edit event"
        onClick={(e) => { e.stopPropagation(); openEventDialog(row); }}>
        <Icon name="edit" className="text-[16px]" />
      </button>
      {!DONE.has(row.status) && (
        <button className="text-ink-3 hover:text-good disabled:opacity-40" title="Mark completed"
          disabled={busy} onClick={complete}>
          <Icon name="check_circle" className="text-[16px]" />
        </button>
      )}
    </div>
  );
}

export default function EventsTable({ mine }) {
  const E = useStore((s) => s.data.evt);
  const [err, setErr] = useState('');
  const u = currentUser();
  const all = E?.events || [];
  const rows = mine ? all.filter((r) => isMine(r, u, MINE_FIELDS.events)) : all;

  const columns = [
    { key: 'name', label: 'ID', cls: 'cell-id' },
    { key: 'subject', label: 'Subject', render: (r) => r.subject || '—' },
    { key: 'event_category', label: 'Category', render: (r) => r.event_category || '—' },
    { key: 'starts_on', label: 'Starts', cls: 'cell-id', render: (r) => fmtDateTime(r.starts_on) },
    { key: 'status', label: 'Status', render: (r) => <StatusBadge value={r.status} /> },
    { key: 'owner', label: 'Owner', cls: 'cell-id', render: (r) => shortUser(r.owner) },
    {
      key: '_assign',
      label: 'Assigned',
      render: (r) => <AssignControl doctype="Event" name={r.name} assigned={parseAssign(r._assign)} />,
    },
    { key: 'actions', label: '', render: (r) => <RowActions row={r} onError={setErr} /> },
  ];

  return (
    <>
      {err && <div className="mb-3 text-[12px] text-bad">{err}</div>}
      <DataTable
        title={mine ? 'My Events' : 'All Events'}
        columns={columns}
        rows={rows}
        doctype="Event"
        searchFields={['name', 'subject', 'event_category', 'status', 'owner', 'location']}
        emptyText={mine ? (u ? 'No events owned by or assigned to you' : 'Sign in to see your events') : 'No events'}
      />
    </>
  );
}
