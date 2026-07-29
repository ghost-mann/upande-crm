import { fmt } from '@shared/utils';
import { useStore } from '../../store';
import DataTable from '../../components/DataTable';
import Icon from '../../components/Icon';

// Email Groups, the audiences a campaign can be sent to. Read-only here: group
// membership is bulk data managed in desk, and a CRM UI for editing 10,000 rows
// would be a worse tool than the one that already exists.
export default function Audiences() {
  const d = useStore((s) => s.data.campaigns);
  const openEnrolDialog = useStore((s) => s.openEnrolDialog);
  const rows = d?.audiences || [];

  const columns = [
    { key: 'name', label: 'Audience' },
    { key: 'active', label: 'Active subscribers', cls: 'cell-id', render: (r) => fmt(r.active) },
    { key: 'unsubscribed', label: 'Unsubscribed', cls: 'cell-id', render: (r) => (
      r.unsubscribed ? <span className="text-warn">{fmt(r.unsubscribed)}</span> : '—'
    ) },
    { key: 'total', label: 'Total', cls: 'cell-id', render: (r) => fmt(r.total) },
    { key: 'actions', label: '', render: (r) => (
      <button className="text-ink-3 hover:text-gold-text" title="Send a campaign to this audience"
        onClick={(e) => { e.stopPropagation(); openEnrolDialog({ target: 'Email Group' }); }}>
        <Icon name="send" className="text-[16px]" />
      </button>
    ) },
  ];

  return (
    <>
      <DataTable title="Audiences" columns={columns} rows={rows}
        searchFields={['name']} emptyText="No email groups exist yet" />
      <div className="mt-3 text-[11.5px] text-ink-mute">
        Membership is managed in desk — these lists run to thousands of rows, which a CRM
        table would handle worse than the tool that already exists.
      </div>
    </>
  );
}
