import { useState } from 'react';
import { Input } from '@/components/ui/input';
import Icon from '../../components/Icon';
import { Panel, Row, NumberBox, SaveBar, useOrgForm } from './parts';

// The organisation's own vocabulary: pipeline stages, lead channels, claim types
// and visit purposes, plus the two "chase it after N days" limits. Lists are
// stored one per line; the order here is the order everywhere (board columns,
// dropdowns). Saving creates any stage or channel that does not exist yet.
const KEYS = ['opportunity_stages', 'lead_channels', 'claim_types', 'visit_purposes', 'claim_sla_days', 'quote_followup_days'];

function lines(text) {
  return String(text || '').split(/\n|,/).map((s) => s.trim()).filter(Boolean);
}

function ListEditor({ value, onChange, disabled, placeholder }) {
  const items = lines(value);
  const [draft, setDraft] = useState('');
  const write = (next) => onChange(next.join('\n'));
  const add = () => {
    const v = draft.trim();
    if (!v || items.includes(v)) return;
    write([...items, v]);
    setDraft('');
  };
  const move = (i, d) => {
    const next = [...items];
    const j = i + d;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    write(next);
  };
  return (
    <div className="w-[340px] max-w-full">
      <div className="grid gap-1 mb-2">
        {items.map((it, i) => (
          <div key={it} className="flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-hairline bg-surface text-[12.5px]">
            <span className="text-ink-mute tabular-nums w-4">{i + 1}</span>
            <span className="flex-1 truncate text-ink-2">{it}</span>
            <button type="button" disabled={disabled || i === 0} onClick={() => move(i, -1)} title="Move up"
              className="text-ink-mute hover:text-ink disabled:opacity-30"><Icon name="arrow_upward" className="text-[15px]" /></button>
            <button type="button" disabled={disabled || i === items.length - 1} onClick={() => move(i, 1)} title="Move down"
              className="text-ink-mute hover:text-ink disabled:opacity-30"><Icon name="arrow_downward" className="text-[15px]" /></button>
            <button type="button" disabled={disabled || items.length === 1} onClick={() => write(items.filter((x) => x !== it))} title="Remove"
              className="text-ink-mute hover:text-bad disabled:opacity-30"><Icon name="close" className="text-[15px]" /></button>
          </div>
        ))}
      </div>
      <div className="flex gap-1.5">
        <Input value={draft} disabled={disabled} placeholder={placeholder} className="h-8 text-[12.5px]"
          onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } }} />
        <button type="button" onClick={add} disabled={disabled || !draft.trim()}
          className="h-8 px-3 rounded-md border border-hairline text-[12.5px] text-ink-2 hover:bg-hover disabled:opacity-40">Add</button>
      </div>
    </div>
  );
}

export default function Lists() {
  const form = useOrgForm(KEYS);
  const f = form.draft;
  const list = (key, placeholder) => (
    <ListEditor value={f[key]} disabled={form.disabled} placeholder={placeholder} onChange={(v) => form.set({ [key]: v })} />
  );
  return (
    <div>
      <Panel title="Pipeline" sub="How a prospect moves from first contact to confirmed customer">
        <Row label="Opportunity stages"
          help="The columns of the pipeline board, left to right — e.g. sample dispatch, quotation, negotiation. An opportunity in a stage you remove is not lost: the board shows it under “Other stages”.">
          {list('opportunity_stages', 'Add a stage…')}
        </Row>
        <Row label="Lead channels"
          help="How leads reach you — email, phone call, trade event, referral. Offered first when a lead is logged, and used by the lead-source reports.">
          {list('lead_channels', 'Add a channel…')}
        </Row>
        <Row label="Follow up quotations after"
          help="An open quotation older than this, with no order yet, is flagged “follow up”.">
          <NumberBox value={f.quote_followup_days} min={1} max={365} suffix="days" disabled={form.disabled}
            onChange={(v) => form.set({ quote_followup_days: v })} />
        </Row>
      </Panel>
      <Panel title="Claims" sub="Complaints and quality claims">
        <Row label="Claim types" help="What a claim can be logged as — quality rejection, short shipment, damaged goods…">
          {list('claim_types', 'Add a claim type…')}
        </Row>
        <Row label="Resolve claims within" help="An open claim older than this is flagged overdue on the Claims dashboard.">
          <NumberBox value={f.claim_sla_days} min={1} max={365} suffix="days" disabled={form.disabled}
            onChange={(v) => form.set({ claim_sla_days: v })} />
        </Row>
      </Panel>
      <Panel title="Visits" sub="Farm visits and sales visits">
        <Row label="Visit purposes" help="Why a visit happened — farm tour, variety showcase, relationship check-in…">
          {list('visit_purposes', 'Add a purpose…')}
        </Row>
        <SaveBar form={form} />
      </Panel>
    </div>
  );
}
