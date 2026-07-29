import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import Icon from './Icon';
import LinkSearch from './LinkSearch';
import { useStore } from '../store';
import { callTypesApi, callTypeAddApi } from '../api';
import { TASK_REF_DOCTYPES, toLocalInput, fromLocalInput, stripHtml } from '@/lib/activity';
import { CALL_DIRECTIONS, CALL_STATUSES } from '@/lib/calls';
import { cn } from '@/lib/utils';

const L = 'text-[10px] uppercase tracking-[0.14em] text-ink-mute font-medium mb-1.5 block';
const SEL = 'h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm outline-none focus:ring-1 focus:ring-ring';

function todayISO(offset = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export default function CallDialog() {
  const call = useStore((s) => s.callDialog);
  const close = useStore((s) => s.closeCallDialog);
  const saveCall = useStore((s) => s.saveCall);
  const org = useStore((s) => s.org);

  const [form, setForm] = useState(null);
  const [types, setTypes] = useState([]);
  const [newType, setNewType] = useState('');
  const [addingType, setAddingType] = useState(false);
  const [err, setErr] = useState('');
  const [warn, setWarn] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!call) { setForm(null); return; }
    const isNew = !call.name;
    setForm({
      name: call.name,
      type: call.type || 'Outgoing',
      number: call.number || call.to || call.from || '',
      status: call.status || 'Completed',
      // Stored in seconds; entered in minutes.
      duration: call.duration ? Math.round((call.duration / 60) * 10) / 10 : '',
      start_time: toLocalInput(call.start_time) || toLocalInput(new Date().toISOString()),
      summary: stripHtml(call.summary),
      type_of_call: call.type_of_call || '',
      reference_doctype: call.reference_doctype || '',
      reference_name: call.reference_name || '',
      follow_up: false,
      follow_up_description: '',
      follow_up_date: todayISO(Number(org.default_task_due_days) || 0),
    });
    setErr(''); setWarn(''); setSaving(false); setNewType('');
    callTypesApi().then((t) => setTypes(t || [])).catch(() => setTypes([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [call]);

  if (!call || !form) return null;

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  async function addType() {
    const label = newType.trim();
    if (!label) return;
    setAddingType(true);
    try {
      const r = await callTypeAddApi(label);
      setTypes((t) => (t.includes(r.name) ? t : [...t, r.name].sort()));
      set({ type_of_call: r.name });
      setNewType('');
    } catch (e) {
      setErr(e.message || 'Could not add that call type.');
    } finally {
      setAddingType(false);
    }
  }

  async function submit() {
    if (!form.number.trim()) { setErr('A phone number is required.'); return; }
    if (form.reference_doctype && !form.reference_name) {
      setErr('Pick the linked record, or clear the reference type.'); return;
    }
    setSaving(true); setErr(''); setWarn('');
    try {
      const payload = {
        name: form.name,
        type: form.type,
        status: form.status,
        // The backend puts the number on the side the direction implies.
        [form.type === 'Incoming' ? 'from' : 'to']: form.number.trim(),
        duration: form.duration === '' ? 0 : Number(form.duration),
        start_time: fromLocalInput(form.start_time),
        summary: form.summary,
        type_of_call: form.type_of_call || null,
        reference_doctype: form.reference_doctype || null,
        reference_name: form.reference_name || null,
      };
      if (form.follow_up) {
        payload.follow_up = {
          description: form.follow_up_description,
          date: form.follow_up_date || null,
        };
      }
      const r = await saveCall(payload);
      // The call saved even if its follow-up did not; say so rather than closing
      // silently on a half-done action.
      if (r?.follow_up_error) {
        setWarn(`Call logged, but the follow-up task failed: ${r.follow_up_error}`);
        setSaving(false);
        return;
      }
      close();
    } catch (e) {
      setErr(e.message || 'Could not log the call.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4">
      <div className="flex flex-col w-[620px] max-w-[96vw] max-h-[92vh] rounded-2xl shadow-2xl border border-hairline bg-surface overflow-hidden">
        <div className="h-11 shrink-0 bg-grad-ink text-white flex items-center gap-1 pl-4 pr-1.5">
          <span className="text-[14px] font-semibold truncate flex-1">
            {form.name ? `Edit call · ${form.name}` : 'Log a call'}
          </span>
          <button className="w-7 h-7 rounded flex items-center justify-center hover:bg-white/15"
            onClick={close} title="Close">
            <Icon name="close" className="text-[18px]" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto crm-scroll p-5 grid gap-4">
          {/* Direction first: it is the first thing you know about a call. */}
          <div>
            <label className={L}>Direction</label>
            <div className="flex gap-2">
              {CALL_DIRECTIONS.map((d) => (
                <button
                  key={d}
                  onClick={() => set({ type: d })}
                  className={cn(
                    'flex items-center gap-1.5 text-[12.5px] font-medium px-3.5 py-2 rounded-full transition-colors',
                    form.type === d ? 'bg-grad-ink text-white' : 'text-ink-4 hover:text-ink hover:bg-hover',
                  )}
                >
                  <Icon name={d === 'Incoming' ? 'call_received' : 'call_made'} className="text-[15px]" />
                  {d}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className={L}>{form.type === 'Incoming' ? 'Caller number' : 'Number called'}</label>
              <Input value={form.number} onChange={(e) => set({ number: e.target.value })}
                placeholder="+254…" />
            </div>
            <div>
              <label className={L}>When</label>
              <Input type="datetime-local" value={form.start_time}
                onChange={(e) => set({ start_time: e.target.value })} />
            </div>
            <div>
              <label className={L}>Duration (minutes)</label>
              <Input type="number" min={0} step={0.5} value={form.duration}
                onChange={(e) => set({ duration: e.target.value === '' ? '' : Number(e.target.value) })} />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className={L}>Outcome</label>
              <select className={SEL} value={form.status} onChange={(e) => set({ status: e.target.value })}>
                {CALL_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className={L}>Call type</label>
              <select className={SEL} value={form.type_of_call}
                onChange={(e) => set({ type_of_call: e.target.value })}>
                <option value="">— none —</option>
                {types.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>

          {/* The disposition vocabulary starts empty on a fresh site, so it has to
              be seedable from here rather than only in desk. */}
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label className={L}>Add a call type</label>
              <Input value={newType} onChange={(e) => setNewType(e.target.value)}
                placeholder="Price query, Complaint, Follow-up…"
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addType(); } }} />
            </div>
            <Button size="sm" variant="outline" className="h-9" disabled={addingType || !newType.trim()}
              onClick={addType}>
              <Icon name="add" className="text-[16px]" />Add
            </Button>
          </div>

          <div>
            <label className={L}>What was said</label>
            <Textarea value={form.summary} onChange={(e) => set({ summary: e.target.value })}
              placeholder="Outcome, next steps, anything promised…" className="min-h-[80px]" />
          </div>

          <div className="grid grid-cols-[160px_1fr] gap-3">
            <div>
              <label className={L}>Linked to</label>
              <select className={SEL} value={form.reference_doctype}
                onChange={(e) => set({ reference_doctype: e.target.value, reference_name: '' })}>
                <option value="">— none —</option>
                {TASK_REF_DOCTYPES.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <div>
              <label className={L}>Record</label>
              <LinkSearch doctype={form.reference_doctype} value={form.reference_name}
                onChange={(v) => set({ reference_name: v })}
                placeholder={form.reference_doctype ? `Find a ${form.reference_doctype}…` : ''} />
            </div>
          </div>

          {/* Follow-up: collapsed until switched on, so it costs nothing visually. */}
          <div className="rounded-xl border border-hairline p-3.5">
            <Checkbox checked={form.follow_up}
              onCheckedChange={(v) => set({ follow_up: v ? 1 : 0 })}
              label="Create a follow-up task" />
            {form.follow_up ? (
              <div className="mt-3 grid grid-cols-1 md:grid-cols-[1fr_170px] gap-3">
                <div>
                  <label className={L}>Task</label>
                  <Input value={form.follow_up_description}
                    onChange={(e) => set({ follow_up_description: e.target.value })}
                    placeholder="Send the revised quote" />
                </div>
                <div>
                  <label className={L}>Due</label>
                  <Input type="date" value={form.follow_up_date}
                    onChange={(e) => set({ follow_up_date: e.target.value })} />
                </div>
                <div className="md:col-span-2 text-[11px] text-ink-mute">
                  Appears in Events &amp; Tasks, assigned to you, at the priority set in
                  Settings.
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <div className="shrink-0 flex items-center gap-3 px-5 py-3 border-t border-line">
          <Button size="sm" onClick={submit} disabled={saving}
            className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5">
            <Icon name="check" className="text-[16px]" />
            {saving ? 'Saving…' : (form.name ? 'Save changes' : 'Log call')}
          </Button>
          <button onClick={close} className="text-[13px] text-ink-3 hover:text-ink">Cancel</button>
          {err && <span className="ml-auto text-[12px] text-bad text-right max-w-[60%]">{err}</span>}
          {!err && warn && <span className="ml-auto text-[12px] text-warn text-right max-w-[60%]">{warn}</span>}
        </div>
      </div>
    </div>
  );
}
