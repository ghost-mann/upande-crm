import { fmtDate } from '@shared/utils';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { useStore } from '../../store';
import { openFrappe, shortUser, badgeClass } from '@/lib/crm';
import Icon from '../../components/Icon';

// Bucket → how the group reads. Overdue leads, because it is the only group that
// is already a problem.
const GROUPS = [
  ['overdue', 'Overdue', 'text-bad'],
  ['today', 'Today', 'text-ink'],
  ['tomorrow', 'Tomorrow', 'text-ink-2'],
  ['week', 'This week', 'text-ink-3'],
  ['later', 'Later', 'text-ink-mute'],
];

// Time of day, or nothing for an all-day task. A ToDo has a date and no clock,
// and printing "00:00" against one implies a precision that isn't there.
function when(row) {
  if (!row.when) return '—';
  if (row.kind === 'task' || row.all_day) return fmtDate(row.when);
  const d = new Date(String(row.when).replace(' ', 'T'));
  if (isNaN(d)) return fmtDate(row.when);
  const p = (n) => String(n).padStart(2, '0');
  return `${fmtDate(row.when)} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

function Row({ row }) {
  const newTab = useStore((s) => s.settings.openInNewTab);
  const openTaskDialog = useStore((s) => s.openTaskDialog);
  const openEventDialog = useStore((s) => s.openEventDialog);
  const setTaskStatus = useStore((s) => s.setTaskStatus);

  const isTask = row.kind === 'task';
  const open = () => (isTask
    ? openTaskDialog({ name: row.name, description: row.title, date: row.when,
                       priority: row.priority, reference_type: row.ref_doctype,
                       reference_name: row.ref_name })
    : openEventDialog({ name: row.name, subject: row.title, starts_on: row.when }));

  return (
    <tr className="clickable" onClick={open}>
      <td className="w-[34px]">
        {isTask ? (
          // Completing a task from the command centre is the whole point of
          // listing it here, so the checkbox does not open the dialog.
          <button type="button" title="Mark done"
            onClick={(e) => { e.stopPropagation(); setTaskStatus(row.name, 'Closed').catch(() => {}); }}
            className="w-[18px] h-[18px] rounded-[5px] border border-line-2 hover:border-gold hover:bg-gold-soft grid place-items-center transition-colors">
            <Icon name="check" className="!text-[13px] text-transparent hover:text-ink" />
          </button>
        ) : (
          <Icon name="event" className="!text-[16px] text-ink-mute" />
        )}
      </td>
      <td className="whitespace-nowrap tabular-nums text-[12.5px]">{when(row)}</td>
      <td>
        <span className={`bdg ${isTask ? 'bdg-other' : 'bdg-open'}`}>{isTask ? 'Task' : 'Event'}</span>
      </td>
      <td className="max-w-[420px]">
        <div className="truncate text-ink font-medium" title={row.title}>{row.title}</div>
        {row.location && <div className="text-[11.5px] text-ink-mute truncate">{row.location}</div>}
      </td>
      <td className="whitespace-nowrap text-[12.5px]">{shortUser(row.who) || '—'}</td>
      <td>
        {row.meta ? <span className={`bdg ${badgeClass(row.meta)}`}>{row.meta}</span> : '—'}
      </td>
      <td className="whitespace-nowrap">
        {row.ref_name ? (
          <button type="button" className="text-[12.5px] text-gold-text hover:underline truncate max-w-[180px]"
            onClick={(e) => { e.stopPropagation(); openFrappe(row.ref_doctype, row.ref_name, newTab); }}>
            {row.ref_name}
          </button>
        ) : <span className="text-ink-mute">—</span>}
      </td>
    </tr>
  );
}

export default function Upcoming() {
  const C = useStore((s) => s.data.command);
  const openTaskDialog = useStore((s) => s.openTaskDialog);
  const rows = C?.upcoming || [];

  const groups = GROUPS
    .map(([key, label, tone]) => [key, label, tone, rows.filter((r) => r.bucket === key)])
    .filter(([, , , items]) => items.length);

  const overdue = rows.filter((r) => r.bucket === 'overdue').length;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Upcoming tasks &amp; events</CardTitle>
          <CardSub>
            From now forward — not the header date range
            {overdue ? ` · ${overdue} overdue` : ''}
          </CardSub>
        </div>
        <button type="button" onClick={() => openTaskDialog({})}
          className="text-[12.5px] font-medium text-gold-text hover:underline shrink-0">
          + Task
        </button>
      </CardHeader>
      {rows.length ? (
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th />
                <th>When</th>
                <th>Kind</th>
                <th>What</th>
                <th>Who</th>
                <th>Priority</th>
                <th>Linked to</th>
              </tr>
            </thead>
            <tbody>
              {groups.map(([key, label, tone, items]) => (
                [
                  <tr key={`h-${key}`} className="bg-[rgba(10,10,10,0.02)]">
                    <td colSpan={7} className={`!py-2 text-[11px] uppercase tracking-[0.14em] font-semibold ${tone}`}>
                      {label} · {items.length}
                    </td>
                  </tr>,
                  ...items.map((r) => <Row key={`${r.kind}-${r.name}`} row={r} />),
                ]
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <CardContent>
          <div className="crm-empty">Nothing scheduled in the next 30 days</div>
        </CardContent>
      )}
    </Card>
  );
}
