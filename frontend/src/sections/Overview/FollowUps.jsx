import { fmt, fmtDate, fmtRelative } from '@shared/utils';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { useStore } from '../../store';
import { openFrappe, shortUser } from '@/lib/crm';
import Icon from '../../components/Icon';

// Work that is waiting on somebody. Both lists are actionable in place — the
// point of surfacing a follow-up on the command centre is to close it from here.

function waitTone(days) {
  if (days >= 14) return 'text-bad';
  if (days >= 7) return 'text-warn';
  return 'text-ink-mute';
}

function Emails({ rows }) {
  const newTab = useStore((s) => s.settings.openInNewTab);
  const openCompose = useStore((s) => s.openCompose);
  if (!rows?.length) return <div className="crm-empty">Every sent email has a reply</div>;
  return (
    <div>
      {rows.map((r) => (
        <div key={r.name} className="flex items-center gap-3 py-2.5 border-b border-hairline last:border-0">
          <span className="flex-1 min-w-0">
            <span className="block text-[13px] text-ink font-medium truncate" title={r.subject}>
              {r.subject}
            </span>
            <span className="block text-[11.5px] text-ink-mute truncate">
              to {r.recipients || '—'} · sent {fmtDate(r.sent_on)}
              {r.ref_name && (
                <button type="button" className="text-gold-text hover:underline ml-1.5"
                  onClick={() => openFrappe(r.ref_doctype, r.ref_name, newTab)}>
                  {r.ref_name}
                </button>
              )}
            </span>
          </span>
          <span className={`text-[12px] font-semibold tabular-nums shrink-0 ${waitTone(r.waiting_days)}`}>
            {fmt(r.waiting_days)}d
          </span>
          <button type="button" title="Follow up"
            onClick={() => openCompose({
              to: r.recipients,
              subject: r.subject?.startsWith('Re:') ? r.subject : `Re: ${r.subject}`,
              reference: r.ref_doctype && r.ref_name
                ? { doctype: r.ref_doctype, name: r.ref_name } : undefined,
            })}
            className="w-7 h-7 rounded-lg grid place-items-center hover:bg-hover text-ink-mute hover:text-ink shrink-0">
            <Icon name="reply" className="!text-[16px]" />
          </button>
        </div>
      ))}
    </div>
  );
}

function Calls({ rows }) {
  const newTab = useStore((s) => s.settings.openInNewTab);
  const openCallDialog = useStore((s) => s.openCallDialog);
  if (!rows?.length) return <div className="crm-empty">No unanswered calls in range</div>;
  return (
    <div>
      {rows.map((r) => (
        <div key={r.name} className="flex items-center gap-3 py-2.5 border-b border-hairline last:border-0">
          <Icon name={r.type === 'Incoming' ? 'call_received' : 'call_made'}
            className="!text-[16px] text-ink-mute shrink-0" />
          <span className="flex-1 min-w-0">
            <span className="block text-[13px] text-ink font-medium truncate">
              {r.type === 'Incoming' ? r.from : r.to}
            </span>
            <span className="block text-[11.5px] text-ink-mute truncate">
              {r.status} · {fmtRelative(r.start_time)} · {shortUser(r.owner)}
              {r.reference_name && (
                <button type="button" className="text-gold-text hover:underline ml-1.5"
                  onClick={() => openFrappe(r.reference_doctype, r.reference_name, newTab)}>
                  {r.reference_name}
                </button>
              )}
            </span>
          </span>
          <button type="button" title="Log a call back"
            onClick={() => openCallDialog({
              type: 'Outgoing',
              to: r.type === 'Incoming' ? r.from : r.to,
              reference_doctype: r.reference_doctype,
              reference_name: r.reference_name,
            })}
            className="w-7 h-7 rounded-lg grid place-items-center hover:bg-hover text-ink-mute hover:text-ink shrink-0">
            <Icon name="phone_forwarded" className="!text-[16px]" />
          </button>
        </div>
      ))}
    </div>
  );
}

export default function FollowUps() {
  const C = useStore((s) => s.data.command);
  const F = C?.follow_ups;
  if (!F) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-[18px] mb-[18px]">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Awaiting a reply</CardTitle>
            <CardSub>Sent with no answer since · longest waiting first</CardSub>
          </div>
        </CardHeader>
        <CardContent><Emails rows={F.emails} /></CardContent>
      </Card>
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Calls to return</CardTitle>
            <CardSub>Nobody was reached</CardSub>
          </div>
        </CardHeader>
        <CardContent><Calls rows={F.calls} /></CardContent>
      </Card>
    </div>
  );
}
