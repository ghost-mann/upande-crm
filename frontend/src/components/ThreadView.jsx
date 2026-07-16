import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import Icon from './Icon';
import { api } from '@shared/api';
import { avatarBg, openFrappe, currentUser } from '@/lib/crm';
import { initials, fmtDateTime, fmtRelative, nameFromAddress } from '@shared/utils';

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
const stripPrefix = (s, re) => String(s || '').replace(re, '').trim();
const splitAddrs = (v) => String(v || '').split(',').map((x) => x.trim()).filter(Boolean);
const fileSize = (n) => (n == null ? '' : n >= 1e6 ? `${(n / 1e6).toFixed(1)} MB` : n >= 1e3 ? `${Math.round(n / 1e3)} KB` : `${n} B`);

function AddrRow({ label, value }) {
  if (!value) return null;
  return (
    <div className="flex gap-2 text-[12.5px]">
      <span className="text-ink-mute w-8 shrink-0">{label}</span>
      <span className="text-ink-3 break-words">{value}</span>
    </div>
  );
}

export default function ThreadView() {
  const m = useStore((s) => s.openMsg);
  const close = useStore((s) => s.closeMessage);
  const openCompose = useStore((s) => s.openCompose);
  const deleteMessages = useStore((s) => s.deleteMessages);
  const newTab = useStore((s) => s.settings.openInNewTab);
  const [attachments, setAttachments] = useState([]);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    if (!m?.name) return undefined;
    let cancelled = false;
    setAttachments([]);
    api('frappe.client.get_list', {
      doctype: 'File',
      filters: JSON.stringify({ attached_to_doctype: 'Communication', attached_to_name: m.name }),
      fields: JSON.stringify(['file_name', 'file_url', 'file_size', 'is_private']),
      limit_page_length: 20,
    }).then((r) => { if (!cancelled) setAttachments(r || []); }).catch(() => {});
    return () => { cancelled = true; };
  }, [m?.name]);

  if (!m) return null;

  const received = (m.direction || m.sent_or_received) === 'Received';
  const senderName = nameFromAddress(m.sender || '') || m.sender || '—';
  const reference = m.reference_doctype && m.reference_name ? { doctype: m.reference_doctype, name: m.reference_name } : undefined;
  const tags = splitAddrs(m._user_tags);
  const quote = `\n\n\n----- On ${fmtDateTime(m.communication_date)}, ${m.sender || ''} wrote: -----\n${toPlain(m.content)}`;

  function reply(all = false) {
    const me = currentUser();
    let to = received ? (m.sender || '') : (m.recipients || '');
    let cc;
    if (all) {
      const others = [...splitAddrs(m.recipients), ...(received ? [m.sender] : [])]
        .filter((a) => a && a.toLowerCase() !== me);
      to = [received ? m.sender : m.recipients, ...others].filter(Boolean).join(', ');
      cc = splitAddrs(m.cc).filter((a) => a.toLowerCase() !== me).join(', ') || undefined;
    }
    openCompose({
      title: all ? 'Reply all' : 'Reply',
      to, cc,
      subject: `Re: ${stripPrefix(m.subject, /^\s*(re:\s*)+/i)}`,
      body: quote, reference, inReplyTo: m.name,
    });
  }
  function forward() {
    openCompose({ title: 'Forward', to: '', subject: `Fwd: ${stripPrefix(m.subject, /^\s*(fwd?:\s*)+/i)}`, body: quote, reference });
  }
  async function del() {
    if (!window.confirm('Delete this email? This cannot be undone.')) return;
    await deleteMessages([m.name]);
    close();
  }

  const status = m.delivery_status;

  return (
    <Card className="mail-card">
      {/* Action bar */}
      <div className="flex items-center gap-1.5 px-4 h-14 border-b border-hairline">
        <Button variant="ghost" size="icon" className="h-9 w-9 rounded-full shrink-0" onClick={close} aria-label="Back"><Icon name="arrow_back" className="text-[19px]" /></Button>
        <div className="ml-auto flex items-center gap-1.5">
          <Button variant="default" size="sm" className="rounded-full bg-gold text-ink hover:bg-gold-2 hover:text-white shadow-none" onClick={() => reply(false)}>
            <Icon name="reply" className="text-[15px]" />Reply
          </Button>
          <Button variant="outline" size="sm" className="rounded-full" onClick={() => reply(true)}><Icon name="reply_all" className="text-[15px]" />Reply all</Button>
          <Button variant="outline" size="sm" className="rounded-full" onClick={forward}><Icon name="forward" className="text-[15px]" />Forward</Button>
          {reference && (
            <Button variant="outline" size="sm" className="rounded-full" onClick={() => openFrappe(reference.doctype, reference.name, newTab)}>
              <Icon name="open_in_new" className="text-[15px]" />{reference.doctype}
            </Button>
          )}
          <Button variant="ghost" size="icon" className="h-9 w-9 rounded-full text-ink-mute hover:text-bad" onClick={del} aria-label="Delete"><Icon name="delete" className="text-[18px]" /></Button>
        </div>
      </div>

      {/* Message header */}
      <div className="px-6 pt-5 pb-4 border-b border-hairline">
        <h2 className="mail-display text-[24px] font-semibold text-ink leading-tight mb-3">{m.subject || '(no subject)'}</h2>
        <div className="flex items-start gap-3">
          <div className="m-avatar !w-11 !h-11 !text-[14px]" style={{ background: avatarBg(senderName) }}>{initials(senderName)}</div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[14px] font-semibold text-ink">{senderName}</span>
              <span className="text-[12px] text-ink-mute">&lt;{m.sender}&gt;</span>
              {status && <span className="bdg bdg-open">{status}</span>}
            </div>
            <button className="text-[12px] text-ink-mute hover:text-ink mt-0.5 flex items-center gap-1" onClick={() => setShowDetails((v) => !v)}>
              to {nameFromAddress(m.recipients || '') || m.recipients || '—'}
              <Icon name={showDetails ? 'expand_less' : 'expand_more'} className="text-[15px]" />
            </button>
            {showDetails && (
              <div className="mt-2 grid gap-1 bg-surface-2 rounded-xl p-3 border border-hairline">
                <AddrRow label="From" value={m.sender} />
                <AddrRow label="To" value={m.recipients} />
                <AddrRow label="Cc" value={m.cc} />
                <AddrRow label="Bcc" value={m.bcc} />
                <AddrRow label="Date" value={fmtDateTime(m.communication_date)} />
              </div>
            )}
          </div>
          <div className="text-right shrink-0">
            <div className="text-[12px] text-ink-3">{fmtDateTime(m.communication_date)}</div>
            <div className="text-[11px] text-ink-mute">{fmtRelative(m.communication_date)}</div>
          </div>
        </div>

        {(reference || tags.length > 0) && (
          <div className="flex items-center gap-2 flex-wrap mt-3">
            {reference && <span className="m-chip">{reference.doctype} · {reference.name}</span>}
            {tags.map((t) => <span key={t} className="bdg bdg-other">{t}</span>)}
          </div>
        )}
      </div>

      {/* Attachments */}
      {attachments.length > 0 && (
        <div className="px-6 py-4 border-b border-hairline">
          <div className="text-[10.5px] uppercase tracking-[0.14em] text-ink-mute font-semibold mb-2.5">{attachments.length} attachment{attachments.length === 1 ? '' : 's'}</div>
          <div className="flex flex-wrap gap-2">
            {attachments.map((a) => (
              <a key={a.file_url} href={a.file_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2.5 px-3 py-2 rounded-xl border border-hairline bg-surface-2 hover:shadow-card transition-shadow max-w-[260px]">
                <Icon name="attach_file" className="text-[18px] text-ink-mute" />
                <div className="min-w-0">
                  <div className="text-[12.5px] text-ink truncate">{a.file_name}</div>
                  <div className="text-[10.5px] text-ink-mute">{fileSize(a.file_size)}</div>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Body */}
      <div
        className="p-6 text-[13.5px] leading-relaxed text-ink-2 [&_img]:max-w-full [&_a]:text-gold-text [&_a]:underline"
        dangerouslySetInnerHTML={{ __html: m.content || '<p class="crm-empty">No content.</p>' }}
      />
    </Card>
  );
}
