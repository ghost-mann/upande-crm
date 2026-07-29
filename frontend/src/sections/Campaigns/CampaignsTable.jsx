import { fmtDate } from '@shared/utils';
import { useStore } from '../../store';
import DataTable from '../../components/DataTable';
import Icon from '../../components/Icon';
import { shortUser } from '@/lib/crm';
import { durationLabel } from '@/lib/campaigns';

export default function CampaignsTable() {
  const d = useStore((s) => s.data.campaigns);
  const openCampaignDialog = useStore((s) => s.openCampaignDialog);
  const openEnrolDialog = useStore((s) => s.openEnrolDialog);
  const rows = d?.campaigns || [];

  const columns = [
    { key: 'title', label: 'Campaign', render: (r) => (
      <>
        {r.title}
        {!r.steps && <span className="bdg bdg-bad ml-2">no schedule</span>}
      </>
    ) },
    { key: 'steps', label: 'Steps', cls: 'cell-id', render: (r) => (
      r.steps ? `${r.steps} · ${durationLabel(r.duration_days)}` : '—'
    ) },
    { key: 'schedule', label: 'Sequence', render: (r) => (
      r.schedule?.length
        ? <span className="text-[11.5px] text-ink-2">
            {r.schedule.map((s) => `${s.email_template} (d${s.send_after_days})`).join(' → ')}
          </span>
        : <span className="text-ink-mute text-[11px]">—</span>
    ) },
    { key: 'enrolled', label: 'Enrolled', cls: 'cell-id' },
    { key: 'active', label: 'Running', cls: 'cell-id', render: (r) => (
      r.active ? <span className="bdg bdg-open">{r.active}</span> : '—'
    ) },
    { key: 'attributed_leads', label: 'Leads tagged', cls: 'cell-id', render: (r) => (
      r.attributed_leads ? `${r.attributed_leads} · ${r.attributed_converted} won` : '—'
    ) },
    { key: 'owner', label: 'Created by', cls: 'cell-id', render: (r) => shortUser(r.owner) },
    { key: 'creation', label: 'Created', cls: 'cell-id', render: (r) => fmtDate(r.creation) },
    { key: 'actions', label: '', render: (r) => (
      <span className="flex items-center gap-1.5">
        <button className="text-ink-3 hover:text-gold-text" title="Enrol recipients"
          onClick={(e) => { e.stopPropagation(); openEnrolDialog({ campaign: r.name }); }}>
          <Icon name="send" className="text-[16px]" />
        </button>
        <button className="text-ink-3 hover:text-ink" title="Edit campaign"
          onClick={(e) => { e.stopPropagation(); openCampaignDialog(r); }}>
          <Icon name="edit" className="text-[16px]" />
        </button>
      </span>
    ) },
  ];

  return (
    <DataTable
      title="Campaigns" columns={columns} rows={rows}
      searchFields={['title', 'description', 'owner']}
      emptyText="No campaigns yet — create one to define a drip sequence"
    />
  );
}
