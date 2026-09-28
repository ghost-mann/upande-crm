import { useEffect, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import LinkSearch from './LinkSearch';
import DialogShell, { LABEL, SELECT } from './DialogShell';
import { claimSaveApi, claimReferencesApi, claimGetApi, CLAIM_STATUSES } from '@/lib/service';
import { fmtDate, fmtMoney } from '@shared/utils';

// Log or update a customer claim. The order picker only offers the customer's
// own invoices, deliveries and orders (the server refuses anything else), and a
// claim cannot be closed without saying how.
const KINDS = ['Sales Invoice', 'Delivery Note', 'Sales Order'];

function today() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const BLANK = {
  customer: '', status: 'Open', reference_name: '', item_code: '', qty_affected: '',
  amount_claimed: '', amount_credited: '', description: '', root_cause: '', resolution: '', assigned_to: '',
};

// A row from a list carries nulls; the form wants empty strings and defaults.
function fromClaim(claim, types) {
  const out = { ...BLANK, raised_on: today(), claim_type: types[0] || '' };
  Object.entries(claim || {}).forEach(([k, v]) => { if (v != null) out[k] = v; });
  out.reference_doctype = claim?.reference_doctype || 'Sales Invoice';
  return out;
}

export default function ClaimDialog({ claim, types = [], onClose, onSaved }) {
  const [form, setForm] = useState(() => fromClaim(claim, types));
  // Editing: load the whole claim first. List rows leave out the long text
  // fields, and saving a form built from a row would blank them.
  const [loading, setLoading] = useState(!!claim?.name);
  useEffect(() => {
    if (!claim?.name) return undefined;
    let dead = false;
    claimGetApi(claim.name)
      .then((r) => { if (!dead) { setForm(fromClaim({ ...r.claim, lockCustomer: claim.lockCustomer }, types)); setLoading(false); } })
      .catch((e) => { if (!dead) { setErr(e.message || 'Could not load the claim'); setLoading(false); } });
    return () => { dead = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [claim?.name]);
  // A type removed from Settings since this claim was logged stays selectable
  // as its current value, rather than the select silently showing another.
  const typeOptions = form.claim_type && !types.includes(form.claim_type) ? [form.claim_type, ...types] : types;
  const [refs, setRefs] = useState([]);
  const [err, setErr] = useState('');
  const [saving, setSaving] = useState(false);
  const set = (patch) => { setForm((f) => ({ ...f, ...patch })); setErr(''); };
  const closing = form.status === 'Resolved' || form.status === 'Rejected';

  useEffect(() => {
    if (!form.customer || !form.reference_doctype) { setRefs([]); return undefined; }
    let dead = false;
    claimReferencesApi(form.customer, form.reference_doctype)
      .then((r) => { if (!dead) setRefs(r.rows || []); })
      .catch(() => { if (!dead) setRefs([]); });
    return () => { dead = true; };
  }, [form.customer, form.reference_doctype]);

  const save = async () => {
    if (loading) return;
    if (!form.customer) { setErr('Pick the customer.'); return; }
    if (!form.description.trim()) { setErr('Say what happened.'); return; }
    if (closing && !String(form.resolution || '').trim()) { setErr(`Say how the claim was ${form.status.toLowerCase()}.`); return; }
    setSaving(true);
    try {
      const payload = { ...form };
      ['qty_affected', 'amount_claimed', 'amount_credited'].forEach((k) => { if (payload[k] === '') delete payload[k]; });
      if (!payload.reference_name) { payload.reference_doctype = ''; }
      delete payload.lockCustomer; delete payload.overdue; delete payload.age_days; delete payload.resolved_on;
      const r = await claimSaveApi(payload);
      onSaved?.(r.claim);
      onClose();
    } catch (e) {
      setErr(e.message || 'Could not save the claim.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <DialogShell title={form.name ? `Claim · ${form.name}` : 'Log a claim'} onClose={onClose} onSave={save}
      saving={saving} err={err} saveLabel={form.name ? 'Save claim' : 'Log claim'} width={680}>
      {loading && <div className="text-[12px] text-ink-mute">Loading the claim…</div>}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={LABEL}>Customer</label>
          <LinkSearch doctype="Customer" value={form.customer} disabled={!!claim?.customer && !!claim?.lockCustomer}
            onChange={(v) => set({ customer: v, reference_name: '' })} placeholder="Find a customer…" />
        </div>
        <div>
          <label className={LABEL}>Type of claim</label>
          <select className={SELECT} value={form.claim_type} onChange={(e) => set({ claim_type: e.target.value })}>
            {typeOptions.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>

      <div>
        <label className={LABEL}>What happened</label>
        <Textarea value={form.description} onChange={(e) => set({ description: e.target.value })}
          placeholder="e.g. 3 boxes of Madam Bombastic arrived with botrytis; photos from the buyer attached in mail."
          className="min-h-[80px]" />
      </div>

      <div className="grid grid-cols-[170px_1fr] gap-3">
        <div>
          <label className={LABEL}>Against</label>
          <select className={SELECT} value={form.reference_doctype} onChange={(e) => set({ reference_doctype: e.target.value, reference_name: '' })}>
            {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        </div>
        <div>
          <label className={LABEL}>{form.reference_doctype}</label>
          <select className={SELECT} value={form.reference_name} disabled={!form.customer}
            onChange={(e) => set({ reference_name: e.target.value })}>
            <option value="">{form.customer ? '— not linked —' : 'Pick the customer first'}</option>
            {form.reference_name && !refs.some((r) => r.name === form.reference_name) && (
              <option value={form.reference_name}>{form.reference_name}</option>
            )}
            {refs.map((r) => (
              <option key={r.name} value={r.name}>{r.name} · {fmtDate(r.date)} · {fmtMoney(r.base_grand_total)}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={LABEL}>Item (optional)</label>
          <LinkSearch doctype="Item" value={form.item_code} onChange={(v) => set({ item_code: v })} placeholder="Find a variety…" />
        </div>
        <div>
          <label className={LABEL}>Quantity affected</label>
          <Input type="number" min={0} value={form.qty_affected ?? ''} onChange={(e) => set({ qty_affected: e.target.value })} placeholder="stems / units" />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className={LABEL}>Amount claimed</label>
          <Input type="number" min={0} value={form.amount_claimed ?? ''} onChange={(e) => set({ amount_claimed: e.target.value })} />
        </div>
        <div>
          <label className={LABEL}>Amount credited</label>
          <Input type="number" min={0} value={form.amount_credited ?? ''} onChange={(e) => set({ amount_credited: e.target.value })} />
        </div>
        <div>
          <label className={LABEL}>Raised on</label>
          <Input type="date" value={form.raised_on || ''} onChange={(e) => set({ raised_on: e.target.value })} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={LABEL}>Status</label>
          <select className={SELECT} value={form.status} onChange={(e) => set({ status: e.target.value })}>
            {CLAIM_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className={LABEL}>Assigned to</label>
          <LinkSearch doctype="User" value={form.assigned_to} onChange={(v) => set({ assigned_to: v })} placeholder="Who is handling it…" />
        </div>
      </div>

      <div>
        <label className={LABEL}>Root cause</label>
        <Input value={form.root_cause || ''} onChange={(e) => set({ root_cause: e.target.value })} placeholder="e.g. cold-chain break at the hub" />
      </div>
      <div>
        <label className={LABEL}>Resolution {closing ? '(required)' : ''}</label>
        <Textarea value={form.resolution || ''} onChange={(e) => set({ resolution: e.target.value })}
          placeholder="Credit note, replacement shipment, rejected with reason…" className="min-h-[60px]" />
      </div>
    </DialogShell>
  );
}
