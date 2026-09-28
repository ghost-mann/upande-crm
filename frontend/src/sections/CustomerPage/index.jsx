import { useEffect, useState } from 'react';
import { useStore } from '../../store';
import { cn } from '@/lib/utils';
import { customerHeaderApi } from '../../lib/customer';
import Header from './Header';
import Overview from './Overview';
import Timeline from './Timeline';
import Orders from './Orders';
import Pricing from './Pricing';
import Contracts from './Contracts';
import Quotations from './Quotations';
import Claims from './Claims';
import Visits from './Visits';

// One customer's page. The customer's name rides in the store's `table` slot
// (`#custpage/<name>`), so it is bookmarkable and Back returns to the list.
// The header loads with the page; each tab fetches its own data on first open,
// because a busy customer carries thousands of invoices.
const TABS = {
  overview: { label: 'Overview', Comp: Overview },
  timeline: { label: 'Timeline', Comp: Timeline },
  orders: { label: 'Orders', Comp: Orders },
  quotations: { label: 'Quotations', Comp: Quotations },
  pricing: { label: 'Pricing', Comp: Pricing },
  claims: { label: 'Claims', Comp: Claims },
  visits: { label: 'Visits', Comp: Visits },
  contracts: { label: 'Contracts', Comp: Contracts },
};

function explain(message) {
  const m = String(message || '');
  if (/switched off/i.test(m)) return 'The customer page is switched off in CRM Settings → Modules.';
  if (/not found/i.test(m)) return 'This customer does not exist — it may have been renamed or deleted.';
  if (/permi/i.test(m)) return "You don't have access to this customer.";
  return m || 'Could not load this customer.';
}

export default function CustomerPage() {
  const name = useStore((s) => s.table);
  const dateFrom = useStore((s) => s.dateFrom);
  const dateTo = useStore((s) => s.dateTo);
  const [header, setHeader] = useState(null);
  const [err, setErr] = useState('');
  const [tab, setTab] = useState(null);
  const [noteFocus, setNoteFocus] = useState(0);

  useEffect(() => { setTab(null); setHeader(null); }, [name]);

  useEffect(() => {
    if (!name) return undefined;
    let dead = false;
    setErr('');
    customerHeaderApi(name, dateFrom, dateTo)
      .then((h) => {
        if (dead) return;
        setHeader(h);
        setTab((t) => (t && h.tabs.includes(t) ? t : h.default_tab));
      })
      .catch((e) => { if (!dead) setErr(explain(e.message)); });
    return () => { dead = true; };
  }, [name, dateFrom, dateTo]);

  if (!name) return <div className="crm-empty">No customer selected.</div>;
  if (err) return <div className="crm-empty">{err}</div>;
  if (!header) return <div className="p-12 text-center text-ink-mute text-[13px]">Loading…</div>;

  const Comp = TABS[tab]?.Comp;
  const addNote = () => {
    if (header.tabs.includes('timeline')) { setTab('timeline'); setNoteFocus((n) => n + 1); }
  };

  return (
    <div>
      <Header header={header} onAddNote={header.tabs.includes('timeline') ? addNote : null} />
      <div className="inline-flex gap-1 p-[5px] rounded-full bg-[var(--hover)] max-w-full overflow-x-auto mb-6" role="tablist">
        {header.tabs.map((k) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={cn('px-4 h-9 rounded-full text-[13px] whitespace-nowrap transition-colors',
              tab === k ? 'bg-ink text-white font-medium' : 'text-ink-3 hover:text-ink')}>
            {TABS[k]?.label || k}
          </button>
        ))}
      </div>
      {Comp && <Comp name={name} currency={header.currency} noteFocus={noteFocus} />}
    </div>
  );
}
