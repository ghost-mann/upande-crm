import { useEffect, useState } from 'react';
import { useStore } from '../../store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import Icon from '../../components/Icon';
import { cn } from '@/lib/utils';
import { Panel, SaveBar } from './parts';

// The eight seeds, in the order they appear on screen. Everything else in the
// palette is derived server-side, so this is the whole surface.
const SEEDS = [
  ['theme_accent', 'Accent', 'Buttons, active states, the primary chart series.'],
  ['theme_ink', 'Ink', 'Darkest structural colour — drives text, hairlines and shadows.'],
  ['theme_ink_muted', 'Ink muted', 'The most-visible grey. Seeded directly so its warmth is chosen.'],
  ['theme_canvas', 'Canvas', 'Page background. Card surfaces and lines derive from it.'],
  ['theme_success', 'Success', ''],
  ['theme_warning', 'Warning', ''],
  ['theme_danger', 'Danger', ''],
  ['theme_info', 'Info', ''],
];

const HEX = /^#[0-9a-fA-F]{6}$/;

function ColorRow({ label, help, value, onChange, disabled }) {
  const valid = !value || HEX.test(value);
  return (
    <div className="py-3 border-b border-hairline last:border-b-0 flex items-start justify-between gap-6">
      <div className="min-w-0">
        <div className="text-[13px] text-ink font-medium">{label}</div>
        {help && <div className="text-[11.5px] text-ink-mute mt-0.5 max-w-[46ch]">{help}</div>}
        {!valid && <div className="text-[11.5px] text-bad mt-1">Needs a full six-digit hex, e.g. #d9a514</div>}
      </div>
      <div className="shrink-0 flex items-center gap-2">
        <input
          type="color"
          value={HEX.test(value) ? value : '#000000'}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          aria-label={`${label} colour picker`}
          className="h-9 w-9 rounded-md border border-input bg-transparent p-0.5 cursor-pointer disabled:opacity-40"
        />
        <Input
          value={value || ''}
          disabled={disabled}
          placeholder="not set"
          onChange={(e) => onChange(e.target.value)}
          className={cn('w-[122px] h-9 font-mono text-[12.5px]', !valid && 'border-bad')}
        />
      </div>
    </div>
  );
}

function PresetCard({ preset, applied, disabled, onApply }) {
  const s = preset.seeds || {};
  const swatches = [s.theme_accent, s.theme_ink, s.theme_canvas].filter(Boolean);
  const on = applied === preset.name;
  return (
    <button
      onClick={() => onApply(preset.name)}
      disabled={disabled}
      className={cn(
        'text-left rounded-2xl border p-3.5 transition-all min-w-[170px]',
        on ? 'border-gold bg-gold-soft' : 'border-hairline hover:border-line-2 hover:bg-hover',
        disabled && 'opacity-50 cursor-not-allowed',
      )}
    >
      <div className="flex items-center gap-1.5 mb-2.5">
        {swatches.map((c, i) => (
          <span key={i} className="w-6 h-6 rounded-full border border-hairline" style={{ background: c }} />
        ))}
      </div>
      <div className="text-[12.5px] font-medium text-ink flex items-center gap-1.5">
        {preset.label}
        {on && <Icon name="check_circle" className="text-[14px] text-gold-text" />}
      </div>
      <div className="text-[10.5px] text-ink-mute mt-0.5">{on ? 'applied' : 'apply'}</div>
    </button>
  );
}

// A miniature of the shell, so the effect of a change is visible without hunting
// through the app. Uses the live CSS variables, which the store has already
// written onto :root after a save.
function Preview() {
  return (
    <div className="rounded-2xl border border-hairline overflow-hidden">
      <div className="bg-grad-ink px-4 py-3 flex items-center gap-2">
        <span className="text-white text-[12.5px] font-semibold">CRM</span>
        <span className="text-white/60 text-[10px] uppercase tracking-[0.16em]">preview</span>
      </div>
      <div className="bg-canvas p-4 grid gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <button className="bg-gold text-[var(--on-accent)] rounded-2xl h-9 px-4 text-[12.5px] font-semibold shadow-none">
            Compose
          </button>
          <span className="bdg bdg-good">Converted</span>
          <span className="bdg bdg-warn">Quotation</span>
          <span className="bdg bdg-bad">Lost</span>
        </div>
        <div className="rounded-[20px] bg-surface-2 border border-hairline px-5 py-4 shadow-card">
          <div className="text-[10px] text-ink-mute uppercase tracking-[0.16em] font-medium mb-2">Revenue</div>
          <div className="text-[26px] leading-none font-semibold text-ink tabular-nums">KES 83.3M</div>
          <div className="k-trend gold mt-2">1,429 orders</div>
        </div>
        <div className="flex items-center gap-2">
          <span className="bg-grad-ink text-white text-[11.5px] font-medium rounded-full px-3.5 py-1.5">Overview</span>
          <span className="text-ink-4 text-[11.5px] px-3.5 py-1.5">Leads</span>
          <span className="bg-gold-soft text-gold-text text-[11.5px] font-medium rounded-full px-3.5 py-1.5">Selected</span>
        </div>
      </div>
    </div>
  );
}

export default function Theme() {
  const theme = useStore((s) => s.theme);
  const loadTheme = useStore((s) => s.loadTheme);
  const saveTheme = useStore((s) => s.saveTheme);
  const applyPreset = useStore((s) => s.applyThemePreset);
  const resetTheme = useStore((s) => s.resetTheme);

  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState('');
  const [err, setErr] = useState('');
  const [ok, setOk] = useState('');

  useEffect(() => { if (!theme) loadTheme(); }, [theme, loadTheme]);
  // Re-seed the draft whenever the server's copy changes (save, preset, reset).
  useEffect(() => { if (theme?.seeds) setDraft({ ...theme.seeds }); }, [theme]);

  if (!theme || !draft) {
    return <Panel title="Theme" sub="Loading…"><div className="crm-empty">Loading theme…</div></Panel>;
  }

  const canEdit = !!theme.can_edit;
  const disabled = !canEdit || !theme.installed;
  const dirty = SEEDS.some(([k]) => (draft[k] || '') !== (theme.seeds?.[k] || ''));
  const anyInvalid = SEEDS.some(([k]) => draft[k] && !HEX.test(draft[k]));

  const form = {
    dirty, saving, err, ok, canEdit, installed: theme.installed,
    reset: () => { setDraft({ ...theme.seeds }); setErr(''); setOk(''); },
    save: async () => {
      if (anyInvalid) { setErr('Fix the highlighted colour first.'); return; }
      setSaving(true); setErr(''); setOk('');
      try {
        await saveTheme(draft);
        setOk('Applied');
      } catch (e) {
        setErr(e.message || 'Could not save the theme.');
      } finally {
        setSaving(false);
      }
    },
  };

  async function run(label, fn) {
    setBusy(label); setErr(''); setOk('');
    try {
      await fn();
      setOk(label === 'reset' ? 'Reset to Upande gold' : 'Preset applied');
    } catch (e) {
      setErr(e.message || 'Could not apply that theme.');
    } finally {
      setBusy('');
    }
  }

  return (
    <div>
      <Panel
        title="Presets"
        sub="A whole palette in one click · applied immediately, no reload"
        aside={
          <Button
            size="sm" variant="outline" disabled={disabled || !!busy}
            onClick={() => run('reset', resetTheme)}
            className="rounded-full h-9"
          >
            <Icon name="restart_alt" className="text-[16px]" />
            {busy === 'reset' ? 'Resetting…' : 'Reset to Upande gold'}
          </Button>
        }
      >
        <div className="flex flex-wrap gap-2.5 pt-1">
          {(theme.presets || []).map((p) => (
            <PresetCard
              key={p.name} preset={p} applied={theme.applied}
              disabled={disabled || !!busy}
              onApply={(name) => run(name, () => applyPreset(name))}
            />
          ))}
          {!theme.presets?.length && <div className="crm-empty">No shipped presets found</div>}
        </div>
      </Panel>

      <Panel
        title="Colours"
        sub="Eight seeds. The ink scale, surfaces, hairlines, shadows, gradients, button and input colours are all derived from them."
      >
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-7">
          <div>
            {SEEDS.map(([key, label, help]) => (
              <ColorRow
                key={key} label={label} help={help} value={draft[key]} disabled={disabled}
                onChange={(v) => { setDraft((d) => ({ ...d, [key]: v })); setOk(''); setErr(''); }}
              />
            ))}
            <SaveBar form={form} />
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.14em] text-ink-mute font-medium mb-2">
              Live preview
            </div>
            <Preview />
            <div className="text-[11px] text-ink-mute mt-2.5">
              Reflects what is saved. Text on the accent fill is chosen automatically for
              contrast, so a dark accent gets white text and a bright one gets ink.
            </div>
          </div>
        </div>
      </Panel>
    </div>
  );
}
