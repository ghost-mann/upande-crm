import { useEffect, useMemo, useRef, useState } from 'react';
import { useStore } from '../../store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import Icon from '../../components/Icon';
import { cn } from '@/lib/utils';
import { Panel, Toggle, SELECT } from './parts';
import ThemePreview from './ThemePreview';

// The CRM's look, in plain words. Every field is optional: blank means the CRM
// works the value out from the others, and with nothing set at all the CRM looks
// exactly as shipped. Each row says what you will see change first, and what it
// drives technically second, so a non-designer and a developer both get a
// straight answer.
//
// The preview on the right is derived by the server (crm_theme_preview) from the
// unsaved draft — the same code that renders the saved theme — so it cannot
// promise something Save will not deliver.

const HEX = /^#[0-9a-fA-F]{6}$/;

const COLOURS = {
  brand: [
    ['theme_accent', 'Accent', 'Your brand colour. Used for highlights, badges, charts and the focus ring.', '--gold family, chart series, focus ring', 'gold'],
    ['theme_accent_dark', 'Accent dark', 'A deeper version of your brand colour, for brand-coloured text on white and the dark end of buttons.', '--gold-2, --gold-text, gradient deep stop', 'gold-2'],
    ['theme_accent_soft', 'Accent soft', 'A very pale version, used behind highlighted badges and selected rows.', '--gold-soft, --selected', 'gold-soft'],
  ],
  neutral: [
    ['theme_ink', 'Ink', 'The main text colour. It also tints every grey and every shadow, so this one choice changes the feel of the whole app.', 'text, 7-step grey scale, shadows', 'text'],
    ['theme_ink_muted', 'Muted text', 'Secondary text like dates, labels and hints. Pick a warm or cool grey to set the mood.', '--ink-mute, --text-3', 'text-3'],
    ['theme_canvas', 'Page canvas', 'The background behind all the cards.', '--bg; lighter surfaces derive from it', 'bg'],
    ['theme_wash', 'Muted fill', 'Slightly darker patches: row hover, quiet panels, the search box.', '--surface-3, secondary/muted fills', 'surface-3'],
    ['theme_border', 'Border', 'Thin lines around cards, inputs and between table rows.', '--line, --border, --input, hairlines', 'line'],
    ['theme_border_strong', 'Border strong', 'Heavier dividers and the edge of outlined buttons.', '--line-2', 'line-2'],
  ],
  status: [
    ['theme_success', 'Success', 'Good news: won deals, paid invoices, completed tasks.', '--good + its pale badge fill', 'good'],
    ['theme_warning', 'Warning', 'Needs attention: overdue tasks, pending quotations.', '--warn + its pale badge fill', 'warn'],
    ['theme_danger', 'Danger', 'Problems: lost deals, failed messages, errors.', '--bad, destructive buttons', 'bad'],
    ['theme_info', 'Info', 'Neutral notes and secondary chart lines.', '--info + its pale badge fill', 'info'],
  ],
};

const FONTS = [
  ['sans', 'theme_font_sans', 'theme_font_sans_name', 'Body font', 'The font for almost everything — text, buttons, tables.', '--f'],
  ['display', 'theme_font_display', 'theme_font_display_name', 'Headings font', 'Big page titles and panel headings.', '--display'],
  ['mono', 'theme_font_mono', 'theme_font_mono_name', 'Numbers font', 'Figures in KPI tiles and codes like invoice numbers.', '--mono'],
];

const SHAPES = [
  ['theme_radius', 'Small corners', 'How rounded buttons, inputs and badges are.', '--radius, --r-sm', 12],
  ['theme_radius_card', 'Card corners', 'How rounded cards, KPI tiles and tables are.', '--r-card', 24],
  ['theme_radius_panel', 'Panel corners', 'How rounded the sidebar, dialogs and large panels are.', '--r-panel', 24],
];

function Help({ plain, tech }) {
  return (
    <>
      <div className="text-[12.5px] text-ink-3 mt-0.5 max-w-[52ch]">{plain}</div>
      {tech && <div className="text-[11px] text-ink-mute mt-0.5">Technically: {tech}</div>}
    </>
  );
}

