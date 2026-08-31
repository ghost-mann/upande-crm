import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import Icon from './Icon';
import LinkSearch from './LinkSearch';
import { useStore } from '../store';
import { flowerSearchApi } from '../api';
import { NameSelect, L } from './LeadFields';
import { fmt, fmtMoneyCompact } from '@shared/utils';
import { cn } from '@/lib/utils';

// Move a record to the next document in the pipeline, and record what was asked
// for on the way.
//
// The item lines are the reason this dialog earns its keep. `api/demand.py` reads
// what clients want from Opportunity Item and Quotation Item rows, and there were
// six such rows on the entire site because entering one meant opening the desk.
// The moment of advancing is when the salesperson knows the answer, so it is
// asked for here.
//
// Every hop itself is ERPNext's: the backend calls its own mappers, so the field
// mapping between doctypes stays whatever ERPNext says it is. See api/advance.py.

// Which target each source may reach, and what the button says. The backend's
// `crm_advance_routes` filters this by permission; this table is the order and
// the wording.
const MODES = {
  Opportunity: { icon: 'trending_up', label: 'To opportunity', verb: 'Create opportunity' },
  Quotation: { icon: 'request_quote', label: 'To quotation', verb: 'Create quotation' },
  Prospect: { icon: 'travel_explore', label: 'To prospect', verb: 'Create prospect' },
  Customer: { icon: 'storefront', label: 'To customer', verb: 'Create customer' },
};

const ORDER = ['Opportunity', 'Quotation', 'Prospect', 'Customer'];

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

// What the customer hop will carry across, shown before it is pressed.
//
// Without this the mapping is invisible: `Customer.email_id` is fetched from the
// primary contact, so a salesperson has no way to tell whether the address they
// collected is coming with them until after the record exists. Measured on this
// site, 9 of 10 lead-derived customers had lost theirs.
function CarryPreview({ doctype, name }) {
  const preview = useStore((s) => s.advancePreview);
  const [p, setP] = useState(null);

  useEffect(() => {
    let dead = false;
    if (!name) { setP(null); return undefined; }
    (async () => {
      const r = await preview(doctype, name);
      if (!dead) setP(r || {});
    })();
    return () => { dead = true; };
  }, [doctype, name, preview]);

  if (!p) return <div className="text-[12px] text-ink-mute">Reading what will carry across…</div>;
  if (p.already_customer) {
    return (
      <div className="text-[12.5px] text-bad">
        Already customer <b>{p.already_customer}</b>. Open that record instead of making a second one.
      </div>
    );
  }

  const contact = p.contact || {};
  const address = p.address || {};
  const fields = p.fields || {};
  const person = [contact.first_name, contact.last_name].filter(Boolean).join(' ');
  const contactLine = [person, contact.email_id, contact.mobile_no, contact.phone,
    contact.whatsapp && `WhatsApp ${contact.whatsapp}`].filter(Boolean).join(' · ');
  const addressLine = [address.address_line1, address.city, address.state, address.country]
    .filter(Boolean).join(', ');
  const fieldKeys = Object.keys(fields);
  const shown = fieldKeys.slice(0, 3).map((k) => `${k.replace(/_/g, ' ')} ${fields[k]}`).join(' · ');

  const Row = ({ head, children }) => (
    <div className="grid grid-cols-[68px_minmax(0,1fr)] gap-2 items-baseline">
      <span className="text-[10px] uppercase tracking-[0.14em] text-ink-mute">{head}</span>
      <span className="text-[12px] text-ink-4 break-words">{children}</span>
    </div>
  );

  return (
    <div className="rounded-xl border border-hairline p-3.5 grid gap-1.5">
      <div className={`${L} !mb-1`}>Will carry across</div>
      <Row head="Contact">
        {contactLine || <span className="text-ink-mute">nothing — this record holds no contact details</span>}
      </Row>
      <Row head="Address">
        {addressLine || (
          <span className="text-ink-mute">
            {p.address_skipped
              ? 'no street line recorded, so no address is created'
              : 'none recorded'}
          </span>
        )}
      </Row>
      <Row head="Customer">
        {shown || <span className="text-ink-mute">defaults only</span>}
        {fieldKeys.length > 3 ? ` · ${fieldKeys.length - 3} more` : ''}
      </Row>
      {p.notes_count > 0 && (
        <Row head="Notes">
          {fmt(p.notes_count)} {p.notes_count === 1 ? 'field' : 'fields'} with no home on
          Customer, kept in its details
        </Row>
      )}
    </div>
  );
}

