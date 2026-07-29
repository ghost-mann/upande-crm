import { useEffect, useState } from 'react';
import { fmt } from '@shared/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import Icon from './Icon';
import { useStore } from '../store';
import { campaignRecipientsApi } from '../api';
import { ENROL_TARGETS, TARGET_ICON } from '@/lib/campaigns';
import { cn } from '@/lib/utils';

const L = 'text-[10px] uppercase tracking-[0.14em] text-ink-mute font-medium mb-1.5 block';
const SEL = 'h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm outline-none focus:ring-1 focus:ring-ring';

function today() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// Enrol recipients in a campaign.
//
// Bulk on purpose, and the result is per-recipient: ERPNext refuses a Lead with no
// email address and a duplicate active enrolment, both of which are facts about one
// recipient rather than the batch. The dialog stays open on partial success and
// shows exactly which ones failed and why.
export default function EnrolDialog() {
  const state = useStore((s) => s.enrolDialog);
  const close = useStore((s) => s.closeEnrolDialog);
  const enrol = useStore((s) => s.enrolCampaign);
  const campaigns = useStore((s) => s.data.campaigns?.campaigns) || [];

  const [form, setForm] = useState(null);
  const [options, setOptions] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!state) { setForm(null); setResult(null); return; }
    setForm({
      campaign: state.campaign || '',
      target: state.target || 'Lead',
      recipients: [],
      start_date: today(),
      attribute: true,
    });
    setSearch(''); setErr(''); setResult(null);
  }, [state]);

  useEffect(() => {
    if (!form?.target) return;
    let dead = false;
    setLoading(true);
    campaignRecipientsApi(form.target, search)
      .then((r) => { if (!dead) setOptions(r || []); })
      .catch(() => { if (!dead) setOptions([]); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [form?.target, search]);

  if (!state || !form) return null;
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const chosen = new Set(form.recipients);
  const campaign = campaigns.find((c) => c.name === form.campaign);

  function toggle(name) {
    const next = new Set(chosen);
    if (next.has(name)) next.delete(name); else next.add(name);
    set({ recipients: [...next] });
    setResult(null);
  }

  async function submit() {
    if (!form.campaign) { setErr('Pick a campaign.'); return; }
    if (!form.recipients.length) { setErr('Pick at least one recipient.'); return; }
    setBusy(true); setErr(''); setResult(null);
    try {
      const r = await enrol({
        campaign: form.campaign,
        target: form.target,
        recipients: form.recipients,
        start_date: form.start_date,
        attribute: form.attribute ? 1 : 0,
      });
      setResult(r);
      // Close only when everything landed; otherwise leave the failures on screen.
      if (!r.failed) setTimeout(close, 1400);
    } catch (e) {
      setErr(e.message || 'Could not enrol these recipients.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4">
      <div className="flex flex-col w-[680px] max-w-[96vw] max-h-[92vh] rounded-2xl shadow-2xl border border-hairline bg-surface overflow-hidden">
        <div className="h-11 shrink-0 bg-grad-ink text-white flex items-center gap-1 pl-4 pr-1.5">
          <span className="text-[14px] font-semibold truncate flex-1">Enrol in a campaign</span>
          <button className="w-7 h-7 rounded flex items-center justify-center hover:bg-white/15"
            onClick={close} title="Close"><Icon name="close" className="text-[18px]" /></button>
        </div>

        <div className="flex-1 overflow-y-auto crm-scroll p-5 grid gap-4">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_150px] gap-3">
            <div>
              <label className={L}>Campaign</label>
              <select className={SEL} value={form.campaign}
                onChange={(e) => { set({ campaign: e.target.value }); setResult(null); }}>
                <option value="">Select a campaign…</option>
                {campaigns.map((c) => (
                  <option key={c.name} value={c.name} disabled={!c.steps}>
                    {c.title}{c.steps ? ` · ${c.steps} step${c.steps > 1 ? 's' : ''}` : ' · no schedule'}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={L}>Start date</label>
              <Input type="date" min={today()} value={form.start_date}
                onChange={(e) => set({ start_date: e.target.value })} />
            </div>
          </div>

          {campaign && !campaign.steps && (
            <div className="text-[12px] text-bad flex items-start gap-2">
              <Icon name="error" className="text-[15px] mt-px" />
              This campaign has no schedule, so there is nothing to send. Add a step first.
            </div>
          )}

          <div>
            <label className={L}>Send to</label>
            <div className="flex gap-2">
              {ENROL_TARGETS.map((t) => (
                <button key={t}
                  onClick={() => { set({ target: t, recipients: [] }); setResult(null); }}
                  className={cn(
                    'flex items-center gap-1.5 text-[12.5px] font-medium px-3.5 py-2 rounded-full transition-colors',
                    form.target === t ? 'bg-grad-ink text-white' : 'text-ink-4 hover:text-ink hover:bg-hover',
                  )}>
                  <Icon name={TARGET_ICON[t]} className="text-[15px]" />{t}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className={L}>
                Recipients{form.recipients.length ? ` · ${form.recipients.length} selected` : ''}
              </label>
              <Input value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder="Search…" className="h-8 w-[190px] text-[12.5px]" />
            </div>
            <div className="rounded-xl border border-hairline max-h-[240px] overflow-y-auto crm-scroll">
              {loading && <div className="crm-empty py-4">Loading…</div>}
              {!loading && !options.length && <div className="crm-empty py-4">Nothing found</div>}
              {!loading && options.map((o) => (
                <button key={o.name} onClick={() => o.eligible && toggle(o.name)}
                  disabled={!o.eligible}
                  className={cn(
                    'w-full flex items-center gap-2.5 px-3 py-2 text-left border-b border-hairline last:border-b-0',
                    o.eligible ? 'hover:bg-hover cursor-pointer' : 'opacity-55 cursor-not-allowed',
                    chosen.has(o.name) && 'bg-gold-soft',
                  )}>
                  <Icon name={chosen.has(o.name) ? 'check_circle' : 'radio_button_unchecked'}
                    className={cn('text-[16px]', chosen.has(o.name) ? 'text-gold-text' : 'text-ink-mute')} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[13px] text-ink truncate">{o.label}</span>
                    <span className={cn('block text-[11px]', o.eligible ? 'text-ink-mute' : 'text-bad')}>
                      {o.detail}
                    </span>
                  </span>
                </button>
              ))}
            </div>
            <div className="text-[11px] text-ink-mute mt-1.5">
              Greyed-out rows have no email address, which ERPNext refuses to enrol.
            </div>
          </div>

          <div className="rounded-xl border border-hairline p-3.5">
            <Checkbox checked={form.attribute} onCheckedChange={(v) => set({ attribute: !!v })}
              label="Tag these leads with the campaign for attribution" />
            <div className="text-[11.5px] text-ink-mute mt-1.5">
              Sets each lead's campaign field, which is what makes campaign performance
              measurable later. Applies to leads only.
            </div>
          </div>

          {/* Nothing has been sent at this point — say so rather than implying a blast. */}
          <div className="flex items-start gap-2 text-[12px] text-ink-2">
            <Icon name="schedule" className="text-[15px] mt-px shrink-0" />
            Emails go out on the daily scheduler run, not immediately.
          </div>

          {result && (
            <div className="rounded-xl border border-hairline p-3.5 grid gap-2">
              <div className="text-[13px] font-medium text-ink">
                {fmt(result.enrolled)} enrolled{result.failed ? `, ${fmt(result.failed)} failed` : ''}
              </div>
              {(result.results || []).filter((r) => !r.ok).map((r) => (
                <div key={r.recipient} className="text-[12px] text-bad">
                  {r.recipient}: {r.error}
                </div>
              ))}
              {!result.failed && (
                <div className="text-[12px] text-good">{result.note}</div>
              )}
            </div>
          )}
        </div>

        <div className="shrink-0 flex items-center gap-3 px-5 py-3 border-t border-line">
          <Button size="sm" onClick={submit}
            disabled={busy || !form.recipients.length || (campaign && !campaign.steps)}
            className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5 disabled:opacity-40">
            <Icon name="send" className="text-[16px] " />
            {busy ? 'Enrolling…' : `Enrol ${form.recipients.length || ''}`.trim()}
          </Button>
          <button onClick={close} className="text-[13px] text-ink-3 hover:text-ink">Close</button>
          {err && <span className="ml-auto text-[12px] text-bad text-right max-w-[55%]">{err}</span>}
        </div>
      </div>
    </div>
  );
}
