import { useStore } from '../store';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import Icon from './Icon';
import { fmtDateTime } from '@shared/utils';

// HTML → readable plaintext, for quoting the original in a reply/forward.
function toPlain(html) {
  return String(html || '')
    .replace(/<\s*br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|tr|h[1-6])>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&').replace(/&lt;/gi, '<').replace(/&gt;/gi, '>')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function stripPrefix(subject, re) {
  return String(subject || '').replace(re, '').trim();
}

export default function ThreadView() {
  const m = useStore((s) => s.openMsg);
  const close = useStore((s) => s.closeMessage);
  const openCompose = useStore((s) => s.openCompose);
  const newTab = useStore((s) => s.settings.openInNewTab);
  if (!m) return null;

  const received = (m.direction || m.sent_or_received) === 'Received';
  const reference = m.reference_doctype && m.reference_name
    ? { doctype: m.reference_doctype, name: m.reference_name }
    : undefined;
  const quote = `\n\n\n----- On ${fmtDateTime(m.communication_date)}, ${m.sender || ''} wrote: -----\n${toPlain(m.content)}`;

  function reply() {
    openCompose({
      title: 'Reply',
      to: received ? (m.sender || '') : (m.recipients || ''),
      subject: `Re: ${stripPrefix(m.subject, /^\s*(re:\s*)+/i)}`,
      body: quote,
      reference,
      inReplyTo: m.name,
    });
  }
  function forward() {
    openCompose({
      title: 'Forward',
      to: '',
      subject: `Fwd: ${stripPrefix(m.subject, /^\s*(fwd?:\s*)+/i)}`,
      body: quote,
      reference,
    });
  }

  return (
    <Card className="mail-card">
      <div className="flex items-center gap-2 px-4 h-16 border-b border-hairline">
        <Button variant="ghost" size="icon" className="h-9 w-9 rounded-full shrink-0" onClick={close}><Icon name="arrow_back" className="text-[18px]" /></Button>
        <div className="min-w-0 flex-1">
          <div className="mail-display text-[17px] font-semibold truncate leading-tight">{m.subject || '(no subject)'}</div>
          <div className="text-[11px] text-ink-3 truncate mt-0.5">
            {m.sender}{m.recipients ? ` → ${m.recipients}` : ''} · {fmtDateTime(m.communication_date)}
          </div>
        </div>
        <Button variant="default" size="sm" className="rounded-full bg-navy hover:bg-navy-2 shadow-none" onClick={reply}>
          <Icon name="reply" className="text-[14px]" />Reply
        </Button>
        <Button variant="outline" size="sm" className="rounded-full" onClick={forward}>
          <Icon name="forward" className="text-[14px]" />Forward
        </Button>
        {reference && (
          <Button variant="outline" size="sm" className="rounded-full"
            onClick={() => window.open(`/app/${m.reference_doctype.toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(m.reference_name)}`, newTab ? '_blank' : '_self')}>
            <Icon name="open_in_new" className="text-[14px]" />{m.reference_doctype}
          </Button>
        )}
      </div>
      <div
        className="p-5 text-[13px] leading-relaxed [&_img]:max-w-full [&_a]:text-navy [&_a]:underline"
        dangerouslySetInnerHTML={{ __html: m.content || '<p class="crm-empty">No content.</p>' }}
      />
    </Card>
  );
}
