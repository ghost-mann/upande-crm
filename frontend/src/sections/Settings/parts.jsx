import { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import Icon from '../../components/Icon';
import { useStore } from '../../store';
import { cn } from '@/lib/utils';

// Shared form primitives for the Settings tabs. Everything here follows the
// existing UFD-modern vocabulary (ink shell, gold as the single accent) rather
// than introducing a second style for settings.

export const LABEL = 'text-[10px] uppercase tracking-[0.14em] text-ink-mute font-medium mb-1.5 block';
export const SELECT =
  'h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm outline-none focus:ring-1 focus:ring-ring';

export function Toggle({ on, onClick, disabled }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={!!on}
      className={cn(
        'w-9 h-5 rounded-full relative transition-colors shrink-0',
        on ? 'bg-gold' : 'bg-line-2',
        disabled && 'opacity-40 cursor-not-allowed',
      )}
    >
      <span className={cn('absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all', on ? 'left-[18px]' : 'left-0.5')} />
    </button>
  );
}

// A labelled row: label + optional help text on the left, control on the right.
export function Row({ label, help, children, footer }) {
  return (
    <div className="py-3 border-b border-hairline last:border-b-0">
      <div className="flex items-start justify-between gap-6">
        <div className="min-w-0">
          <div className="text-[13px] text-ink font-medium">{label}</div>
          {help && <div className="text-[11.5px] text-ink-mute mt-0.5 max-w-[46ch]">{help}</div>}
        </div>
        <div className="shrink-0 flex items-center gap-2">{children}</div>
      </div>
      {footer}
    </div>
  );
}

export function NumberBox({ value, onChange, min, max, step = 1, suffix, disabled }) {
  return (
    <div className="flex items-center gap-1.5">
      <Input
        type="number" min={min} max={max} step={step} value={value} disabled={disabled}
        onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
        className="w-[104px] h-9 text-right tabular-nums"
      />
      {suffix && <span className="text-[11.5px] text-ink-mute w-16">{suffix}</span>}
    </div>
  );
}

export function SelectBox({ value, onChange, options, labels, disabled, className }) {
  return (
    <select
      className={cn(SELECT, 'w-[190px]', className)}
      value={value ?? ''}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map((o) => <option key={o} value={o}>{labels?.[o] || o}</option>)}
    </select>
  );
}

export function Panel({ title, sub, children, aside }) {
  return (
    <Card className="mb-[18px]">
      <CardHeader>
        <div><CardTitle>{title}</CardTitle>{sub && <CardSub>{sub}</CardSub>}</div>
        {aside}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

// Progress meter used by the target previews.
export function Meter({ pct, tone = 'gold', marker }) {
  const width = Math.max(0, Math.min(100, pct || 0));
  const fill = tone === 'good' ? 'var(--good)' : tone === 'bad' ? 'var(--bad)' : 'var(--gold)';
  return (
    <div className="h-[10px] rounded-full bg-[rgba(10,10,10,0.06)] relative overflow-hidden">
      <div className="h-full rounded-full transition-all" style={{ width: `${width}%`, background: fill }} />
      {marker != null && (
        <span
          title="Time elapsed"
          className="absolute top-0 bottom-0 w-px bg-ink-3"
          style={{ left: `${Math.max(0, Math.min(100, marker))}%` }}
        />
      )}
    </div>
  );
}

export function StatusDot({ status }) {
  const tone = {
    ok: 'bg-good', warn: 'bg-warn', off: 'bg-ink-3', missing: 'bg-bad',
  }[status] || 'bg-ink-3';
  return <span className={cn('w-2 h-2 rounded-full shrink-0', tone)} />;
}

// One save affordance per tab. Nothing is written until it is pressed, so a
// half-typed target never reaches the dashboards.
export function SaveBar({ form }) {
  const { dirty, saving, err, ok, save, reset, canEdit, installed } = form;
  if (!canEdit) {
    return (
      <div className="mt-4 flex items-center gap-2 text-[12px] text-ink-mute">
        <Icon name="lock" className="text-[15px]" />
        Only a Sales Manager or System Manager can change these.
      </div>
    );
  }
  if (!installed) {
    return (
      <div className="mt-4 flex items-center gap-2 text-[12px] text-warn">
        <Icon name="warning" className="text-[15px]" />
        Settings storage is not installed on this site — run <code className="mx-1">bench migrate</code> to save changes.
      </div>
    );
  }
  return (
    <div className="mt-4 flex items-center gap-3">
      <Button
        size="sm" onClick={save} disabled={saving || !dirty}
        className="rounded-full bg-gold text-ink hover:bg-gold-2 hover:text-white shadow-none px-5 disabled:opacity-40"
      >
        <Icon name="check" className="text-[16px]" />{saving ? 'Saving…' : 'Save changes'}
      </Button>
      {dirty && !saving && (
        <button onClick={reset} className="text-[13px] text-ink-3 hover:text-ink">Discard</button>
      )}
      {err && <span className="text-[12px] text-bad">{err}</span>}
      {!err && ok && <span className="text-[12px] text-good flex items-center gap-1"><Icon name="check_circle" className="text-[14px]" />{ok}</span>}
      {!err && !ok && !dirty && <span className="text-[12px] text-ink-mute">No unsaved changes</span>}
    </div>
  );
}

function pick(src, keys) {
  const out = {};
  keys.forEach((k) => { out[k] = src?.[k]; });
  return out;
}

// Draft state for a tab's slice of the organisation settings.
//
// `keys` must be a stable module-level array — it is the effect dependency that
// re-syncs the draft after someone else's save lands.
export function useOrgForm(keys) {
  const org = useStore((s) => s.org);
  const canEdit = useStore((s) => s.orgMeta.can_edit);
  const installed = useStore((s) => s.orgMeta.installed);
  const saveOrg = useStore((s) => s.saveOrg);

  const [draft, setDraft] = useState(() => pick(org, keys));
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [ok, setOk] = useState('');

  useEffect(() => { setDraft(pick(org, keys)); }, [org, keys]);

  const dirty = keys.some((k) => String(draft[k] ?? '') !== String(org[k] ?? ''));

  async function save() {
    setSaving(true); setErr(''); setOk('');
    try {
      await saveOrg(pick(draft, keys));
      setOk('Saved');
    } catch (e) {
      // Keep the draft: the server rejected a value and the user needs to see
      // which one, with what they typed still on screen.
      setErr(e.message || 'Could not save these settings.');
    } finally {
      setSaving(false);
    }
  }

  return {
    draft,
    set: (patch) => { setDraft((d) => ({ ...d, ...patch })); setOk(''); setErr(''); },
    reset: () => { setDraft(pick(org, keys)); setErr(''); setOk(''); },
    dirty, saving, err, ok, save, canEdit, installed,
    disabled: !canEdit || !installed,
  };
}
