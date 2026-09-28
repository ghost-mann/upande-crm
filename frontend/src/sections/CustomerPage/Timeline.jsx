import { useEffect, useRef, useState } from 'react';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { fmtDate } from '@shared/utils';
import { cn } from '@/lib/utils';
import { useStore } from '../../store';
import Icon from '../../components/Icon';
import { openFrappe, shortUser } from '@/lib/crm';
import { customerTimelineApi, customerAddNoteApi } from '../../lib/customer';

// Every conversation and piece of work with this customer, newest first —
// so nothing about the relationship lives only in one person's inbox.
const KINDS = [
  { key: 'email', label: 'Emails', icon: 'mail', module: 'mail' },
  { key: 'call', label: 'Calls', icon: 'call', module: 'calls' },
  { key: 'whatsapp', label: 'WhatsApp', icon: 'chat', module: 'wa' },
  { key: 'event', label: 'Events', icon: 'event', module: 'evt' },
  { key: 'task', label: 'Tasks', icon: 'task_alt', module: 'evt' },
  { key: 'note', label: 'Notes', icon: 'edit_note' },
  { key: 'claim', label: 'Claims', icon: 'report', module: 'claims' },
  { key: 'visit', label: 'Visits', icon: 'handshake', module: 'visits' },
];
const ICON = Object.fromEntries(KINDS.map((k) => [k.key, k.icon]));

export default function Timeline({ name, noteFocus }) {
  const on = useStore((s) => s.moduleOn);
  useStore((s) => s.orgMeta.modules);
  const newTab = useStore((s) => s.settings.openInNewTab);
  const available = KINDS.filter((k) => !k.module || on(k.module));
  const [picked, setPicked] = useState(() => available.map((k) => k.key));
  const [items, setItems] = useState([]);
  const [next, setNext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const noteRef = useRef(null);

  useEffect(() => { if (noteFocus) noteRef.current?.focus(); }, [noteFocus]);

  const load = async (before) => {
    setLoading(true); setErr('');
    try {
      const r = await customerTimelineApi(name, { kinds: JSON.stringify(picked), before, limit: 50 });
      setItems((prev) => (before ? [...prev, ...r.items] : r.items));
      setNext(r.next_before);
    } catch (e) {
      setErr(e.message || 'Could not load the timeline');
    } finally {
      setLoading(false);
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (picked.length) load(null); else { setItems([]); setNext(null); setLoading(false); } }, [name, picked.join(',')]);

  const toggle = (k) => setPicked((p) => (p.includes(k) ? p.filter((x) => x !== k) : [...p, k]));

  const saveNote = async () => {
    if (!note.trim()) return;
    setSaving(true); setErr('');
    try {
      const r = await customerAddNoteApi(name, note.trim());
      if (picked.includes('note')) setItems((prev) => [r.item, ...prev]);
      setNote('');
    } catch (e) {
      setErr(e.message || 'Could not save the note');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] gap-[18px] items-start">
      <Card>
        <CardHeader>
          <div><CardTitle>Timeline</CardTitle><CardSub>Newest first</CardSub></div>
          <div className="flex flex-wrap gap-1.5">
            {available.map((k) => (
              <button key={k.key} type="button" onClick={() => toggle(k.key)} aria-pressed={picked.includes(k.key)}
                className={cn('h-7 px-2.5 rounded-full text-[12px] border border-hairline flex items-center gap-1',
                  picked.includes(k.key) ? 'bg-gold-soft text-gold-text' : 'text-ink-mute')}>
                <Icon name={k.icon} className="text-[14px]" />{k.label}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          {err && <div className="text-[12.5px] text-bad mb-3">{err}</div>}
          {!items.length && !loading && <div className="crm-empty">Nothing recorded with this customer yet</div>}
          <ol className="relative">
            {items.map((i, idx) => (
              <li key={`${i.kind}-${i.ref_name}-${i.when}-${idx}`} className="flex gap-3 py-3 border-b border-hairline last:border-b-0">
                <span className="w-8 h-8 rounded-full bg-surface-3 grid place-items-center shrink-0">
                  <Icon name={ICON[i.kind] || 'circle'} className="text-[16px] text-ink-3" />
                </span>
                <button type="button" className="min-w-0 flex-1 text-left" disabled={i.kind === 'note'}
                  onClick={() => i.kind !== 'note' && openFrappe(i.ref_doctype, i.ref_name, newTab)}>
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-[13px] text-ink font-medium truncate">{i.title || '(no subject)'}</span>
                    <span className="text-[11.5px] text-ink-mute shrink-0">{fmtDate(i.when)}</span>
                  </div>
                  {i.snippet && <div className="text-[12.5px] text-ink-3 mt-0.5 line-clamp-2 break-words">{i.snippet}</div>}
                  {i.who && <div className="text-[11px] text-ink-mute mt-0.5">{shortUser(i.who)}</div>}
                </button>
              </li>
            ))}
          </ol>
          {loading && <div className="crm-empty">Loading…</div>}
          {next && !loading && (
            <div className="pt-3 text-center">
              <Button size="sm" variant="outline" className="rounded-full" onClick={() => load(next)}>Load older</Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><div><CardTitle>Add a note</CardTitle><CardSub>Meeting notes, a call summary, anything worth keeping</CardSub></div></CardHeader>
        <CardContent>
          <textarea ref={noteRef} value={note} onChange={(e) => setNote(e.target.value)} rows={5}
            placeholder="e.g. Visited the farm with their buyer — wants samples of the new red varieties by Friday."
            className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-[13px] outline-none focus:ring-1 focus:ring-ring" />
          <div className="mt-2 flex items-center gap-3">
            <Button size="sm" onClick={saveNote} disabled={saving || !note.trim()}
              className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-4">
              {saving ? 'Saving…' : 'Save note'}
            </Button>
            <span className="text-[11.5px] text-ink-mute">Also shows on the customer in the desk</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
