import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import Icon from './Icon';
import { useStore } from '../store';
import { cn } from '@/lib/utils';

// Gmail-style compose window: docked bottom-right, with minimize / expand /
// close. Driven by store.compose: null = closed, an object = open with optional
// prefill {to, cc, subject, body, reference, inReplyTo, title}.
export default function ComposeDialog() {
  const compose = useStore((s) => s.compose);
  const closeCompose = useStore((s) => s.closeCompose);
  const sendEmail = useStore((s) => s.sendEmail);

  const [to, setTo] = useState('');
  const [cc, setCc] = useState('');
  const [showCc, setShowCc] = useState(false);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [status, setStatus] = useState(null);
  const [sending, setSending] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [maximized, setMaximized] = useState(false);

  const open = compose !== null;

  // (Re)load prefill and reset the window each time it opens.
  useEffect(() => {
    if (compose) {
      setTo(compose.to || '');
      setCc(compose.cc || '');
      setShowCc(!!compose.cc);
      setSubject(compose.subject || '');
      setBody(compose.body || '');
      setStatus(null);
      setSending(false);
      setMinimized(false);
      setMaximized(false);
    }
  }, [compose]);

  if (!open) return null;

  async function send() {
    if (!to.trim()) { setStatus('Recipients required'); return; }
    setSending(true); setStatus(null);
    try {
      const r = await sendEmail({
        recipients: to,
        cc: cc || undefined,
        subject,
        content: body.replace(/\n/g, '<br>'),
        reference_doctype: compose?.reference?.doctype || undefined,
        reference_name: compose?.reference?.name || undefined,
        in_reply_to: compose?.inReplyTo || undefined,
      });
      setStatus(`✓ ${r?.status || 'sent'}`);
      setTimeout(() => closeCompose(), 900);
    } catch (e) {
      setStatus(`✗ ${e.message || 'Failed to send'}`);
    } finally {
      setSending(false);
    }
  }

  const title = compose?.title || 'New message';

  // Window chrome positioning per state.
  const wrap = maximized
    ? 'fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4'
    : 'fixed bottom-0 right-5 z-[60]';
  const panel = maximized
    ? 'flex flex-col w-[760px] max-w-[95vw] h-[88vh] rounded-2xl shadow-2xl border border-hairline bg-surface overflow-hidden'
    : cn(
        'flex flex-col w-[480px] max-w-[calc(100vw-1.5rem)] rounded-t-2xl shadow-2xl border border-hairline bg-surface overflow-hidden',
        minimized ? 'h-11' : 'h-[560px] max-h-[calc(100vh-72px)]',
      );

  const headerBtn = 'w-7 h-7 rounded flex items-center justify-center hover:bg-white/15';

  return (
    <div className={wrap} onMouseDown={(e) => { if (maximized && e.target === e.currentTarget) e.preventDefault(); }}>
      <div className={panel}>
        {/* Header bar */}
        <div
          className="h-11 shrink-0 bg-grad-ink text-white flex items-center gap-1 pl-4 pr-1.5 cursor-pointer select-none"
          onClick={() => minimized && setMinimized(false)}
        >
          <span className="mail-display text-[14px] font-semibold truncate flex-1">{title}</span>
          <button className={headerBtn} title={minimized ? 'Expand' : 'Minimize'}
            onClick={(e) => { e.stopPropagation(); setMinimized((m) => !m); setMaximized(false); }}>
            <Icon name={minimized ? 'expand_less' : 'remove'} className="text-[18px]" />
          </button>
          <button className={headerBtn} title={maximized ? 'Restore' : 'Full screen'}
            onClick={(e) => { e.stopPropagation(); setMaximized((m) => !m); setMinimized(false); }}>
            <Icon name={maximized ? 'close_fullscreen' : 'open_in_full'} className="text-[15px]" />
          </button>
          <button className={headerBtn} title="Close" onClick={(e) => { e.stopPropagation(); closeCompose(); }}>
            <Icon name="close" className="text-[18px]" />
          </button>
        </div>

        {!minimized && (
          <>
            <div className="flex-1 overflow-y-auto crm-scroll">
              {/* Recipient rows, Gmail-style underlined fields */}
              <div className="flex items-center gap-2 px-3 h-10 border-b border-line">
                <span className="text-[11px] font-mono uppercase text-ink-3 w-8">To</span>
                <input value={to} onChange={(e) => setTo(e.target.value)} placeholder="email@example.com, …"
                  className="flex-1 bg-transparent outline-none text-sm" />
                {!showCc && (
                  <button className="text-[11px] text-ink-3 hover:text-gold-text px-1" onClick={() => setShowCc(true)}>Cc</button>
                )}
              </div>
              {showCc && (
                <div className="flex items-center gap-2 px-3 h-10 border-b border-line">
                  <span className="text-[11px] font-mono uppercase text-ink-3 w-8">Cc</span>
                  <input value={cc} onChange={(e) => setCc(e.target.value)} placeholder="cc@example.com"
                    className="flex-1 bg-transparent outline-none text-sm" />
                </div>
              )}
              <div className="flex items-center gap-2 px-3 h-10 border-b border-line">
                <span className="text-[11px] font-mono uppercase text-ink-3 w-8">Subj</span>
                <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject"
                  className="flex-1 bg-transparent outline-none text-sm" />
              </div>
              {compose?.reference?.name && (
                <div className="px-3 py-1.5 font-mono text-[10px] text-ink-3 border-b border-line">
                  Linked to {compose.reference.doctype} · {compose.reference.name}
                </div>
              )}
              <textarea value={body} onChange={(e) => setBody(e.target.value)}
                placeholder="Write your message…"
                className="w-full min-h-[200px] resize-none bg-transparent outline-none p-3 text-sm leading-relaxed" />
            </div>

            <div className="shrink-0 flex items-center gap-2 px-3 py-2 border-t border-line">
              <Button size="sm" className="rounded-full bg-gold text-ink hover:bg-gold-2 hover:text-white shadow-none px-5" onClick={send} disabled={sending}>
                <Icon name="send" className="text-[15px]" />{sending ? 'Sending…' : 'Send'}
              </Button>
              <button onClick={() => closeCompose()} className="text-ink-3 hover:text-bad" title="Discard">
                <Icon name="delete" className="text-[18px]" />
              </button>
              {status && <span className="ml-auto text-xs text-ink-2">{status}</span>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
