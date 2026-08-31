import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import Icon from './Icon';
import { useStore } from '../store';
import { Field, NameSelect, L } from './LeadFields';

// Capture a lead without leaving the CRM.
//
// The form is half fixed and half discovered. The fixed half is what this app
// always offers — source, industry, owner. The discovered half is whatever *this*
// site has made mandatory on Lead, read from the meta at open time. That is not
// over-engineering: this install requires eleven fields including two custom ones,
// and a hardcoded form could not create a single lead here.
//
// On save the dialog does not just close. A lead that nobody moves on is the thing
// the conversion card spends its time complaining about, so the natural next step
// is offered immediately.

const OPTIONAL_FIELDS = ['source', 'industry', 'website', 'no_of_employees'];

export default function LeadDialog() {
  const ctx = useStore((s) => s.leadDialog);
  const close = useStore((s) => s.closeLeadDialog);
  const saveLead = useStore((s) => s.saveLead);
  const options = useStore((s) => s.leadOptions);
  const openAdvance = useStore((s) => s.openAdvanceDialog);

  const [form, setForm] = useState({});
  const [err, setErr] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(null);

  useEffect(() => {
    if (!ctx) { setForm({}); setSaved(null); setErr(''); return; }
    const seed = { status: 'Lead', ...(ctx.prefill || {}) };
    (options?.required_fields || []).forEach((f) => {
      if (f.default && seed[f.fieldname] === undefined) seed[f.fieldname] = f.default;
    });
    setForm(seed);
    setErr(''); setSaving(false); setSaved(null);
  }, [ctx, options]);

  if (!ctx) return null;

  const required = options?.required_fields || [];

  // Hand the freshly saved lead to the Advance dialog, whichever hop was picked.
  const advance = (mode) => openAdvance({
    doctype: 'Lead',
    name: saved.name,
    label: saved.company_name || saved.lead_name,
    mode,
  });
  const requiredNames = new Set(required.map((f) => f.fieldname));
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const missing = required.filter((f) => {
    const v = form[f.fieldname];
    return v === undefined || v === '' || v === null;
  });

  async function submit() {
    if (!form.lead_name && !form.first_name && !form.company_name) {
      setErr('A lead needs a person or a company.'); return;
    }
    if (missing.length) {
      setErr(`Still needed: ${missing.map((f) => f.label).join(', ')}.`); return;
    }
    setSaving(true); setErr('');
    try {
      const r = await saveLead(form);
      setSaved(r);
    } catch (e) {
      setErr(e.message || 'Could not save the lead.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4">
      <div className="flex flex-col w-[720px] max-w-[96vw] max-h-[92vh] rounded-2xl shadow-2xl border border-hairline bg-surface overflow-hidden">
        <div className="h-11 shrink-0 bg-grad-ink text-white flex items-center gap-1 pl-4 pr-1.5">
          <span className="text-[14px] font-semibold truncate flex-1">
            {saved ? `Lead created · ${saved.name}` : 'New lead'}
          </span>
          <button className="w-7 h-7 rounded flex items-center justify-center hover:bg-white/15"
            onClick={close} title="Close">
            <Icon name="close" className="text-[18px]" />
          </button>
        </div>

        {saved ? (
          // The lead exists. Offering the next step here is the point — the whole
          // reason the conversion card reads the way it does is that leads get
          // captured and then left alone.
          <div className="p-6 grid gap-4">
            <div className="text-[14px] text-ink">
              <b>{saved.company_name || saved.lead_name}</b> is saved as {saved.name}.
            </div>
            <div className="text-[12.5px] text-ink-mute leading-relaxed">
              Move it on now while you still have the detail. An opportunity or a
              quotation is also where you record which flowers were asked for —
              that is what the demand card reads.
            </div>
            <div className="flex flex-wrap gap-2.5">
              <Button size="sm"
                className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5"
                onClick={() => { close(); advance('Opportunity'); }}>
                <Icon name="trending_up" className="text-[16px]" />Convert to opportunity
              </Button>
              <Button size="sm" variant="outline" className="rounded-full"
                onClick={() => { close(); advance('Quotation'); }}>
                <Icon name="request_quote" className="text-[16px]" />Quote it
              </Button>
              <Button size="sm" variant="outline" className="rounded-full"
                onClick={() => { close(); advance('Prospect'); }}>
                <Icon name="travel_explore" className="text-[16px]" />Make it a prospect
              </Button>
              <button onClick={close} className="text-[13px] text-ink-3 hover:text-ink px-2">
                Later
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto crm-scroll p-5 grid gap-4">
              {required.length > 0 && (
                <div>
                  <div className="text-[11px] text-ink-mute mb-2.5">
                    Required on this site
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {required.map((f) => (
                      <Field key={f.fieldname} field={f} value={form[f.fieldname]}
                        onChange={set} />
                    ))}
                  </div>
                </div>
              )}

              <div className="border-t border-hairline pt-4">
                <div className="text-[11px] text-ink-mute mb-2.5">Optional</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {!requiredNames.has('lead_name') && (
                    <Field field={{ fieldname: 'lead_name', label: 'Contact name', fieldtype: 'Data' }}
                      value={form.lead_name} onChange={set} />
                  )}
                  {!requiredNames.has('source') && (
                    <NameSelect label="Source" value={form.source}
                      onChange={(v) => set('source', v)} options={options?.sources || []} />
                  )}
                  {!requiredNames.has('industry') && (
                    <NameSelect label="Industry" value={form.industry}
                      onChange={(v) => set('industry', v)} options={options?.industries || []} />
                  )}
                  <NameSelect label="Lead owner" value={form.lead_owner}
                    onChange={(v) => set('lead_owner', v)}
                    options={(options?.users || []).map((u) => ({ value: u.name, label: u.full_name }))}
                    placeholder="— unassigned —" />
                  {OPTIONAL_FIELDS.filter((n) => !requiredNames.has(n) && n !== 'source' && n !== 'industry')
                    .map((n) => (
                      <Field key={n}
                        field={{ fieldname: n, label: n === 'no_of_employees' ? 'Employees' : 'Website',
                          fieldtype: n === 'no_of_employees' ? 'Int' : 'Data' }}
                        value={form[n]} onChange={set} />
                    ))}
                </div>
              </div>
            </div>

            <div className="shrink-0 flex items-center gap-3 px-5 py-3 border-t border-line">
              <Button size="sm" onClick={submit} disabled={saving}
                className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5">
                <Icon name="check" className="text-[16px]" />
                {saving ? 'Saving…' : 'Create lead'}
              </Button>
              <button onClick={close} className="text-[13px] text-ink-3 hover:text-ink">Cancel</button>
              {err && <span className="ml-auto text-[12px] text-bad text-right max-w-[60%]">{err}</span>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
