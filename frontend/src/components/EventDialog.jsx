import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import Icon from './Icon';
import LinkSearch from './LinkSearch';
import { useStore } from '../store';
import { myCalendarsApi } from '../api';
import {
  PARTICIPANT_DOCTYPES, EVENT_CATEGORIES, EVENT_STATUSES, REPEAT_ON,
  toLocalInput, fromLocalInput, stripHtml, toHtml,
} from '@/lib/activity';

const WEEKDAYS = [
  ['monday', 'Mon'], ['tuesday', 'Tue'], ['wednesday', 'Wed'], ['thursday', 'Thu'],
  ['friday', 'Fri'], ['saturday', 'Sat'], ['sunday', 'Sun'],
];

const L = 'text-[10px] uppercase tracking-[0.14em] text-ink-mute font-medium mb-1.5 block';
const SEL = 'h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm outline-none focus:ring-1 focus:ring-ring';

export default function EventDialog() {
  const ev = useStore((s) => s.eventDialog);
  const closeEventDialog = useStore((s) => s.closeEventDialog);
  const saveEvent = useStore((s) => s.saveEvent);

  const [form, setForm] = useState(null);
  const [parts, setParts] = useState([]);
  const [newPart, setNewPart] = useState({ reference_doctype: 'Customer', reference_docname: '' });
  const [cals, setCals] = useState([]);
  const [err, setErr] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!ev) { setForm(null); return; }
    setForm({
      name: ev.name,
      subject: ev.subject || '',
      event_category: ev.event_category || 'Meeting',
      event_type: ev.event_type || 'Private',
      starts_on: toLocalInput(ev.starts_on) || toLocalInput(ev.prefillStart),
      ends_on: toLocalInput(ev.ends_on),
      all_day: ev.all_day ? 1 : 0,
      status: ev.status || 'Open',
      location: ev.location || '',
      description: stripHtml(ev.description),
      repeat_this_event: ev.repeat_this_event ? 1 : 0,
      repeat_on: ev.repeat_on || 'Weekly',
      repeat_till: ev.repeat_till || '',
      monday: ev.monday ? 1 : 0, tuesday: ev.tuesday ? 1 : 0, wednesday: ev.wednesday ? 1 : 0,
      thursday: ev.thursday ? 1 : 0, friday: ev.friday ? 1 : 0, saturday: ev.saturday ? 1 : 0,
      sunday: ev.sunday ? 1 : 0,
      sync_with_google_calendar: ev.sync_with_google_calendar ? 1 : 0,
      google_calendar: ev.google_calendar || '',
      add_video_conferencing: ev.add_video_conferencing ? 1 : 0,
    });
    setParts(ev.participants || []);
    setNewPart({ reference_doctype: 'Customer', reference_docname: '' });
    setErr('');
    setSaving(false);
    // Sync is only offered when the signed-in user has an authorized calendar —
    // otherwise the toggle would create an Event doomed to fail on push.
    myCalendarsApi().then((c) => setCals(c || [])).catch(() => setCals([]));
  }, [ev]);

  if (!ev || !form) return null;

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  function addParticipant() {
    if (!newPart.reference_docname) { setErr('Pick a record to add as a participant.'); return; }
    const dup = parts.some((p) => p.reference_doctype === newPart.reference_doctype
      && p.reference_docname === newPart.reference_docname);
    if (dup) { setErr('That participant is already on this event.'); return; }
    setParts((p) => [...p, { ...newPart }]);
    setNewPart({ reference_doctype: newPart.reference_doctype, reference_docname: '' });
    setErr('');
  }

  async function submit() {
    if (!form.subject.trim()) { setErr('Subject is required.'); return; }
    if (!form.starts_on) { setErr('Pick a start date and time.'); return; }
    if (form.ends_on && form.ends_on < form.starts_on) { setErr('End must be on or after the start.'); return; }
    if (form.repeat_this_event && form.repeat_on === 'Weekly'
        && !WEEKDAYS.some(([k]) => form[k])) {
      setErr('Pick at least one weekday for a weekly repeat.'); return;
    }
    setSaving(true); setErr('');
    try {
      await saveEvent({
        ...form,
        starts_on: fromLocalInput(form.starts_on),
        ends_on: form.ends_on ? fromLocalInput(form.ends_on) : null,
        repeat_till: form.repeat_this_event ? (form.repeat_till || null) : null,
        description: toHtml(form.description),
        google_calendar: form.google_calendar || null,
        participants: parts,
      });
      closeEventDialog();
    } catch (e) {
      setErr(e.message || 'Could not save the event.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4">
      <div className="flex flex-col w-[720px] max-w-[96vw] max-h-[92vh] rounded-2xl shadow-2xl border border-hairline bg-surface overflow-hidden">
        <div className="h-11 shrink-0 bg-grad-ink text-white flex items-center gap-1 pl-4 pr-1.5">
          <span className="text-[14px] font-semibold truncate flex-1">
            {form.name ? `Edit event · ${form.name}` : 'New event'}
          </span>
          <button className="w-7 h-7 rounded flex items-center justify-center hover:bg-white/15"
            onClick={closeEventDialog} title="Close">
            <Icon name="close" className="text-[18px]" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto crm-scroll p-5 grid gap-4">
          <div>
            <label className={L}>Subject</label>
            <Input value={form.subject} onChange={(e) => set({ subject: e.target.value })}
              placeholder="Discovery call with…" />
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <label className={L}>Category</label>
              <select className={SEL} value={form.event_category}
                onChange={(e) => set({ event_category: e.target.value })}>
                {EVENT_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className={L}>Visibility</label>
              <select className={SEL} value={form.event_type}
                onChange={(e) => set({ event_type: e.target.value })}>
                <option value="Private">Private</option>
                <option value="Public">Public</option>
              </select>
            </div>
            <div>
              <label className={L}>Status</label>
              <select className={SEL} value={form.status} onChange={(e) => set({ status: e.target.value })}>
                {EVENT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className={L}>Location</label>
              <Input value={form.location} onChange={(e) => set({ location: e.target.value })} placeholder="Room / link" />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-3 items-end">
            <div>
              <label className={L}>Starts</label>
              <Input type="datetime-local" value={form.starts_on} onChange={(e) => set({ starts_on: e.target.value })} />
            </div>
            <div>
              <label className={L}>Ends</label>
              <Input type="datetime-local" value={form.ends_on} min={form.starts_on || undefined}
                onChange={(e) => set({ ends_on: e.target.value })} />
            </div>
            <div className="pb-2">
              <Checkbox checked={form.all_day} onCheckedChange={(v) => set({ all_day: v ? 1 : 0 })} label="All day" />
            </div>
          </div>

          <div>
            <label className={L}>Description</label>
            <Textarea value={form.description} onChange={(e) => set({ description: e.target.value })}
              placeholder="Agenda, notes…" />
          </div>

          {/* Participants — the linkage pattern actually used on this site. */}
          <div className="rounded-xl border border-hairline p-3.5">
            <div className="text-[11px] uppercase tracking-[0.14em] text-ink-mute font-medium mb-2.5">
              Participants
            </div>
            {parts.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2.5">
                {parts.map((p, i) => (
                  <span key={`${p.reference_doctype}:${p.reference_docname}`}
                    className="bdg bdg-other inline-flex items-center gap-1.5 normal-case">
                    <span className="text-ink-mute">{p.reference_doctype}</span>
                    {p.reference_docname}
                    <button onClick={() => setParts(parts.filter((_, j) => j !== i))}
                      className="hover:text-bad" title="Remove">
                      <Icon name="close" className="text-[12px]" />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <div className="grid grid-cols-[150px_1fr_auto] gap-2">
              <select className={SEL} value={newPart.reference_doctype}
                onChange={(e) => setNewPart({ reference_doctype: e.target.value, reference_docname: '' })}>
                {PARTICIPANT_DOCTYPES.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
              <LinkSearch doctype={newPart.reference_doctype} value={newPart.reference_docname}
                onChange={(v) => setNewPart((n) => ({ ...n, reference_docname: v }))}
                placeholder={`Find a ${newPart.reference_doctype}…`} />
              <Button size="sm" variant="outline" onClick={addParticipant} className="h-9">
                <Icon name="add" className="text-[16px]" />Add
              </Button>
            </div>
          </div>

          {/* Repeat — collapsed until switched on, so it costs nothing visually. */}
          <div className="rounded-xl border border-hairline p-3.5">
            <Checkbox checked={form.repeat_this_event}
              onCheckedChange={(v) => set({ repeat_this_event: v ? 1 : 0 })} label="Repeat this event" />
            {form.repeat_this_event ? (
              <div className="mt-3 grid gap-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={L}>Repeat</label>
                    <select className={SEL} value={form.repeat_on} onChange={(e) => set({ repeat_on: e.target.value })}>
                      {REPEAT_ON.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className={L}>Until</label>
                    <Input type="date" value={form.repeat_till} onChange={(e) => set({ repeat_till: e.target.value })} />
                  </div>
                </div>
                {form.repeat_on === 'Weekly' && (
                  <div className="flex flex-wrap gap-3">
                    {WEEKDAYS.map(([k, lbl]) => (
                      <Checkbox key={k} checked={form[k]} onCheckedChange={(v) => set({ [k]: v ? 1 : 0 })} label={lbl} />
                    ))}
                  </div>
                )}
              </div>
            ) : null}
          </div>

          {/* Google sync — only when the user has an authorized calendar. */}
          {cals.length > 0 && (
            <div className="rounded-xl border border-hairline p-3.5 grid gap-3">
              <Checkbox checked={form.sync_with_google_calendar}
                onCheckedChange={(v) => set({ sync_with_google_calendar: v ? 1 : 0 })}
                label="Sync with Google Calendar" />
              {form.sync_with_google_calendar ? (
                <>
                  <div>
                    <label className={L}>Calendar</label>
                    <select className={SEL} value={form.google_calendar}
                      onChange={(e) => set({ google_calendar: e.target.value })}>
                      <option value="">Select a calendar…</option>
                      {cals.map((c) => <option key={c.name} value={c.name}>{c.calendar_name}</option>)}
                    </select>
                  </div>
                  <Checkbox checked={form.add_video_conferencing}
                    onCheckedChange={(v) => set({ add_video_conferencing: v ? 1 : 0 })}
                    label="Add a Google Meet link" />
                </>
              ) : null}
            </div>
          )}
        </div>

        <div className="shrink-0 flex items-center gap-3 px-5 py-3 border-t border-line">
          <Button size="sm" onClick={submit} disabled={saving}
            className="rounded-full bg-gold text-ink hover:bg-gold-2 hover:text-white shadow-none px-5">
            <Icon name="check" className="text-[16px]" />{saving ? 'Saving…' : (form.name ? 'Save changes' : 'Create event')}
          </Button>
          <button onClick={closeEventDialog} className="text-[13px] text-ink-3 hover:text-ink">Cancel</button>
          {err && <span className="ml-auto text-[12px] text-bad text-right">{err}</span>}
        </div>
      </div>
    </div>
  );
}
