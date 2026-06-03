import { useState } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter } from '@/components/ui/sheet';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import Icon from './Icon';
import { useStore } from '../store';

export default function ComposeDialog({ open, onOpenChange }) {
  const sendEmail = useStore((s) => s.sendEmail);
  const [to, setTo] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [status, setStatus] = useState(null);
  const [sending, setSending] = useState(false);

  async function send() {
    if (!to.trim()) { setStatus('Recipients required'); return; }
    setSending(true); setStatus(null);
    try {
      const r = await sendEmail({ recipients: to, subject, content: body.replace(/\n/g, '<br>') });
      setStatus(`✓ ${r?.status || 'sent'}`);
      setTimeout(() => { onOpenChange(false); setTo(''); setSubject(''); setBody(''); setStatus(null); }, 900);
    } catch (e) {
      setStatus(`✗ ${e.message || 'Failed to send'}`);
    } finally {
      setSending(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[460px]">
        <SheetHeader><SheetTitle>New message</SheetTitle></SheetHeader>
        <div className="flex-1 overflow-y-auto p-4 grid gap-3">
          <label className="grid gap-1"><span className="text-[11px] font-mono uppercase text-ink-3">To</span>
            <Input value={to} onChange={(e) => setTo(e.target.value)} placeholder="email@example.com, …" /></label>
          <label className="grid gap-1"><span className="text-[11px] font-mono uppercase text-ink-3">Subject</span>
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} /></label>
          <label className="grid gap-1"><span className="text-[11px] font-mono uppercase text-ink-3">Message</span>
            <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={12}
              className="rounded-md border border-input bg-transparent p-3 text-sm resize-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" /></label>
          {status && <div className="text-xs text-ink-2">{status}</div>}
        </div>
        <SheetFooter className="flex-row items-center justify-end gap-2 border-t-0">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button size="sm" onClick={send} disabled={sending}>
            <Icon name="send" className="text-[15px]" />{sending ? 'Sending…' : 'Send'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
