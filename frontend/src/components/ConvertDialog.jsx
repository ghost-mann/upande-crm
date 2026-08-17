import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import Icon from './Icon';
import LinkSearch from './LinkSearch';
import { useStore } from '../store';
import { flowerSearchApi } from '../api';
import { NameSelect, L, SEL } from './LeadFields';
import { fmt, fmtMoneyCompact } from '@shared/utils';
import { cn } from '@/lib/utils';

// Move a lead — or a prospect — along, and record what was actually asked for.
//
// The item lines are the reason this dialog earns its keep. `api/demand.py` reads
// what clients want from Opportunity Item and Quotation Item rows, and there were
// six such rows on the entire site because entering one meant opening the desk.
// The moment of conversion is when the salesperson knows the answer, so it is
// asked for here.
//
// The conversion itself is ERPNext's: the backend calls its own mappers, so the
// field mapping between Lead and Opportunity stays whatever ERPNext says it is.

function todayPlus(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function FlowerPicker({ onPick }) {
  const [q, setQ] = useState('');
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    let dead = false;
    const t = setTimeout(async () => {
      try {
        const r = await flowerSearchApi(q, 12);
        if (!dead) setRows(r || []);
      } catch { if (!dead) setRows([]); }
    }, 250);
    return () => { dead = true; clearTimeout(t); };
  }, [q, open]);

  return (
    <div className="relative">
      <div className="flex items-center gap-1.5 rounded-md border border-input px-2.5 h-9">
        <Icon name="local_florist" className="text-[15px] text-ink-mute shrink-0" />
        <input value={q} onChange={(e) => { setQ(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder="Add a variety — Giselle, Fireworks…"
          className="flex-1 bg-transparent outline-none text-sm min-w-0" />
      </div>
      {open && rows.length > 0 && (
        <div className="absolute z-[70] mt-1 w-full max-h-56 overflow-y-auto rounded-md border border-line bg-surface shadow-lg">
          {rows.map((r) => (
            <button type="button" key={r.value}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => { onPick(r); setQ(''); setOpen(false); }}
              className="w-full text-left px-3 py-2 text-[13px] hover:bg-hover">
              <div className="text-ink truncate">{r.label}</div>
              <div className="text-[11px] text-ink-mute truncate">{r.value} · {r.group || '—'}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ConvertDialog() {
  const ctx = useStore((s) => s.convertDialog);
  const close = useStore((s) => s.closeConvertDialog);
  const options = useStore((s) => s.leadOptions);
  const leadToProspect = useStore((s) => s.leadToProspect);
  const leadToOpportunity = useStore((s) => s.leadToOpportunity);
  const prospectToOpportunity = useStore((s) => s.prospectToOpportunity);
  const ccy = useStore((s) => s.data.command?.currency) || 'KES';

  const [mode, setMode] = useState('opportunity');
  const [lead, setLead] = useState('');
  const [prospect, setProspect] = useState('');
  const [existingProspect, setExistingProspect] = useState('');
  const [form, setForm] = useState({});
  const [items, setItems] = useState([]);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);

  useEffect(() => {
    if (!ctx) return;
    setMode(ctx.mode || (ctx.prospect ? 'opportunity' : 'opportunity'));
    setLead(ctx.lead || '');
    setProspect(ctx.prospect || '');
    setExistingProspect('');
    setForm({ expected_closing: todayPlus(30), sales_stage: '', opportunity_type: '' });
    setItems([]);
    setErr(''); setBusy(false); setDone(null);
  }, [ctx]);

  const total = useMemo(
    () => items.reduce((sum, r) => sum + (Number(r.qty) || 0) * (Number(r.rate) || 0), 0),
    [items],
  );

  if (!ctx) return null;

  // A prospect source can only become an opportunity; the prospect step is a
  // lead-only move, so the toggle is hidden rather than shown-and-disabled.
  const fromProspect = !!prospect && !lead;
  const subject = ctx.label || lead || prospect || '—';

  const addItem = (r) => setItems((xs) => (
    xs.some((x) => x.item_code === r.value)
      ? xs
      : [...xs, { item_code: r.value, label: r.label, uom: r.uom, qty: '', rate: '' }]
  ));
  const setItem = (i, patch) => setItems((xs) => xs.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const dropItem = (i) => setItems((xs) => xs.filter((_, j) => j !== i));

  async function submit() {
    setErr('');
    if (mode === 'prospect') {
      if (!lead) { setErr('Pick the lead to convert.'); return; }
      setBusy(true);
      try {
        const r = await leadToProspect(lead, { prospect: existingProspect });
        setDone({ kind: 'prospect', ...r });
      } catch (e) {
        setErr(e.message || 'Could not create the prospect.');
      } finally { setBusy(false); }
      return;
    }

    if (!lead && !prospect) { setErr('Pick the lead or prospect to convert.'); return; }
    const bad = items.findIndex((r) => !(Number(r.qty) > 0));
    if (bad >= 0) { setErr(`${items[bad].label}: enter how many stems were asked for.`); return; }

    setBusy(true);
    try {
      const payload = {
        sales_stage: form.sales_stage || undefined,
        opportunity_type: form.opportunity_type || undefined,
        expected_closing: form.expected_closing || undefined,
        items: items.map((r) => ({
          item_code: r.item_code,
          qty: Number(r.qty),
          ...(r.rate === '' ? {} : { rate: Number(r.rate) }),
        })),
      };
      const r = lead
        ? await leadToOpportunity(lead, payload)
        : await prospectToOpportunity(prospect, payload);
      setDone({ kind: 'opportunity', ...r });
    } catch (e) {
      setErr(e.message || 'Could not create the opportunity.');
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4">
      <div className="flex flex-col w-[700px] max-w-[96vw] max-h-[92vh] rounded-2xl shadow-2xl border border-hairline bg-surface overflow-hidden">
        <div className="h-11 shrink-0 bg-grad-ink text-white flex items-center gap-1 pl-4 pr-1.5">
          <span className="text-[14px] font-semibold truncate flex-1">Convert · {subject}</span>
          <button className="w-7 h-7 rounded flex items-center justify-center hover:bg-white/15"
            onClick={close} title="Close">
            <Icon name="close" className="text-[18px]" />
          </button>
        </div>

        {done ? (
          <div className="p-6 grid gap-4">
            <div className="text-[14px] text-ink">
              {done.kind === 'prospect'
                ? <>Prospect <b>{done.prospect}</b> {done.created ? 'created' : 'updated'}.</>
                : <>Opportunity <b>{done.name}</b> created{done.items ? ` with ${fmt(done.items)} ${done.items === 1 ? 'variety' : 'varieties'}` : ''}.</>}
            </div>
            {done.kind === 'prospect' && (
              <div className="text-[12.5px] text-ink-mute leading-relaxed">
                A prospect on its own does not move the funnel — that stage counts
                opportunities. Raise one when there is something to quote.
              </div>
            )}
            <div className="flex gap-2.5">
              {done.kind === 'prospect' && (
                <Button size="sm"
                  className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5"
                  onClick={() => { setDone(null); setMode('opportunity'); setLead(''); setProspect(done.prospect); }}>
                  <Icon name="trending_up" className="text-[16px]" />Now raise an opportunity
                </Button>
              )}
              <Button size="sm" variant="outline" className="rounded-full" onClick={close}>Done</Button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto crm-scroll p-5 grid gap-4">
              {!fromProspect && (
                <div className="flex gap-2">
                  {[['opportunity', 'trending_up', 'To opportunity'],
                    ['prospect', 'travel_explore', 'To prospect']].map(([m, icon, label]) => (
                    <button key={m} onClick={() => setMode(m)}
                      className={cn(
                        'flex items-center gap-1.5 text-[12.5px] font-medium px-3.5 py-2 rounded-full transition-colors',
                        mode === m ? 'bg-grad-ink text-white' : 'text-ink-4 hover:text-ink hover:bg-hover',
                      )}>
                      <Icon name={icon} className="text-[15px]" />{label}
                    </button>
                  ))}
                </div>
              )}

              {!ctx.lead && !ctx.prospect && (
                <div>
                  <label className={L}>Lead</label>
                  <LinkSearch doctype="Lead" value={lead} onChange={(v) => setLead(v)}
                    placeholder="Find the lead…" />
                </div>
              )}

              {mode === 'prospect' ? (
                <div className="grid gap-3">
                  <div>
                    <label className={L}>Add to an existing prospect</label>
                    <LinkSearch doctype="Prospect" value={existingProspect}
                      onChange={(v) => setExistingProspect(v)}
                      placeholder="Leave empty to create a new one…" />
                  </div>
                  <div className="text-[11.5px] text-ink-mute leading-relaxed">
                    Left empty, a new prospect is created from the lead’s company, carrying
                    its territory, industry, size and owner across. A prospect is named by
                    its company, so a name already in use has to be picked above instead.
                  </div>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <NameSelect label="Sales stage" value={form.sales_stage}
                      onChange={(v) => setForm((f) => ({ ...f, sales_stage: v }))}
                      options={options?.sales_stages || []} />
                    <NameSelect label="Opportunity type" value={form.opportunity_type}
                      onChange={(v) => setForm((f) => ({ ...f, opportunity_type: v }))}
                      options={options?.opportunity_types || []} />
                    <div>
                      <label className={L}>Expected closing</label>
                      <Input type="date" value={form.expected_closing || ''}
                        onChange={(e) => setForm((f) => ({ ...f, expected_closing: e.target.value }))} />
                    </div>
                  </div>

                  <div className="rounded-xl border border-hairline p-3.5">
                    <div className="flex items-baseline justify-between gap-3 mb-2.5">
                      <span className={`${L} !mb-0`}>Flowers requested</span>
                      <span className="text-[11px] text-ink-mute">
                        optional — but this is what the demand card reads
                      </span>
                    </div>
                    <FlowerPicker onPick={addItem} />

                    {items.length > 0 && (
                      <div className="mt-3 grid gap-2">
                        {items.map((r, i) => (
                          <div key={r.item_code}
                            className="grid grid-cols-[minmax(0,1fr)_92px_92px_28px] gap-2 items-center">
                            <div className="min-w-0">
                              <div className="text-[12.5px] text-ink truncate" title={r.item_code}>
                                {r.label}
                              </div>
                              <div className="text-[10.5px] text-ink-mute truncate">
                                {r.item_code}{r.uom ? ` · ${r.uom}` : ''}
                              </div>
                            </div>
                            <Input type="number" min={0} placeholder="stems" value={r.qty}
                              onChange={(e) => setItem(i, { qty: e.target.value })} className="h-9" />
                            <Input type="number" min={0} step="0.01" placeholder="rate" value={r.rate}
                              onChange={(e) => setItem(i, { rate: e.target.value })} className="h-9" />
                            <button onClick={() => dropItem(i)} title="Remove"
                              className="text-ink-3 hover:text-bad flex items-center justify-center">
                              <Icon name="close" className="text-[16px]" />
                            </button>
                          </div>
                        ))}
                        <div className="flex justify-end text-[12px] text-ink-mute pt-1 border-t border-hairline">
                          Total&nbsp;
                          <span className="text-ink font-semibold tabular-nums">
                            {fmtMoneyCompact(total, ccy)}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>

            <div className="shrink-0 flex items-center gap-3 px-5 py-3 border-t border-line">
              <Button size="sm" onClick={submit} disabled={busy}
                className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5">
                <Icon name="check" className="text-[16px]" />
                {busy ? 'Working…' : mode === 'prospect' ? 'Create prospect' : 'Create opportunity'}
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
