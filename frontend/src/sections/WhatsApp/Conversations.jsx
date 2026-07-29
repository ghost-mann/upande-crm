import { fmtRelative, initials } from '@shared/utils';
import { Card, CardHeader, CardTitle, CardSub } from '@/components/ui/card';
import { useStore } from '../../store';
import Icon from '../../components/Icon';
import { avatarBg, openFrappe } from '@/lib/crm';
import { cn } from '@/lib/utils';

// Outgoing delivery states, worst-first in visual weight. 82 of 191 outgoing
// messages on this site are `failed`, so failure must be unmissable.
const STATUS_TONE = {
  failed: 'text-bad',
  read: 'text-good',
  delivered: 'text-ink-3',
  sent: 'text-ink-mute',
};

const STATUS_ICON = {
  failed: 'error',
  read: 'done_all',
  delivered: 'done_all',
  sent: 'done',
};

export default function Conversations() {
  const waConvos = useStore((s) => s.waConvos);
  const waLoading = useStore((s) => s.waLoading);
  const openWaThread = useStore((s) => s.openWaThread);
  const newTab = useStore((s) => s.settings.openInNewTab);

  if (!waConvos) {
    return <div className="crm-empty">{waLoading ? 'Loading conversations…' : 'No data'}</div>;
  }
  if (!waConvos.available) {
    return (
      <div className="crm-empty">
        WhatsApp is not configured on this site. Set up a WhatsApp Account in desk first.
      </div>
    );
  }

  const rows = waConvos.rows || [];

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Conversations</CardTitle>
          <CardSub>
            {rows.length} threads
            {waConvos.unread_total ? ` · ${waConvos.unread_total} unread` : ''}
          </CardSub>
        </div>
      </CardHeader>

      {rows.length ? (
        <div className="tbl-wrap">
          {rows.map((r) => {
            const out = r.last_direction === 'Outgoing';
            const st = (r.last_status || '').toLowerCase();
            return (
              <div
                key={r.party}
                onClick={() => openWaThread(r.party)}
                className="grid grid-cols-[38px_minmax(0,1fr)_auto] gap-3 items-center px-4 py-3
                           border-b border-hairline last:border-0 cursor-pointer hover:bg-hover transition-colors"
              >
                <div className="w-[38px] h-[38px] rounded-full grid place-items-center text-white text-[13px] font-semibold"
                  style={{ background: avatarBg(r.display_name || r.party) }}>
                  {initials(r.display_name || r.party)}
                </div>

                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={cn('text-[14px] truncate',
                      r.unread ? 'font-semibold text-ink' : 'font-medium text-ink-2')}>
                      {r.display_name}
                    </span>
                    {r.link && (
                      <button
                        onClick={(e) => { e.stopPropagation(); openFrappe(r.link.doctype, r.link.name, newTab); }}
                        className="bdg bdg-open normal-case shrink-0 hover:underline"
                        title={`${r.link.doctype} · ${r.link.name}`}
                      >
                        {r.link.doctype}
                      </button>
                    )}
                    {!r.window_open && (
                      <span className="bdg bdg-warn normal-case shrink-0" title="Outside Meta's 24-hour window — templates only">
                        template only
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    {out && st && (
                      <Icon name={STATUS_ICON[st] || 'schedule'}
                        className={cn('text-[13px] shrink-0', STATUS_TONE[st] || 'text-ink-mute')} />
                    )}
                    <span className={cn('text-[12.5px] truncate',
                      st === 'failed' ? 'text-bad' : 'text-ink-mute')}>
                      {st === 'failed' ? 'Not delivered · ' : ''}{r.last_message || '—'}
                    </span>
                  </div>
                  <div className="text-[10.5px] text-ink-faint font-mono mt-0.5">{r.party}</div>
                </div>

                <div className="text-right shrink-0">
                  <div className="text-[11px] text-ink-mute">{fmtRelative(r.last_at)}</div>
                  {r.unread ? (
                    <div className="mt-1 inline-grid place-items-center min-w-[20px] h-5 px-1.5 rounded-full
                                    bg-gold text-[var(--on-accent)] text-[11px] font-semibold">
                      {r.unread}
                    </div>
                  ) : (
                    <div className="mt-1 text-[10.5px] text-ink-faint">{r.total} msg</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="crm-empty">No WhatsApp conversations yet</div>
      )}
    </Card>
  );
}
