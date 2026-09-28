import { useMemo } from 'react';
import { useStore } from '../../store';
import { cn } from '@/lib/utils';
import { Panel, Row, Toggle, SaveBar, SelectBox, useOrgForm } from './parts';

// Organisation-wide module switches. The list, labels and help text all come
// from upande_crm/modules.py via crm_settings, so this tab never drifts from
// what the server enforces.
const GROUP_ORDER = ['Customers', 'Pipeline', 'Communication', 'Marketing', 'Insight', 'Coming soon'];
const GROUP_NOTE = {
  Customers: 'How a single customer is shown',
  Pipeline: 'Moving an enquiry towards a sale',
  Communication: 'Talking to customers, and keeping track of it',
  Marketing: 'Reaching many customers at once',
  Insight: 'Reports, maps and analysis',
  'Coming soon': 'Being built — these switch on once they exist',
};

const TAB_LABELS = {
  overview: 'Overview', timeline: 'Timeline', orders: 'Orders', pricing: 'Pricing', contracts: 'Contracts',
};
const TAB_KEYS = Object.keys(TAB_LABELS);
const CUSTPAGE_KEYS = ['custpage_tabs', 'custpage_default_tab'];

function parseTabs(text) {
  const tabs = String(text || '').split(/[\n,]/).map((t) => t.trim()).filter(Boolean);
  return tabs.length ? tabs : TAB_KEYS;
}

function CustomerPageOptions({ form }) {
  const tabs = parseTabs(form.draft.custpage_tabs);
  const toggle = (key) => {
    const next = tabs.includes(key) ? tabs.filter((t) => t !== key) : TAB_KEYS.filter((t) => t === key || tabs.includes(t));
    if (!next.length) return; // at least one tab must stay
    const patch = { custpage_tabs: next.join('\n') };
    if (!next.includes(form.draft.custpage_default_tab)) patch.custpage_default_tab = next[0];
    form.set(patch);
  };
  return (
    <div className="mt-3 ml-1 pl-4 border-l-2 border-hairline">
      <div className="text-[12px] text-ink-3 mb-2">Which tabs a customer's page shows:</div>
      <div className="flex flex-wrap gap-2 mb-3">
        {TAB_KEYS.map((k) => (
          <label key={k} className={cn('flex items-center gap-1.5 text-[12.5px] px-2.5 h-8 rounded-full border border-hairline cursor-pointer',
            tabs.includes(k) ? 'bg-gold-soft text-gold-text' : 'text-ink-3', form.disabled && 'opacity-50 cursor-not-allowed')}>
            <input type="checkbox" className="accent-[var(--gold)]" checked={tabs.includes(k)} disabled={form.disabled}
              onChange={() => toggle(k)} />
            {TAB_LABELS[k]}
          </label>
        ))}
      </div>
      <div className="flex items-center gap-3 text-[12px] text-ink-3">
        Opens on
        <SelectBox value={form.draft.custpage_default_tab || tabs[0]} options={tabs} labels={TAB_LABELS}
          disabled={form.disabled} onChange={(v) => form.set({ custpage_default_tab: v })} />
      </div>
    </div>
  );
}

export default function Modules() {
  const meta = useStore((s) => s.orgMeta.moduleMeta);
  // Stable across renders: useOrgForm re-syncs its draft whenever `keys` changes.
  const keys = useMemo(() => [...meta.map((m) => m.field), ...CUSTPAGE_KEYS], [meta]);
  const form = useOrgForm(keys);

  if (!meta.length) {
    return <Panel title="Modules"><div className="crm-empty">Module settings are not available on this site yet — run <code>bench migrate</code>.</div></Panel>;
  }

  const groups = GROUP_ORDER
    .map((g) => ({ g, items: meta.filter((m) => m.group === g) }))
    .filter((x) => x.items.length);

  return (
    <div>
      {groups.map(({ g, items }) => (
        <Panel key={g} title={g} sub={GROUP_NOTE[g]}>
          {items.map((m) => {
            const on = m.available && !!Number(form.draft[m.field]);
            return (
              <Row
                key={m.key}
                label={<span className="flex items-center gap-2">{m.label}{!m.available && <span className="bdg bdg-info">Coming soon</span>}</span>}
                help={m.help}
                footer={m.key === 'customer_page' && on ? <CustomerPageOptions form={form} /> : null}
              >
                <Toggle on={on} disabled={form.disabled || !m.available}
                  onClick={() => form.set({ [m.field]: on ? 0 : 1 })} />
              </Row>
            );
          })}
        </Panel>
      ))}
      <Panel title="Save" sub="Switching a module off hides it for everyone and stops its data being served">
        <SaveBar form={form} />
      </Panel>
    </div>
  );
}