function FieldRow({ label, plain, tech, children }) {
  return (
    <div className="py-3.5 border-b border-hairline last:border-b-0 flex items-start justify-between gap-6 flex-wrap">
      <div className="min-w-0 flex-1">
        <div className="text-[13px] text-ink font-medium">{label}</div>
        <Help plain={plain} tech={tech} />
      </div>
      <div className="shrink-0 flex items-center gap-2">{children}</div>
    </div>
  );
}

function ColourRow({ spec, value, derived, onChange, disabled }) {
  const [field, label, plain, tech, token] = spec;
  const valid = !value || HEX.test(value);
  const fallback = derived?.[token];
  return (
    <FieldRow label={label} plain={plain} tech={tech}>
      {!value && fallback && HEX.test(fallback) && (
        <span className="text-[11px] text-ink-mute flex items-center gap-1.5">
          <span className="w-4 h-4 rounded-full border border-hairline opacity-60" style={{ background: fallback }} />
          worked out for you
        </span>
      )}
      <input
        type="color"
        value={HEX.test(value) ? value : (HEX.test(fallback || '') ? fallback : '#000000')}
        disabled={disabled}
        onChange={(e) => onChange(field, e.target.value)}
        aria-label={`${label} colour picker`}
        className="h-9 w-9 rounded-md border border-input bg-transparent p-0.5 cursor-pointer disabled:opacity-40"
      />
      <Input
        value={value || ''}
        disabled={disabled}
        placeholder="blank"
        onChange={(e) => onChange(field, e.target.value.trim())}
        className={cn('w-[112px] h-9 font-mono text-[12.5px]', !valid && 'border-bad')}
        aria-invalid={!valid}
      />
      {value && !disabled && (
        <button type="button" onClick={() => onChange(field, '')} className="text-[12px] text-ink-3 hover:text-ink">Clear</button>
      )}
      {!valid && <span className="basis-full text-right text-[11.5px] text-bad">Needs a six-digit colour code, e.g. #d9a514</span>}
    </FieldRow>
  );
}

function ShapeRow({ spec, value, onChange, disabled }) {
  const [field, label, plain, tech, shipped] = spec;
  const px = value === '0' ? 0 : /^\d+(\.\d+)?px$/.test(value || '') ? parseFloat(value) : null;
  const shown = px ?? shipped;
  return (
    <FieldRow label={label} plain={plain} tech={tech}>
      <input type="range" min={0} max={32} step={1} value={shown} disabled={disabled}
        onChange={(e) => onChange(field, e.target.value === '0' ? '0' : `${e.target.value}px`)}
        className="w-[130px] accent-[var(--gold)]" aria-label={`${label} size`} />
      <Input value={value || ''} disabled={disabled} placeholder={`${shipped}px`}
        onChange={(e) => onChange(field, e.target.value.trim())} className="w-[84px] h-9 font-mono text-[12.5px]" />
      <label className="text-[12px] text-ink-3 flex items-center gap-1.5">
        <input type="checkbox" className="accent-[var(--gold)]" checked={value === '0'} disabled={disabled}
          onChange={(e) => onChange(field, e.target.checked ? '0' : '')} />
        Square
      </label>
      {value && value !== '0' && px == null && (
        <span className="basis-full text-right text-[11.5px] text-ink-mute">Sizes like 8px, 0.5rem or 0 are accepted.</span>
      )}
    </FieldRow>
  );
}

const LEVEL = {
  ok: { icon: 'check_circle', cls: 'text-good', text: 'Readable' },
  warn: { icon: 'warning', cls: 'text-warn', text: 'Hard to read for small text' },
  bad: { icon: 'error', cls: 'text-bad', text: 'Hard to read' },
};

function Contrast({ report }) {
  if (!report?.length) return null;
  return (
    <div className="rounded-card border border-hairline bg-surface-2 p-4 mt-4">
      <div className="text-[13px] text-ink font-medium">Can people read it?</div>
      <div className="text-[11.5px] text-ink-mute mb-2">Checked against the WCAG contrast guideline. A warning never stops you saving.</div>
      {report.map((r) => {
        const L = LEVEL[r.level] || LEVEL.ok;
        return (
          <div key={r.key} className="flex items-center gap-2.5 py-1.5 text-[12px]">
            <span className="w-7 h-5 rounded-[4px] border border-hairline grid place-items-center text-[10px] font-semibold shrink-0"
              style={{ background: r.bg, color: r.fg }}>Aa</span>
            <span className="flex-1 min-w-0 text-ink-2 truncate">{r.label}</span>
            <span className="tabular-nums text-ink-mute">{r.ratio.toFixed(1)}:1</span>
            <span className={cn('flex items-center gap-1 shrink-0', L.cls)} title={L.text}>
              <Icon name={L.icon} className="text-[15px]" />
            </span>
          </div>
        );
      })}
    </div>
  );
}

function pickSeeds(theme) {
  return { ...(theme?.seeds || {}) };
}

export default function Theme() {
  const theme = useStore((s) => s.theme);
  const loadTheme = useStore((s) => s.loadTheme);
  const saveTheme = useStore((s) => s.saveTheme);
  const resetTheme = useStore((s) => s.resetTheme);
  const previewTheme = useStore((s) => s.previewTheme);

  const [draft, setDraft] = useState(null);
  const [preview, setPreview] = useState(null);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [ok, setOk] = useState('');
  const seq = useRef(0);

  useEffect(() => { if (!theme) loadTheme(); }, [theme, loadTheme]);
  useEffect(() => { if (theme?.seeds) { setDraft(pickSeeds(theme)); setPreview(theme); } }, [theme]);

  const dirty = useMemo(() => {
    if (!draft || !theme?.seeds) return false;
    return Object.keys(draft).some((k) => String(draft[k] ?? '') !== String(theme.seeds[k] ?? ''));
  }, [draft, theme]);

  // Re-derive the preview 250ms after the last change. Late answers from an
  // older draft are dropped, so fast typing cannot leave a stale preview.
  useEffect(() => {
    if (!draft || !dirty) { if (theme) setPreview(theme); return undefined; }
    const n = ++seq.current;
    const t = setTimeout(() => {
      previewTheme(draft).then((p) => { if (n === seq.current) setPreview(p); }).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [draft, dirty, theme, previewTheme]);

  if (!theme || !draft) return <div className="p-12 text-center text-ink-mute text-[13px]">Loading theme…</div>;
  if (theme.error) return <div className="crm-empty">Could not load the theme settings.</div>;

  const disabled = !theme.can_edit || !theme.installed;
  const set = (field, value) => { setDraft((d) => ({ ...d, [field]: value })); setOk(''); setErr(''); };
  const fonts = theme.fonts || {};
  const anyCustom = FONTS.some(([, f]) => draft[f] === 'Custom');

  const save = async () => {
    setSaving(true); setErr(''); setOk('');
    try {
      await saveTheme(draft);
      setOk('Saved — the whole CRM now uses this theme.');
    } catch (e) {
      setErr(e.message || 'Could not save the theme.');
    } finally {
      setSaving(false);
    }
  };
  const reset = async () => {
    if (!window.confirm('Put the CRM back to its shipped look? Every theme setting will be cleared.')) return;
    setSaving(true); setErr(''); setOk('');
    try {
      await resetTheme();
      setOk('Back to the shipped look.');
    } catch (e) {
      setErr(e.message || 'Could not reset the theme.');
    } finally {
      setSaving(false);
    }
  };

  const colourPanel = (title, sub, list) => (
    <Panel title={title} sub={sub}>
      {list.map((spec) => (
        <ColourRow key={spec[0]} spec={spec} value={draft[spec[0]]} derived={preview?.derived || theme.derived}
          onChange={set} disabled={disabled} />
      ))}
    </Panel>
  );

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-[18px] items-start">
      <div className="min-w-0 order-2 xl:order-1">
        {colourPanel('Brand colours', 'The colour people recognise as yours', COLOURS.brand)}
        <Panel title="Main buttons" sub="Where your brand colour shows up">
          <FieldRow label="Use accent for main buttons"
            plain="Off: main buttons are near-black and your brand colour is just trim. On: buttons, the focus ring and the active menu item use your brand colour."
            tech="--primary, --ring, active nav item">
            <Toggle on={!!Number(draft.theme_accent_primary)} disabled={disabled || !draft.theme_accent}
              onClick={() => set('theme_accent_primary', Number(draft.theme_accent_primary) ? 0 : 1)} />
          </FieldRow>
          {!draft.theme_accent && <div className="text-[11.5px] text-ink-mute pt-2">Set an Accent colour first.</div>}
        </Panel>
        {colourPanel('Neutral colours', 'Text, backgrounds and lines — most of what you see', COLOURS.neutral)}
        {colourPanel('Status colours', 'Each one also makes its own pale badge background', COLOURS.status)}

        <Panel title="Fonts" sub="Bundled fonts need no internet connection">
          {FONTS.map(([role, field, nameField, label, plain, tech]) => (
            <FieldRow key={field} label={label} plain={plain} tech={tech}>
              <select className={cn(SELECT, 'w-[170px]')} disabled={disabled} value={draft[field] || ''}
                onChange={(e) => set(field, e.target.value)}>
                {(fonts[role] || ['']).map((o) => <option key={o} value={o}>{o || 'As shipped'}</option>)}
              </select>
              {draft[field] === 'Custom' && (
                <Input value={draft[nameField] || ''} disabled={disabled} placeholder="Family, e.g. Lora"
                  onChange={(e) => set(nameField, e.target.value)} className="w-[150px] h-9 text-[12.5px]" />
              )}
            </FieldRow>
          ))}
          {anyCustom && (
            <FieldRow label="Google Fonts link"
              plain="Custom fonts load from Google. Pick the font on fonts.google.com, copy its stylesheet link, and paste it here."
              tech="must start https://fonts.googleapis.com — any other address is refused">
              <Input value={draft.theme_google_fonts_url || ''} disabled={disabled}
                placeholder="https://fonts.googleapis.com/css2?family=…"
                onChange={(e) => set('theme_google_fonts_url', e.target.value.trim())} className="w-[300px] h-9 text-[12px] font-mono" />
            </FieldRow>
          )}
          {anyCustom && <div className="text-[11.5px] text-ink-mute pt-2">Custom fonts show in the preview after you save.</div>}
        </Panel>

        <Panel title="Corners" sub="How rounded things are — drag to 0 for a square, crisp look">
          {SHAPES.map((spec) => (
            <ShapeRow key={spec[0]} spec={spec} value={draft[spec[0]]} onChange={set} disabled={disabled} />
          ))}
        </Panel>

        <details className="mb-[18px] rounded-card border border-hairline bg-surface-2 px-6 py-4">
          <summary className="cursor-pointer text-[13px] text-ink font-medium">Advanced — for developers</summary>
          <div className="text-[12px] text-ink-3 mt-2 mb-2">
            CSS custom properties applied last, overriding everything above. One per line, e.g. <code>--ink-4: #54586b;</code>
          </div>
          <textarea value={draft.theme_custom_css || ''} disabled={disabled} rows={5}
            onChange={(e) => set('theme_custom_css', e.target.value)}
            className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-[12px] font-mono outline-none focus:ring-1 focus:ring-ring" />
        </details>

        <div className="flex items-center gap-3 flex-wrap mb-8">
          {disabled ? (
            <span className="text-[12px] text-ink-mute flex items-center gap-2">
              <Icon name="lock" className="text-[15px]" />
              {theme.installed ? 'Only a Sales Manager or System Manager can change the theme.' : 'Run bench migrate to enable theme settings.'}
            </span>
          ) : (
            <>
              <Button size="sm" onClick={save} disabled={saving || !dirty}
                className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5 disabled:opacity-40">
                <Icon name="check" className="text-[16px]" />{saving ? 'Saving…' : 'Save theme'}
              </Button>
              {dirty && !saving && (
                <button type="button" onClick={() => { setDraft(pickSeeds(theme)); setErr(''); }} className="text-[13px] text-ink-3 hover:text-ink">Discard changes</button>
              )}
              <button type="button" onClick={reset} disabled={saving} className="text-[13px] text-ink-3 hover:text-bad ml-auto">
                Reset to the shipped look
              </button>
            </>
          )}
          {err && <span className="basis-full text-[12px] text-bad">{err}</span>}
          {!err && ok && <span className="basis-full text-[12px] text-good flex items-center gap-1"><Icon name="check_circle" className="text-[14px]" />{ok}</span>}
        </div>
      </div>

      <div className="order-1 xl:order-2 xl:sticky xl:top-[96px]">
        <ThemePreview tokens={preview?.preview_tokens || preview?.tokens || {}} />
        <Contrast report={preview?.contrast || theme.contrast} />
      </div>
    </div>
  );
}
