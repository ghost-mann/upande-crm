import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import LinkSearch from './LinkSearch';

// One input per Lead field, chosen from the field's own type.
//
// Shared by the create and convert dialogs because neither can hardcode a form:
// the mandatory fields on Lead are a *site* decision, and this install has made
// eleven of them mandatory including two custom ones. `crm_lead_form_options`
// returns the meta and this renders whatever comes back, so a farm that adds a
// required field gets asked for it instead of getting a MandatoryError after
// pressing save.

export const L = 'text-[10px] uppercase tracking-[0.14em] text-ink-mute font-medium mb-1.5 block';
export const SEL = 'h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm outline-none focus:ring-1 focus:ring-ring';

const NUMERIC = new Set(['Int', 'Float', 'Currency', 'Percent']);

export function Field({ field, value, onChange }) {
  const { fieldname, label, fieldtype, options } = field;
  const set = (v) => onChange(fieldname, v);

  if (fieldtype === 'Check') {
    return (
      <div className="flex items-end h-full pb-2">
        <Checkbox checked={!!value} onCheckedChange={(v) => set(v ? 1 : 0)} label={label} />
      </div>
    );
  }

  return (
    <div>
      <label className={L}>{label}</label>
      {fieldtype === 'Link' ? (
        <LinkSearch doctype={options} value={value || ''} onChange={(v) => set(v)}
          placeholder={`Find a ${options || 'record'}…`} />
      ) : fieldtype === 'Select' ? (
        <select className={SEL} value={value || ''} onChange={(e) => set(e.target.value)}>
          <option value="">— none —</option>
          {String(options || '').split('\n').filter(Boolean).map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      ) : fieldtype === 'Small Text' || fieldtype === 'Text' || fieldtype === 'Long Text' ? (
        <Textarea value={value || ''} onChange={(e) => set(e.target.value)} className="min-h-[64px]" />
      ) : NUMERIC.has(fieldtype) ? (
        <Input type="number" value={value ?? ''}
          onChange={(e) => set(e.target.value === '' ? '' : Number(e.target.value))} />
      ) : fieldtype === 'Date' ? (
        <Input type="date" value={value || ''} onChange={(e) => set(e.target.value)} />
      ) : (
        <Input value={value || ''} onChange={(e) => set(e.target.value)} />
      )}
    </div>
  );
}

// A plain select over a list of names, for the optional link-ish fields the app
// offers by default (source, industry, owner). Kept separate from `Field` because
// these come from `crm_lead_form_options` as bare name lists, not as meta.
export function NameSelect({ label, value, onChange, options = [], placeholder = '— none —' }) {
  return (
    <div>
      <label className={L}>{label}</label>
      <select className={SEL} value={value || ''} onChange={(e) => onChange(e.target.value)}>
        <option value="">{placeholder}</option>
        {options.map((o) => {
          const val = typeof o === 'string' ? o : (o.value ?? o.name);
          const lbl = typeof o === 'string' ? o : (o.label ?? o.full_name ?? val);
          return <option key={val} value={val}>{lbl}</option>;
        })}
      </select>
    </div>
  );
}
