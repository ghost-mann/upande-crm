import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import Icon from './Icon';
import LinkSearch from './LinkSearch';
import { useStore } from '../store';
import { assignableUsersApi } from '../api';
import {
  TASK_REF_DOCTYPES, TASK_STATUSES, TASK_PRIORITIES, stripHtml, toHtml,
} from '@/lib/activity';

const L = 'text-[10px] uppercase tracking-[0.14em] text-ink-mute font-medium mb-1.5 block';
const SEL = 'h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm outline-none focus:ring-1 focus:ring-ring';

// today + n days, as the YYYY-MM-DD a date input expects.
function dueDate(days) {
  const n = Number(days);
  if (!Number.isFinite(n) || n < 0) return '';
  const d = new Date();
  d.setDate(d.getDate() + n);
  const p = (x) => String(x).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export default function TaskDialog() {
  const t = useStore((s) => s.taskDialog);
  const closeTaskDialog = useStore((s) => s.closeTaskDialog);
  const saveTask = useStore((s) => s.saveTask);
  const org = useStore((s) => s.org);

  const [form, setForm] = useState(null);
  const [users, setUsers] = useState([]);
  const [err, setErr] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!t) { setForm(null); return; }
    // New tasks open on the organisation's configured defaults; an existing task
    // and an explicitly prefilled one keep their own values.
    const isNew = !t.name;
    setForm({
      name: t.name,
      description: stripHtml(t.description),
      date: t.date || (isNew ? dueDate(org.default_task_due_days) : ''),
      priority: t.priority || (isNew ? org.default_task_priority : '') || 'Medium',
      status: t.status || 'Open',
      reference_type: t.reference_type || '',
      reference_name: t.reference_name || '',
      allocated_to: t.allocated_to || '',
    });
    setErr('');
    setSaving(false);
    assignableUsersApi().then((u) => setUsers(u || [])).catch(() => setUsers([]));
    // `org` is intentionally not a dependency: re-seeding an open dialog because
    // a manager changed a default in another tab would discard what was typed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t]);

  if (!t || !form) return null;

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  async function submit() {
    if (!form.description.trim()) { setErr('Description is required.'); return; }
    if (form.reference_type && !form.reference_name) {
      setErr('Pick the linked record, or clear the reference type.'); return;
    }
    setSaving(true); setErr('');
    try {
      await saveTask({
        ...form,
        description: toHtml(form.description),
        date: form.date || null,
        reference_type: form.reference_type || null,
        reference_name: form.reference_name || null,
        allocated_to: form.allocated_to || null,
      });
      closeTaskDialog();
    } catch (e) {
      setErr(e.message || 'Could not save the task.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4">
      <div className="flex flex-col w-[600px] max-w-[96vw] max-h-[92vh] rounded-2xl shadow-2xl border border-hairline bg-surface overflow-hidden">
        <div className="h-11 shrink-0 bg-grad-ink text-white flex items-center gap-1 pl-4 pr-1.5">
          <span className="text-[14px] font-semibold truncate flex-1">
            {form.name ? `Edit task · ${form.name}` : 'New task'}
          </span>
          <button className="w-7 h-7 rounded flex items-center justify-center hover:bg-white/15"
            onClick={closeTaskDialog} title="Close">
            <Icon name="close" className="text-[18px]" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto crm-scroll p-5 grid gap-4">
          <div>
            <label className={L}>Description</label>
            <Textarea value={form.description} onChange={(e) => set({ description: e.target.value })}
              placeholder="What needs doing?" className="min-h-[92px]" />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className={L}>Due</label>
              <Input type="date" value={form.date} onChange={(e) => set({ date: e.target.value })} />
            </div>
            <div>
              <label className={L}>Priority</label>
              <select className={SEL} value={form.priority} onChange={(e) => set({ priority: e.target.value })}>
                {TASK_PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className={L}>Status</label>
              <select className={SEL} value={form.status} onChange={(e) => set({ status: e.target.value })}>
                {TASK_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>

          {/* A task's own assignee is its allocated_to field. This is NOT the
              assign action — routing it through assign_to.add would create a
              second ToDo pointing at this one. */}
          <div>
            <label className={L}>Assigned to</label>
            <select className={SEL} value={form.allocated_to}
              onChange={(e) => set({ allocated_to: e.target.value })}>
              <option value="">— nobody —</option>
              {users.map((u) => <option key={u.name} value={u.name}>{u.full_name} · {u.name}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-[160px_1fr] gap-3">
            <div>
              <label className={L}>Linked to</label>
              <select className={SEL} value={form.reference_type}
                onChange={(e) => set({ reference_type: e.target.value, reference_name: '' })}>
                <option value="">— none —</option>
                {TASK_REF_DOCTYPES.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <div>
              <label className={L}>Record</label>
              <LinkSearch doctype={form.reference_type} value={form.reference_name}
                onChange={(v) => set({ reference_name: v })}
                placeholder={form.reference_type ? `Find a ${form.reference_type}…` : ''} />
            </div>
          </div>
        </div>

        <div className="shrink-0 flex items-center gap-3 px-5 py-3 border-t border-line">
          <Button size="sm" onClick={submit} disabled={saving}
            className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5">
            <Icon name="check" className="text-[16px]" />{saving ? 'Saving…' : (form.name ? 'Save changes' : 'Create task')}
          </Button>
          <button onClick={closeTaskDialog} className="text-[13px] text-ink-3 hover:text-ink">Cancel</button>
          {err && <span className="ml-auto text-[12px] text-bad text-right">{err}</span>}
        </div>
      </div>
    </div>
  );
}
