import { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import Icon from './Icon';
import LinkSearch from './LinkSearch';
import DialogShell, { LABEL, SELECT } from './DialogShell';
import { visitSaveApi, VISIT_STATUSES } from '@/lib/service';
import { toLocalInput, fromLocalInput, stripHtml } from '@/lib/activity';

// Log a farm visit by a customer, or a sales visit to one: why, who, what came
// of it, and the follow-ups — each of which becomes a task for its owner.
const TYPES = ['Customer visit to farm', 'Sales visit to customer'];
const PARTIES = ['Customer', 'Lead', 'Prospect'];

export default function VisitDialog({ visit, purposes = [], onClose, onSaved }) {
  const [form, setForm] = useState(() => ({
    visit_type: TYPES[1], party_type: 'Customer', party: '', status: 'Planned',
    visit_date: toLocalInput(new Date().toISOString()), purpose: purposes[0] || '', location: '',
    staff: '', customer_attendees: '', outcome: '', actions: [],
    ...(visit || {}),
    ...(visit?.visit_date ? { visit_date: toLocalInput(visit.visit_date) } : {}),
    ...(visit?.outcome ? { outcome: stripHtml(visit.outcome) } : {}),
  }));
  const [err, setErr] = useState('');
  const [saving, setSaving] = useState(false);
  const set = (patch) => { setForm((f) => ({ ...f, ...patch })); setErr(''); };
  const setAction = (i, patch) => set({ actions: form.actions.map((a, j) => (j === i ? { ...a, ...patch } : a)) });

  const save = async () => {
    if (!form.party) { setErr(`Pick the ${form.party_type.toLowerCase()}.`); return; }
    if (form.status === 'Completed' && !form.outcome.trim()) { setErr('Record what came of the visit before completing it.'); return; }
    if (form.actions.some((a) => !String(a.action || '').trim())) { setErr('Every follow-up needs a description.'); return; }
    setSaving(true);
    try {
      const r = await visitSaveApi({ ...form, visit_date: fromLocalInput(form.visit_date) });
      onSaved?.(r.visit);
      onClose();
    } catch (e) {
      setErr(e.message || 'Could not save the visit.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <DialogShell title={form.name ? `Visit · ${form.name}` : 'Log a visit'} onClose={onClose} onSave={save}
      saving={saving} err={err} saveLabel={form.name ? 'Save visit' : 'Log visit'} width={720}>
      <div className="grid grid-cols-2 gap-2">
        {TYPES.map((t) => (
          <button key={t} type="button" onClick={() => set({ visit_type: t })}
            className={`h-10 rounded-md border text-[13px] flex items-center justify-center gap-2 ${form.visit_type === t ? 'border-gold bg-gold-soft text-gold-text font-medium' : 'border-hairline text-ink-3'}`}>
            <Icon name={t.startsWith('Customer') ? 'agriculture' : 'directions_car'} className="text-[17px]" />{t}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-[150px_1fr] gap-3">
        <div>
          <label className={LABEL}>{form.visit_type.startsWith('Customer') ? 'Visitor is a' : 'Visiting a'}</label>
          <select className={SELECT} value={form.party_type} disabled={!!visit?.lockParty}
            onChange={(e) => set({ party_type: e.target.value, party: '' })}>
            {PARTIES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div>
          <label className={LABEL}>{form.party_type}</label>
          <LinkSearch doctype={form.party_type} value={form.party} disabled={!!visit?.lockParty}
            onChange={(v) => set({ party: v })} placeholder={`Find a ${form.party_type.toLowerCase()}…`} />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className={LABEL}>When</label>
          <Input type="datetime-local" value={form.visit_date || ''} onChange={(e) => set({ visit_date: e.target.value })} />
        </div>
        <div>
          <label className={LABEL}>Purpose</label>
          <select className={SELECT} value={form.purpose} onChange={(e) => set({ purpose: e.target.value })}>
            {purposes.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div>
          <label className={LABEL}>Status</label>
          <select className={SELECT} value={form.status} onChange={(e) => set({ status: e.target.value })}>
            {VISIT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className={LABEL}>Where</label>
          <Input value={form.location || ''} onChange={(e) => set({ location: e.target.value })} placeholder="Farm, their office…" />
        </div>
        <div>
          <label className={LABEL}>Our staff</label>
          <Input value={form.staff || ''} onChange={(e) => set({ staff: e.target.value })} placeholder="Who went / hosted" />
        </div>
        <div>
          <label className={LABEL}>Their people</label>
          <Input value={form.customer_attendees || ''} onChange={(e) => set({ customer_attendees: e.target.value })} placeholder="Buyer, QA manager…" />
        </div>
      </div>

      <div>
        <label className={LABEL}>What came of it {form.status === 'Completed' ? '(required)' : ''}</label>
        <Textarea value={form.outcome || ''} onChange={(e) => set({ outcome: e.target.value })}
          placeholder="Decisions, feedback on varieties, prices discussed, concerns raised…" className="min-h-[80px]" />
      </div>

      <div className="rounded-xl border border-hairline p-3.5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[13px] text-ink font-medium">Follow-ups</span>
          <button type="button" onClick={() => set({ actions: [...form.actions, { action: '', assigned_to: '', due_date: '' }] })}
            className="text-[12.5px] text-gold-text flex items-center gap-1 hover:underline">
            <Icon name="add" className="text-[16px]" />Add follow-up
          </button>
        </div>
        {!form.actions.length && <div className="text-[12px] text-ink-mute">Each follow-up becomes a task for its owner when you save.</div>}
        {form.actions.map((a, i) => (
          <div key={a.name || i} className="grid grid-cols-[1fr_190px_140px_28px] gap-2 mb-2 items-center">
            <Input value={a.action || ''} onChange={(e) => setAction(i, { action: e.target.value })} placeholder="e.g. Send a sample box of new reds" />
            <LinkSearch doctype="User" value={a.assigned_to} onChange={(v) => setAction(i, { assigned_to: v })} placeholder="Owner" />
            <Input type="date" value={a.due_date || ''} onChange={(e) => setAction(i, { due_date: e.target.value })} />
            {a.todo ? (
              <Icon name="task_alt" className="text-[18px] text-good" title="Task created" />
            ) : (
              <button type="button" onClick={() => set({ actions: form.actions.filter((_, j) => j !== i) })} title="Remove"
                className="text-ink-mute hover:text-bad"><Icon name="close" className="text-[18px]" /></button>
            )}
          </div>
        ))}
      </div>
    </DialogShell>
  );
}
