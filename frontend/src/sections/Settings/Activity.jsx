import { useStore } from '../../store';
import { Panel, Row, NumberBox, SelectBox, SaveBar, useOrgForm } from './parts';

const KEYS = [
  'default_task_priority', 'default_task_due_days',
  'default_event_category', 'default_event_duration_mins',
];

function dueHint(days) {
  const n = Number(days);
  if (!Number.isFinite(n)) return '';
  if (n === 0) return 'due today';
  if (n === 1) return 'due tomorrow';
  const d = new Date();
  d.setDate(d.getDate() + n);
  return `a task created now would be due ${d.toISOString().slice(0, 10)}`;
}

export default function Activity() {
  const form = useOrgForm(KEYS);
  const options = useStore((s) => s.orgMeta.options) || {};
  const priorities = options.default_task_priority || ['High', 'Medium', 'Low'];
  const categories = options.default_event_category
    || ['Event', 'Meeting', 'Call', 'Sent/Received Email', 'Other'];

  return (
    <div>
      <Panel title="New task defaults" sub="What the New task dialog opens with">
        <Row label="Priority">
          <SelectBox
            value={form.draft.default_task_priority} options={priorities}
            disabled={form.disabled} onChange={(v) => form.set({ default_task_priority: v })}
          />
        </Row>
        <Row label="Due in" help={dueHint(form.draft.default_task_due_days)}>
          <NumberBox
            value={form.draft.default_task_due_days} min={0} max={365} suffix="days"
            disabled={form.disabled} onChange={(v) => form.set({ default_task_due_days: v })}
          />
        </Row>
      </Panel>

      <Panel title="New event defaults" sub="What the New event dialog opens with">
        <Row label="Category">
          <SelectBox
            value={form.draft.default_event_category} options={categories}
            disabled={form.disabled} onChange={(v) => form.set({ default_event_category: v })}
          />
        </Row>
        <Row
          label="Duration"
          help="Fills in the end time when a start is picked and the end is still blank."
        >
          <NumberBox
            value={form.draft.default_event_duration_mins} min={5} max={1440} step={5} suffix="minutes"
            disabled={form.disabled} onChange={(v) => form.set({ default_event_duration_mins: v })}
          />
        </Row>
        <SaveBar form={form} />
      </Panel>
    </div>
  );
}