export default function AdvanceDialog() {
  const ctx = useStore((s) => s.advanceDialog);
  const close = useStore((s) => s.closeAdvanceDialog);
  const options = useStore((s) => s.leadOptions);
  const routes = useStore((s) => s.advanceRoutes);
  const leadToProspect = useStore((s) => s.leadToProspect);
  const leadToOpportunity = useStore((s) => s.leadToOpportunity);
  const prospectToOpportunity = useStore((s) => s.prospectToOpportunity);
  const leadToQuotation = useStore((s) => s.leadToQuotation);
  const opportunityToQuotation = useStore((s) => s.opportunityToQuotation);
  const leadToCustomer = useStore((s) => s.leadToCustomer);
  const prospectToCustomer = useStore((s) => s.prospectToCustomer);
  const opportunityToCustomer = useStore((s) => s.opportunityToCustomer);
  const quotationToCustomer = useStore((s) => s.quotationToCustomer);
  const ccy = useStore((s) => s.data.command?.currency) || 'KES';

  const [doctype, setDoctype] = useState('Lead');
  const [name, setName] = useState('');
  const [mode, setMode] = useState('Opportunity');
  const [existingProspect, setExistingProspect] = useState('');
  const [form, setForm] = useState({});
  const [items, setItems] = useState([]);
  const [alsoOpp, setAlsoOpp] = useState(false);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);

  useEffect(() => {
    if (!ctx) return;
    setDoctype(ctx.doctype || 'Lead');
    setName(ctx.name || '');
    setMode(ctx.mode || (ctx.doctype === 'Quotation' ? 'Customer' : 'Opportunity'));
    setExistingProspect('');
    setForm({
      expected_closing: todayPlus(30), valid_till: todayPlus(30),
      sales_stage: '', opportunity_type: '', order_type: 'Sales',
      customer_group: '', territory: '',
    });
    setItems([]);
    setAlsoOpp(false);
    setErr(''); setBusy(false); setDone(null);
  }, [ctx]);

  const available = useMemo(() => {
    const allowed = (routes || {})[doctype] || [];
    return ORDER.filter((t) => allowed.includes(t));
  }, [routes, doctype]);

  // A mode the source cannot reach must not stay selected — the button would
  // call an endpoint that refuses.
  useEffect(() => {
    if (available.length && !available.includes(mode)) setMode(available[0]);
  }, [available, mode]);

  const total = useMemo(
    () => items.reduce((sum, r) => sum + (Number(r.qty) || 0) * (Number(r.rate) || 0), 0),
    [items],
  );

  if (!ctx) return null;

  const subject = ctx.label || name || '—';
  const wantsItems = mode === 'Opportunity' || mode === 'Quotation';
  const verb = MODES[mode]?.verb || 'Create';

  const addItem = (r) => setItems((xs) => (
    xs.some((x) => x.item_code === r.value)
      ? xs
      : [...xs, { item_code: r.value, label: r.label, uom: r.uom, qty: '', rate: '' }]
  ));
  const setItem = (i, patch) => setItems((xs) => xs.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const dropItem = (i) => setItems((xs) => xs.filter((_, j) => j !== i));

  function itemPayload() {
    return items.map((r) => ({
      item_code: r.item_code,
      qty: Number(r.qty),
      ...(r.rate === '' ? {} : { rate: Number(r.rate) }),
    }));
  }

  async function submit() {
    setErr('');
    if (!name) { setErr(`Pick the ${doctype.toLowerCase()} to advance.`); return; }

    if (wantsItems) {
      const bad = items.findIndex((r) => !(Number(r.qty) > 0));
      if (bad >= 0) { setErr(`${items[bad].label}: enter how many stems were asked for.`); return; }
    }
    // Quotation.items is mandatory in ERPNext; say so before the round trip.
    if (mode === 'Quotation' && !items.length && doctype !== 'Opportunity') {
      setErr('A quotation needs at least one variety.');
      return;
    }

    setBusy(true);
    try {
      let r;
      if (mode === 'Prospect') {
        r = await leadToProspect(name, { prospect: existingProspect });
        setDone({ kind: 'Prospect', name: r.prospect, created: r.created });
      } else if (mode === 'Opportunity') {
        const payload = {
          sales_stage: form.sales_stage || undefined,
          opportunity_type: form.opportunity_type || undefined,
          expected_closing: form.expected_closing || undefined,
          items: itemPayload(),
        };
        r = doctype === 'Lead'
          ? await leadToOpportunity(name, payload)
          : await prospectToOpportunity(name, payload);
        setDone({ kind: 'Opportunity', ...r });
      } else if (mode === 'Quotation') {
        const payload = {
          valid_till: form.valid_till || undefined,
          order_type: form.order_type || undefined,
          items: itemPayload(),
        };
        r = doctype === 'Lead'
          ? await leadToQuotation(name, payload, alsoOpp)
          : await opportunityToQuotation(name, payload);
        setDone({ kind: 'Quotation', ...r });
      } else {
        const payload = {
          customer_group: form.customer_group || undefined,
          territory: form.territory || undefined,
        };
        if (doctype === 'Lead') r = await leadToCustomer(name, payload);
        else if (doctype === 'Prospect') r = await prospectToCustomer(name, payload);
        else if (doctype === 'Opportunity') r = await opportunityToCustomer(name, payload);
        else r = await quotationToCustomer(name);
        setDone({ kind: 'Customer', ...r });
      }
    } catch (e) {
      setErr(e.message || `Could not create the ${mode.toLowerCase()}.`);
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4">
      <div className="flex flex-col w-[700px] max-w-[96vw] max-h-[92vh] rounded-2xl shadow-2xl border border-hairline bg-surface overflow-hidden">
        <div className="h-11 shrink-0 bg-grad-ink text-white flex items-center gap-1 pl-4 pr-1.5">
          <span className="text-[14px] font-semibold truncate flex-1">Advance · {subject}</span>
          <button className="w-7 h-7 rounded flex items-center justify-center hover:bg-white/15"
            onClick={close} title="Close">
            <Icon name="close" className="text-[18px]" />
          </button>
        </div>

        {done ? (
          <div className="p-6 grid gap-4">
            <div className="text-[14px] text-ink">
              {done.kind === 'Prospect' ? (
                <>Prospect <b>{done.name}</b> {done.created ? 'created' : 'updated'}.</>
              ) : done.kind === 'Customer' ? (
                <>Customer <b>{done.title || done.name}</b> {done.existing ? 'already existed' : 'created'}.</>
              ) : (
                <>
                  {done.kind} <b>{done.name}</b> created
                  {done.items ? ` with ${fmt(done.items)} ${done.items === 1 ? 'variety' : 'varieties'}` : ''}
                  {done.kind === 'Quotation' ? ' as a draft' : ''}.
                </>
              )}
            </div>

            {done.kind === 'Quotation' && (
              <div className="text-[12.5px] text-ink-mute leading-relaxed">
                Drafts stay drafts here — submit, print and send it from the desk. Until it
                is submitted the lead’s status does not move to Quotation, because that
                count only follows submitted quotes.
                {done.opportunity ? <> Raised alongside opportunity <b>{done.opportunity}</b>.</> : null}
              </div>
            )}
            {done.kind === 'Customer' && (done.contact || done.address) && (
              <div className="text-[12.5px] text-ink-mute leading-relaxed">
                Contact {done.contact ? <b>{done.contact}</b> : '—'} and address{' '}
                {done.address ? <b>{done.address}</b> : '—'} are linked to it, so the
                email and phone numbers came across.
              </div>
            )}
            {done.kind === 'Prospect' && (
              <div className="text-[12.5px] text-ink-mute leading-relaxed">
                A prospect on its own does not move the funnel — that stage counts
                opportunities. Raise one when there is something to quote.
              </div>
            )}

            <div className="flex gap-2.5 flex-wrap">
              {done.kind === 'Prospect' && (
                <Button size="sm"
                  className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5"
                  onClick={() => {
                    setDone(null); setMode('Opportunity');
                    setDoctype('Prospect'); setName(done.name);
                  }}>
                  <Icon name="trending_up" className="text-[16px]" />Now raise an opportunity
                </Button>
              )}
              {done.kind === 'Opportunity' && (
                <Button size="sm"
                  className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5"
                  onClick={() => {
                    setDone(null); setMode('Quotation');
                    setDoctype('Opportunity'); setName(done.name); setItems([]);
                  }}>
                  <Icon name="request_quote" className="text-[16px]" />Now quote it
                </Button>
              )}
              {done.kind === 'Quotation' && !done.existing && (
                <Button size="sm"
                  className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5"
                  onClick={() => {
                    setDone(null); setMode('Customer');
                    setDoctype('Quotation'); setName(done.name);
                  }}>
                  <Icon name="storefront" className="text-[16px]" />Now make them a customer
                </Button>
              )}
              <Button size="sm" variant="outline" className="rounded-full" onClick={close}>Done</Button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto crm-scroll p-5 grid gap-4">
              {available.length > 1 && (
                <div className="flex gap-2 flex-wrap">
                  {available.map((m) => (
                    <button key={m} onClick={() => setMode(m)}
                      className={cn(
                        'flex items-center gap-1.5 text-[12.5px] font-medium px-3.5 py-2 rounded-full transition-colors',
                        mode === m ? 'bg-grad-ink text-white' : 'text-ink-4 hover:text-ink hover:bg-hover',
                      )}>
                      <Icon name={MODES[m].icon} className="text-[15px]" />{MODES[m].label}
                    </button>
                  ))}
                </div>
              )}

              {!ctx.name && (
                <div>
                  <label className={L}>{doctype}</label>
                  <LinkSearch doctype={doctype} value={name} onChange={(v) => setName(v)}
                    placeholder={`Find the ${doctype.toLowerCase()}…`} />
                </div>
              )}

              {mode === 'Prospect' && (
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
              )}

              {mode === 'Opportunity' && (
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
              )}

              {mode === 'Quotation' && (
                <div className="grid gap-3">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className={L}>Valid till</label>
                      <Input type="date" value={form.valid_till || ''}
                        onChange={(e) => setForm((f) => ({ ...f, valid_till: e.target.value }))} />
                    </div>
                    <NameSelect label="Order type" value={form.order_type}
                      onChange={(v) => setForm((f) => ({ ...f, order_type: v }))}
                      options={options?.order_types || []} />
                  </div>
                  {doctype === 'Lead' && (
                    <Checkbox checked={alsoOpp} onCheckedChange={(v) => setAlsoOpp(!!v)}
                      label="Also raise an opportunity, and link the quote to it" />
                  )}
                  <div className="text-[11.5px] text-ink-mute leading-relaxed">
                    A quotation can be addressed to a lead — they only become a customer
                    when it turns into an order. It is saved as a draft; submit and send it
                    from the desk.
                  </div>
                </div>
              )}

              {mode === 'Customer' && (
                <div className="grid gap-3">
                  {doctype !== 'Quotation' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <NameSelect label="Customer group" value={form.customer_group}
                        onChange={(v) => setForm((f) => ({ ...f, customer_group: v }))}
                        options={options?.customer_groups || []} />
                      <NameSelect label="Territory" value={form.territory}
                        onChange={(v) => setForm((f) => ({ ...f, territory: v }))}
                        options={options?.territories || []} />
                    </div>
                  )}
                  {doctype === 'Quotation' ? (
                    <div className="text-[11.5px] text-ink-mute leading-relaxed">
                      The customer behind this quotation is resolved from the party it is
                      addressed to, carrying that record’s contact and address across. If
                      one already exists, it is returned rather than duplicated.
                    </div>
                  ) : (
                    <CarryPreview doctype={doctype} name={name} />
                  )}
                  {doctype === 'Lead' && (
                    <div className="text-[11.5px] text-ink-mute leading-relaxed">
                      Straight to customer skips the quote. That is allowed — it is the
                      phone order — but the funnel counts opportunities, so nothing of this
                      lead’s journey is recorded unless one is raised too.
                    </div>
                  )}
                </div>
              )}

              {wantsItems && (
                <div className="rounded-xl border border-hairline p-3.5">
                  <div className="flex items-baseline justify-between gap-3 mb-2.5">
                    <span className={`${L} !mb-0`}>
                      {mode === 'Quotation' ? 'Flowers quoted' : 'Flowers requested'}
                    </span>
                    <span className="text-[11px] text-ink-mute">
                      {mode === 'Quotation' && doctype === 'Lead'
                        ? 'required — a quotation needs a line'
                        : 'optional — but this is what the demand card reads'}
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
              )}

              {!available.length && (
                <div className="text-[12.5px] text-ink-mute">
                  You do not have permission to create any of the documents a
                  {` ${doctype.toLowerCase()} `}can become.
                </div>
              )}
            </div>

            <div className="shrink-0 flex items-center gap-3 px-5 py-3 border-t border-line">
              <Button size="sm" onClick={submit} disabled={busy || !available.length}
                className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5">
                <Icon name="check" className="text-[16px]" />
                {busy ? 'Working…' : verb}
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
