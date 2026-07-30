import { useEffect, useRef } from 'react';
import { fmtDateTime, initials } from '@shared/utils';
import { Card } from '@/components/ui/card';
import { useStore } from '../../store';
import Icon from '../../components/Icon';
import { avatarBg, openFrappe } from '@/lib/crm';
import { cn } from '@/lib/utils';
import WaComposer from '../../components/WaComposer';

const STATUS_ICON = { failed: 'error', read: 'done_all', delivered: 'done_all', sent: 'done' };

function bodyText(html) {
  return String(html || '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(div|p)>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ')
    .trim();
}

export default function Thread() {
  const t = useStore((s) => s.waThread);
  const party = useStore((s) => s.waParty);
  const loading = useStore((s) => s.waLoading);
  const closeWaThread = useStore((s) => s.closeWaThread);
  const openTaskDialog = useStore((s) => s.openTaskDialog);
  const newTab = useStore((s) => s.settings.openInNewTab);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [t?.messages?.length]);

  if (!t) return <div className="crm-empty">{loading ? 'Loading conversation…' : 'No conversation'}</div>;

  const msgs = t.messages || [];

  return (
    <Card>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-hairline">
        <button className="iconbtn !w-9 !h-9 !shadow-none" onClick={closeWaThread} title="Back to conversations">
          <Icon name="arrow_back" className="text-[18px]" />
        </button>
        <div className="w-9 h-9 rounded-full grid place-items-center text-white text-[13px] font-semibold shrink-0"
          style={{ background: avatarBg(t.display_name || party) }}>
          {initials(t.display_name || party)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[15px] font-semibold text-ink truncate">{t.display_name}</div>
          <div className="text-[11px] text-ink-mute font-mono">{party}</div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {t.link ? (
            <button className="bdg bdg-open normal-case hover:underline"
              onClick={() => openFrappe(t.link.doctype, t.link.name, newTab)}
              title={`Open ${t.link.doctype} ${t.link.name}`}>
              {t.link.doctype} · {t.link.name}
            </button>
          ) : (
            <span className="bdg bdg-other normal-case">No CRM match</span>
          )}
          {/* Where the three specs join: log this conversation as CRM work. */}
          <button
            className="datepill !py-2"
            title="Create a follow-up task for this conversation"
            onClick={() => openTaskDialog({
              description: `WhatsApp follow-up with ${t.display_name} (${party})`,
              reference_type: t.link?.doctype || '',
              reference_name: t.link?.name || '',
            })}
          >
            <Icon name="add_task" className="text-[15px]" />Log task
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="px-4 py-4 max-h-[calc(100vh-420px)] overflow-y-auto crm-scroll">
        {msgs.length ? msgs.map((m) => {
          const out = m.type === 'Outgoing';
          const st = (m.status || '').toLowerCase();
          const failed = st === 'failed';
          return (
            <div key={m.name} className={cn('flex mb-2.5', out ? 'justify-end' : 'justify-start')}>
              <div className={cn(
                'max-w-[76%] rounded-2xl px-3.5 py-2.5 text-[13.5px] leading-relaxed whitespace-pre-wrap break-words',
                out
                  ? (failed ? 'bg-bad-soft border border-bad/40 text-ink' : 'bg-gold-soft border border-gold/30 text-ink')
                  : 'bg-surface-2 border border-hairline text-ink-2',
              )}>
                {bodyText(m.message) || <span className="text-ink-mute italic">
                  {m.content_type && m.content_type !== 'text' ? `[${m.content_type}]` : '(empty)'}
                </span>}
                <div className={cn('flex items-center gap-1.5 mt-1.5 text-[10px]',
                  failed ? 'text-bad' : 'text-ink-mute')}>
                  {/* A template reads differently from something typed by hand. */}
                  {m.is_template ? (
                    <span className="inline-flex items-center gap-1" title={m.template_name || 'Template message'}>
                      <Icon name="description" className="text-[11px]" />template
                    </span>
                  ) : null}
                  <span>{fmtDateTime(m.creation)}</span>
                  {out && st && (
                    <>
                      <Icon name={STATUS_ICON[st] || 'schedule'} className="text-[12px]" />
                      <span>{failed ? 'not delivered' : st}</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        }) : <div className="crm-empty">No messages</div>}
        <div ref={endRef} />
      </div>

      <WaComposer party={party} windowOpen={t.window_open} link={t.link} lastInboundAt={t.last_inbound_at} />
    </Card>
  );
}
