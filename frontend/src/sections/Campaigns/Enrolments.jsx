import { useState } from 'react';
import { fmtDate } from '@shared/utils';
import { useStore } from '../../store';
import DataTable from '../../components/DataTable';
import StatusBadge from '../../components/StatusBadge';
import Icon from '../../components/Icon';
import { openFrappe, shortUser, currentUser } from '@/lib/crm';
import { TARGET_ICON } from '@/lib/campaigns';

export default function Enrolments({ mine }) {
  const d = useStore((s) => s.data.campaigns);
  const cancelEnrolment = useStore((s) => s.cancelEnrolment);
  const newTab = useStore((s) => s.settings.openInNewTab);
  const [err, setErr] = useState('');
  const u = currentUser();
  const all = d?.enrolments || [];
  const rows = mine ? all.filter((r) => String(r.owner || '').toLowerCase() === u) : all;

  async function cancel(row) {
    setErr('');
    try {
      await cancelEnrolment(row.name);
    } catch (e) {
      setErr(e.message || 'Could not cancel that enrolment');
    }
  }

  const columns = [
    { key: 'for', label: '', thStyle: { width: 34 }, render: (r) => (
      <Icon name={TARGET_ICON[r.email_campaign_for] || 'mail'} className="text-[16px] text-ink-3" />
    ) },
    { key: 'campaign_title', label: 'Campaign' },
    { key: 'recipient', label: 'Recipient', cls: 'cell-id', render: (r) => (
      r.email_campaign_for === 'Email Group' ? r.recipient : (
        <button className="text-gold-text hover:underline text-left"
          onClick={(e) => { e.stopPropagation(); openFrappe(r.email_campaign_for, r.recipient, newTab); }}>
          {r.recipient}
        </button>
      )
    ) },
    { key: 'status', label: 'Status', render: (r) => <StatusBadge value={r.status} /> },
    { key: 'start_date', label: 'Starts', cls: 'cell-id', render: (r) => fmtDate(r.start_date) },
    { key: 'end_date', label: 'Last email', cls: 'cell-id', render: (r) => fmtDate(r.end_date) },
    { key: 'sender', label: 'Sender', cls: 'cell-id', render: (r) => shortUser(r.sender) },
    { key: 'owner', label: 'Enrolled by', cls: 'cell-id', render: (r) => shortUser(r.owner) },
    { key: 'actions', label: '', render: (r) => (
      <button className="text-ink-3 hover:text-bad" title="Cancel this enrolment"
        onClick={(e) => { e.stopPropagation(); cancel(r); }}>
        <Icon name="delete" className="text-[16px]" />
      </button>
    ) },
  ];

  return (
    <>
      {err && <div className="mb-3 text-[12px] text-bad">{err}</div>}
      <DataTable
        title={mine ? 'My enrolments' : 'Enrolments'} columns={columns} rows={rows}
        searchFields={['campaign_title', 'recipient', 'status', 'sender', 'owner']}
        emptyText={mine ? 'You have not enrolled anyone yet' : 'Nothing enrolled yet'}
      />
    </>
  );
}
