import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import Icon from './Icon';
import { useStore } from '../store';
import { emailTemplatesApi } from '../api';

const L = 'text-[10px] uppercase tracking-[0.14em] text-ink-mute font-medium mb-1.5 block';
const SEL = 'h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm outline-none focus:ring-1 focus:ring-ring';

// Define a campaign: a name and a drip schedule of (template, send after N days).
//
// The schedule is the campaign — a campaign with no steps cannot be enrolled
// against, because ERPNext's controller refuses it. So the dialog nudges toward at
// least one step rather than letting an empty one be saved and fail later.
export default function CampaignDialog() {
  const c = useStore((s) => s.campaignDialog);
  const close = useStore((s) => s.closeCampaignDialog);
  const saveCampaign = useStore((s) => s.saveCampaign);

  const [form, setForm] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [err, setErr] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!c) { setForm(null); return; }
    setForm({
      name: c.name,
      campaign_name: c.title || c.campaign_name || '',
      description: c.description || '',
      schedule: (c.schedule || []).map((s) => ({ ...s })),
    });
    setErr(''); setSaving(false);
    emailTemplatesApi().then((t) => setTemplates(t || [])).catch(() => setTemplates([]));
  }, [c]);

  if (!c || !form) return null;
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  function addStep() {
    const used = new Set(form.schedule.map((s) => Number(s.send_after_days)));
    let day = form.schedule.length ? Math.max(...used) + 3 : 0;
    while (used.has(day)) day += 1;
    set({ schedule: [...form.schedule, { email_template: templates[0]?.name || '', send_after_days: day }] });
  }

  async function submit() {
    if (!form.campaign_name.trim()) { setErr('Give the campaign a name.'); return; }
    if (!form.schedule.length) { setErr('Add at least one step — a campaign with no schedule cannot send.'); return; }
    if (form.schedule.some((s) => !s.email_template)) { setErr('Every step needs a template.'); return; }
    const days = form.schedule.map((s) => Number(s.send_after_days));
    if (new Set(days).size !== days.length) { setErr('Two steps share the same day offset.'); return; }
    setSaving(true); setErr('');
    try {
      await saveCampaign({
        name: form.name,
        campaign_name: form.campaign_name.trim(),
        description: form.description,
        schedule: form.schedule.map((s) => ({
          email_template: s.email_template, send_after_days: Number(s.send_after_days) || 0,
        })),
      });
      close();
    } catch (e) {
      setErr(e.message || 'Could not save the campaign.');
    } finally {
      setSaving(false);
    }
  }

  const sorted = [...form.schedule].sort((a, b) => a.send_after_days - b.send_after_days);
  const span = sorted.length ? Number(sorted[sorted.length - 1].send_after_days) : 0;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4">
      <div className="flex flex-col w-[660px] max-w-[96vw] max-h-[92vh] rounded-2xl shadow-2xl border border-hairline bg-surface overflow-hidden">
        <div className="h-11 shrink-0 bg-grad-ink text-white flex items-center gap-1 pl-4 pr-1.5">
          <span className="text-[14px] font-semibold truncate flex-1">
            {form.name ? `Edit campaign · ${form.campaign_name}` : 'New campaign'}
          </span>
          <button className="w-7 h-7 rounded flex items-center justify-center hover:bg-white/15"
            onClick={close} title="Close"><Icon name="close" className="text-[18px]" /></button>
        </div>

        <div className="flex-1 overflow-y-auto crm-scroll p-5 grid gap-4">
          <div>
            <label className={L}>Campaign name</label>
            <Input value={form.campaign_name} onChange={(e) => set({ campaign_name: e.target.value })}
              placeholder="Flowers Expo Moscow" />
          </div>
          <div>
            <label className={L}>Description</label>
            <Textarea value={form.description} onChange={(e) => set({ description: e.target.value })}
              placeholder="What this campaign is for, and who it targets…" className="min-h-[70px]" />
          </div>

          <div className="rounded-xl border border-hairline p-3.5">
            <div className="flex items-center justify-between mb-2.5">
              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] text-ink-mute font-medium">
                  Email schedule
                </div>
                <div className="text-[11.5px] text-ink-mute mt-0.5">
                  {sorted.length
                    ? `${sorted.length} step${sorted.length > 1 ? 's' : ''} spanning ${span} day${span === 1 ? '' : 's'} from enrolment`
                    : 'No steps yet — a campaign needs at least one to send'}
                </div>
              </div>
              <Button size="sm" variant="outline" onClick={addStep} className="h-8 rounded-full">
                <Icon name="add" className="text-[15px]" />Add step
              </Button>
            </div>

            {form.schedule.length === 0 && (
              <div className="crm-empty py-4">Add a template and when it should go out</div>
            )}

            <div className="grid gap-2">
              {form.schedule.map((step, i) => (
                <div key={i} className="grid grid-cols-[1fr_130px_auto] gap-2 items-center">
                  <select className={SEL} value={step.email_template}
                    onChange={(e) => {
                      const next = [...form.schedule];
                      next[i] = { ...next[i], email_template: e.target.value };
                      set({ schedule: next });
                    }}>
                    <option value="">Select a template…</option>
                    {templates.map((t) => (
                      <option key={t.name} value={t.name}>{t.name} — {t.subject}</option>
                    ))}
                  </select>
                  <div className="flex items-center gap-1.5">
                    <Input type="number" min={0} max={365} value={step.send_after_days}
                      onChange={(e) => {
                        const next = [...form.schedule];
                        next[i] = { ...next[i], send_after_days: Number(e.target.value) || 0 };
                        set({ schedule: next });
                      }}
                      className="h-9 w-[64px] text-right" />
                    <span className="text-[11px] text-ink-mute">days after</span>
                  </div>
                  <button className="text-ink-3 hover:text-bad px-1" title="Remove step"
                    onClick={() => set({ schedule: form.schedule.filter((_, j) => j !== i) })}>
                    <Icon name="close" className="text-[16px]" />
                  </button>
                </div>
              ))}
            </div>
            {!templates.length && (
              <div className="text-[11.5px] text-warn mt-2.5">
                No email templates exist yet — create one in desk first.
              </div>
            )}
          </div>
        </div>

        <div className="shrink-0 flex items-center gap-3 px-5 py-3 border-t border-line">
          <Button size="sm" onClick={submit} disabled={saving}
            className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5">
            <Icon name="check" className="text-[16px]" />
            {saving ? 'Saving…' : (form.name ? 'Save changes' : 'Create campaign')}
          </Button>
          <button onClick={close} className="text-[13px] text-ink-3 hover:text-ink">Cancel</button>
          {err && <span className="ml-auto text-[12px] text-bad text-right max-w-[60%]">{err}</span>}
        </div>
      </div>
    </div>
  );
}
