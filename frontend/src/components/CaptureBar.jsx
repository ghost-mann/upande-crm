import { Button } from '@/components/ui/button';
import Icon from './Icon';
import { useStore } from '../store';

// The row of "what you can add from here" buttons that sits above a section.
//
// It exists because every hop between pipeline documents used to mean opening the
// desk: the dashboard could capture a lead and convert it two ways, and quoting
// or making a customer had no route at all. One component rather than four, so a
// new hop appears everywhere it applies at once and the wording cannot drift
// between sections.
//
// `primary` is the capture action; `advance` entries open the Advance dialog on a
// given source doctype and mode.
export default function CaptureBar({ primary, advance = [], note }) {
  const openLead = useStore((s) => s.openLeadDialog);
  const openAdvance = useStore((s) => s.openAdvanceDialog);
  const routes = useStore((s) => s.advanceRoutes);

  // Hide a hop this user cannot take, rather than offering a button whose
  // endpoint would refuse. `routes` is null until loaded — show them then, since
  // the dialog itself re-checks.
  const allowed = (a) => !routes || ((routes[a.doctype] || []).includes(a.mode));
  const hops = advance.filter(allowed);

  if (!primary && !hops.length) return null;

  return (
    <div className="flex items-center gap-2.5 flex-wrap mb-[18px]">
      {primary && (
        <Button size="sm" onClick={() => openLead({})}
          className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-4">
          <Icon name="person_add" className="text-[16px]" />{primary}
        </Button>
      )}
      {hops.map((a) => (
        <Button key={`${a.doctype}-${a.mode}`} size="sm" variant="outline" className="rounded-full"
          onClick={() => openAdvance({ doctype: a.doctype, mode: a.mode })}>
          <Icon name={a.icon} className="text-[16px]" />{a.label}
        </Button>
      ))}
      {note && <span className="text-[11.5px] text-ink-mute">{note}</span>}
    </div>
  );
}

// The bars each section shows, kept together so the vocabulary stays consistent.
export const BARS = {
  leads: {
    primary: 'New lead',
    advance: [
      { doctype: 'Lead', mode: 'Opportunity', icon: 'trending_up', label: 'Convert a lead' },
      { doctype: 'Lead', mode: 'Quotation', icon: 'request_quote', label: 'Quote a lead' },
      { doctype: 'Lead', mode: 'Customer', icon: 'storefront', label: 'Make a customer' },
    ],
    note: 'a lead can be quoted before it is a customer',
  },
  opps: {
    advance: [
      { doctype: 'Lead', mode: 'Opportunity', icon: 'trending_up', label: 'New opportunity' },
      { doctype: 'Opportunity', mode: 'Quotation', icon: 'request_quote', label: 'Raise a quote' },
      { doctype: 'Opportunity', mode: 'Customer', icon: 'storefront', label: 'Make a customer' },
    ],
  },
  prosp: {
    advance: [
      { doctype: 'Prospect', mode: 'Opportunity', icon: 'trending_up', label: 'Raise an opportunity' },
      { doctype: 'Prospect', mode: 'Customer', icon: 'storefront', label: 'Make a customer' },
    ],
  },
  cust: {
    advance: [
      { doctype: 'Lead', mode: 'Customer', icon: 'storefront', label: 'Customer from a lead' },
      { doctype: 'Quotation', mode: 'Customer', icon: 'request_quote', label: 'Customer from a quote' },
    ],
    note: 'contact details and address come across with them',
  },
};
