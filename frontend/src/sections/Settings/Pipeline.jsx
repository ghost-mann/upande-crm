import { fmt } from '@shared/utils';
import { useStore } from '../../store';
import { Textarea } from '@/components/ui/textarea';
import Icon from '../../components/Icon';
import { Panel, Row, NumberBox, SaveBar, useOrgForm, LABEL } from './parts';

const KEYS = ['lead_open_statuses', 'opportunity_open_statuses', 'top_n'];

function parse(text) {
  return String(text || '').split(',').map((s) => s.trim()).filter(Boolean);
}

// The statuses actually present on this site, so nobody has to guess the
// vocabulary. Clicking one adds it to the list.
function StatusPicker({ rows, selected, onToggle, disabled }) {
  if (!rows?.length) return <div className="text-[11.5px] text-ink-mute">No status data in the current range.</div>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {rows.map((r) => {
        const on = selected.includes(r.label);
        return (
          <button
            key={r.label}
            type="button"
            disabled={disabled}
            onClick={() => onToggle(r.label)}
            title={on ? 'Counted as open — click to remove' : 'Click to count as open'}
            className={`text-[11px] rounded-full px-2.5 py-1 border transition-colors ${
              on ? 'bg-gold-soft border-gold text-gold-text font-medium'
                : 'border-hairline text-ink-4 hover:text-ink hover:bg-hover'
            } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {r.label}<span className="text-ink-mute ml-1.5 tabular-nums">{fmt(r.count)}</span>
          </button>
        );
      })}
    </div>
  );
}

export default function Pipeline() {
  const form = useOrgForm(KEYS);
  const leadStatuses = useStore((s) => s.data.overview?.lead_status) || [];
  const oppStatuses = useStore((s) => s.data.opps?.status_mix) || [];

  const leadList = parse(form.draft.lead_open_statuses);
  const oppList = parse(form.draft.opportunity_open_statuses);

  const toggle = (key, list) => (label) => {
    const next = list.includes(label) ? list.filter((x) => x !== label) : [...list, label];
    form.set({ [key]: next.join(', ') });
  };

  return (
    <div>
      <Panel
        title="What counts as open"
        sub="Drives the “open leads” and “open opportunities” figures on every dashboard"
      >
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-1">
          <div>
            <label className={LABEL}>Open lead statuses</label>
            <Textarea
              value={form.draft.lead_open_statuses ?? ''} disabled={form.disabled}
              onChange={(e) => form.set({ lead_open_statuses: e.target.value })}
              placeholder="Lead, Open, Replied, Interested"
              className="min-h-[64px] font-mono text-[12.5px]"
            />
            <div className="text-[11px] text-ink-mute mt-1.5 mb-2.5">
              Comma-separated. Only commas separate, so multi-word statuses are fine.
            </div>
            <StatusPicker rows={leadStatuses} selected={leadList} disabled={form.disabled}
              onToggle={toggle('lead_open_statuses', leadList)} />
          </div>
          <div>
            <label className={LABEL}>Open opportunity statuses</label>
            <Textarea
              value={form.draft.opportunity_open_statuses ?? ''} disabled={form.disabled}
              onChange={(e) => form.set({ opportunity_open_statuses: e.target.value })}
              placeholder="Open, Quotation, Replied"
              className="min-h-[64px] font-mono text-[12.5px]"
            />
            <div className="text-[11px] text-ink-mute mt-1.5 mb-2.5">
              A status you remove stops being counted as open everywhere at once.
            </div>
            <StatusPicker rows={oppStatuses} selected={oppList} disabled={form.disabled}
              onToggle={toggle('opportunity_open_statuses', oppList)} />
          </div>
        </div>
        {(!leadList.length || !oppList.length) && (
          <div className="mt-4 flex items-center gap-2 text-[12px] text-warn">
            <Icon name="warning" className="text-[15px]" />
            Each list needs at least one status — an empty list would count zero.
          </div>
        )}
      </Panel>

      <Panel title="Chart depth" sub="How many rows every top-N chart shows">
        <Row
          label="Top-N rows"
          help="Applies to sales reps, top products, territories, sources and status mixes together."
        >
          <NumberBox
            value={form.draft.top_n} min={3} max={20} suffix="rows" disabled={form.disabled}
            onChange={(v) => form.set({ top_n: v })}
          />
        </Row>
        {/* One save affordance for the whole tab — both panels edit the same draft. */}
        <SaveBar form={form} />
      </Panel>
    </div>
  );
}
