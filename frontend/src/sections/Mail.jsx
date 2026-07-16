import { useState, useEffect } from 'react';
import { useStore } from '../store';
import { Card } from '@/components/ui/card';
import Icon from '../components/Icon';
import MailList from '../components/MailList';

const LABELS = {
  unread: 'Unread', inbox: 'All inbox', sent: 'Sent', starred: 'Starred',
  crm_leads: 'Lead emails', crm_opps: 'Opportunity emails',
  crm_customers: 'Customer emails', crm_quotations: 'Quotation emails',
};

function headerCount(table, counts, fallback) {
  const map = {
    unread: 'inbox_unread', inbox: 'inbox', sent: 'sent_ok',
    crm_leads: 'crm_leads', crm_opps: 'crm_opps', crm_customers: 'crm_customers', crm_quotations: 'crm_quotations',
  };
  return counts?.[map[table]] ?? fallback;
}

function isUnread(r) {
  return !!r.unread || (r.sent_or_received === 'Received' && r.status === 'Open' && !r.seen);
}

export default function Mail() {
  const { table, mailFolder, mailLoading, starred, loadMail } = useStore();
  const openMessage = useStore((s) => s.openMessage);
  const openCompose = useStore((s) => s.openCompose);
  const markRead = useStore((s) => s.markRead);
  const toggleStar = useStore((s) => s.toggleStar);
  const deleteMessages = useStore((s) => s.deleteMessages);
  const offset = useStore((s) => s.mailOffset);
  const t = table || 'unread';
  const PAGE = 50;

  const [sel, setSel] = useState(() => new Set());
  const [busy, setBusy] = useState(false);
  // Clear selection when the folder or page changes.
  useEffect(() => { setSel(new Set()); }, [t, offset]);

  let rows = mailFolder?.rows || [];
  if (mailFolder?.clientFilter === 'starred') {
    rows = rows.filter((r) => starred.includes(r.name) || String(r._user_tags || '').toLowerCase().includes('starred'));
  }
  const count = headerCount(t, mailFolder?.counts, rows.length);
  const names = rows.map((r) => r.name);
  const allSelected = names.length > 0 && names.every((n) => sel.has(n));
  const someSelected = sel.size > 0;

  const toggleSelect = (name) => setSel((prev) => {
    const next = new Set(prev);
    next.has(name) ? next.delete(name) : next.add(name);
    return next;
  });
  const selectAll = () => setSel(allSelected ? new Set() : new Set(names));
  const clear = () => setSel(new Set());

  async function run(fn) { setBusy(true); try { await fn(); } finally { setBusy(false); } }
  const markSel = (seen) => run(async () => { await Promise.all([...sel].map((n) => markRead(n, seen))); clear(); });
  const starSel = (make) => run(async () => { await Promise.all([...sel].map((n) => toggleStar(n, make))); clear(); });
  const delSel = () => {
    if (!window.confirm(`Delete ${sel.size} email${sel.size === 1 ? '' : 's'}? This cannot be undone.`)) return;
    run(async () => {
      const r = await deleteMessages([...sel]);
      clear();
      if (r.failed) window.alert(`${r.ok} deleted · ${r.failed} could not be deleted (permission).`);
    });
  };
  const markAllRead = () => run(async () => {
    await Promise.all(rows.filter(isUnread).map((r) => markRead(r.name, true)));
  });

  return (
    <Card className="mail-card">
      {/* Folder header */}
      <div className="flex items-center justify-between px-6 pt-5 pb-4">
        <div>
          <div className="mail-display text-[22px] font-semibold text-ink leading-tight">{LABELS[t] || t}</div>
          <div className="text-[12px] text-ink-mute mt-1">{mailLoading ? 'Loading…' : `Showing ${rows.length} of ${count}`}</div>
        </div>
        <button onClick={() => openCompose({})} className="h-10 px-4 bg-gold text-ink rounded-full text-[13px] font-semibold inline-flex items-center gap-2 hover:bg-gold-2 hover:text-white transition-colors shadow-[0_4px_14px_rgba(217,165,20,0.28)]">
          <Icon name="edit_square" className="text-[18px]" />Compose
        </button>
      </div>

      {/* Toolbar — contextual (bulk actions when rows are selected) */}
      <div className="mailbar">
        <label className="grid place-items-center w-9 h-9 rounded-[9px] hover:bg-hover cursor-pointer" title={allSelected ? 'Deselect all' : 'Select all'}>
          <input type="checkbox" aria-label="Select all emails" checked={allSelected} ref={(el) => { if (el) el.indeterminate = someSelected && !allSelected; }} onChange={selectAll} />
        </label>

        {someSelected ? (
          <>
            <span className="text-[12px] font-medium text-ink px-2">{sel.size} selected</span>
            <div className="w-px h-5 bg-hairline mx-1" />
            <button title="Mark as read" aria-label="Mark as read" onClick={() => markSel(true)} disabled={busy}><Icon name="mark_email_read" className="text-[18px]" /></button>
            <button title="Mark as unread" aria-label="Mark as unread" onClick={() => markSel(false)} disabled={busy}><Icon name="mark_email_unread" className="text-[18px]" /></button>
            <button title="Star" aria-label="Star" onClick={() => starSel(true)} disabled={busy}><Icon name="star" className="text-[18px]" /></button>
            <button title="Unstar" aria-label="Unstar" onClick={() => starSel(false)} disabled={busy}><Icon name="star_border" className="text-[18px]" /></button>
            <button title="Delete" aria-label="Delete" onClick={delSel} disabled={busy}><Icon name="delete" className="text-[18px]" /></button>
            <button className="!text-ink-mute" title="Clear selection" aria-label="Clear selection" onClick={clear}><Icon name="close" className="text-[18px]" /></button>
          </>
        ) : (
          <>
            <button title="Refresh" aria-label="Refresh" onClick={() => loadMail(t, offset)} disabled={mailLoading}><Icon name="refresh" className="text-[19px]" /></button>
            <button title="Mark all as read" aria-label="Mark all as read" onClick={markAllRead} disabled={busy || !rows.some(isUnread)}>
              <Icon name="done_all" className="text-[19px]" />
            </button>
            <div className="ml-auto flex items-center gap-1">
              <span className="text-[12px] text-ink-mute tabular-nums pr-1">
                {rows.length ? `${offset + 1}–${offset + rows.length}` : '0'} of {count}
              </span>
              <button title="Newer" aria-label="Newer" onClick={() => loadMail(t, Math.max(0, offset - PAGE))} disabled={mailLoading || offset === 0}>
                <Icon name="chevron_left" className="text-[20px]" />
              </button>
              <button title="Older" aria-label="Older" onClick={() => loadMail(t, offset + PAGE)} disabled={mailLoading || offset + rows.length >= count || rows.length < PAGE}>
                <Icon name="chevron_right" className="text-[20px]" />
              </button>
            </div>
          </>
        )}
      </div>

      <div className="px-2 py-1.5">
        {mailLoading ? <div className="crm-empty">Loading mailbox…</div>
          : rows.length ? <MailList rows={rows} onOpen={openMessage} selected={sel} onToggleSelect={toggleSelect} />
            : <div className="crm-empty">No messages in this folder.</div>}
      </div>
    </Card>
  );
}
