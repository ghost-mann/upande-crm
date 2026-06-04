import { useState, useEffect } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter } from '@/components/ui/sheet';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import Icon from './Icon';
import { useStore } from '../store';

// Compose / reply / forward. Driven by store.compose: null = closed, an object
// = open with optional prefill {to, cc, subject, body, reference, inReplyTo}.
export default function ComposeDialog() {
  const compose = useStore((s) => s.compose);
  const closeCompose = useStore((s) => s.closeCompose);
  const sendEmail = useStore((s) => s.sendEmail);

  const [to, setTo] = useState('');
  const [cc, setCc] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [status, setStatus] = useState(null);
  const [sending, setSending] = useState(false);

  const open = compose !== null;

  // Load the prefill each time the dialog is (re)opened.
  useEffect(() => {
    if (compose) {
      setTo(compose.to || '');
      setCc(compose.cc || '');
      setSubject(compose.subject || '');
      setBody(compose.body || '');
      setStatus(null);
      setSending(false);
    }
  }, [compose]);

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

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) closeCompose(); }}>
      <SheetContent className="w-[460px]">
        <SheetHeader><SheetTitle>{title}</SheetTitle></SheetHeader>
        <div className="flex-1 overflow-y-auto p-4 grid gap-3">
          <label className="grid gap-1"><span className="text-[11px] font-mono uppercase text-ink-3">To</span>
            <Input value={to} onChange={(e) => setTo(e.target.value)} placeholder="email@example.com, …" /></label>
          <label className="grid gap-1"><span className="text-[11px] font-mono uppercase text-ink-3">Cc</span>
            <Input value={cc} onChange={(e) => setCc(e.target.value)} placeholder="(optional)" /></label>
          <label className="grid gap-1"><span className="text-[11px] font-mono uppercase text-ink-3">Subject</span>
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} /></label>
          {compose?.reference?.name && (
            <div className="font-mono text-[10px] text-ink-3">
              Linked to {compose.reference.doctype} · {compose.reference.name}
            </div>
          )}
          <label className="grid gap-1"><span className="text-[11px] font-mono uppercase text-ink-3">Message</span>
            <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={12}
              className="rounded-md border border-input bg-transparent p-3 text-sm resize-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" /></label>
          {status && <div className="text-xs text-ink-2">{status}</div>}
        </div>
        <SheetFooter className="flex-row items-center justify-end gap-2 border-t-0">
          <Button variant="outline" size="sm" onClick={() => closeCompose()}>Cancel</Button>
          <Button size="sm" onClick={send} disabled={sending}>
            <Icon name="send" className="text-[15px]" />{sending ? 'Sending…' : 'Send'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
