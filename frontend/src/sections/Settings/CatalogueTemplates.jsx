import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import Icon from '../../components/Icon';
import { Panel, Row, Toggle, SELECT } from './parts';
import {
  templatesApi, templateGetApi, templateSaveApi, templateCopyApi, templateDeleteApi, cataloguesApi,
} from '@/lib/catalogues';

// Settings → Catalogue templates: the magazine look and wording a catalogue is
// shown with (docs/superpowers/specs/2026-10-26-crm-catalogue-magazine-design.md).
// The preview on the right is the real buyer page in preview mode: each change
// is posted to it, so what you see is what buyers will get, before saving.
const INPUT = 'h-8 w-full rounded-md border border-input bg-transparent px-2 text-[13px] outline-none focus:ring-1 focus:ring-ring';
const AREA = 'w-full rounded-md border border-input bg-transparent px-2 py-1.5 text-[13px] outline-none focus:ring-1 focus:ring-ring h-16';

// Starting points; picking one fills colours and fonts, everything else stays.
const PRESETS = {
  Almanac: { font_pair: 'almanac', brand: '#1E4D3A', brand_ink: '#F3F6EF', paper: '#F6F6F1', ink: '#18181A', accent: '#F2E3B6', accent_ink: '#6A4A06' },
  'Field guide': { font_pair: 'fieldguide', brand: '#1F3B2D', brand_ink: '#EEF2EA', paper: '#E6ECE3', ink: '#1F3B2D', accent: '#C9D6C0', accent_ink: '#1F3B2D' },
  'Market sheet': { font_pair: 'market', brand: '#14213D', brand_ink: '#FFFFFF', paper: '#FFFFFF', ink: '#111827', accent: '#FCA311', accent_ink: '#14213D' },
};
const COLOURS = [['brand', 'Brand'], ['brand_ink', 'On brand'], ['paper', 'Paper'], ['ink', 'Ink'], ['accent', 'Accent'], ['accent_ink', 'On accent']];
const SECTIONS = [['show_cover', 'Cover'], ['show_letter', 'Letter from the farm'], ['show_tabs', 'Group tabs'], ['show_mixes', 'Mixes'],
  ['show_badges', 'Badges'], ['show_notes', 'Notes'], ['show_estimate', 'Estimate in the bar'], ['show_codes', 'Codes (e.g. VBN)'],
  ['show_weight', 'Weight'], ['show_more_info', '"More about" links']];
const WORDING = [['unit_label', 'Unit (priced per)'], ['pack_label', 'Pack'], ['pack_label_plural', 'Pack, plural'], ['grade_label', 'Grade column'],
  ['bunch_label', 'Bunch column (blank hides it)'], ['weight_label', 'Weight unit'], ['price_label', 'Price column'], ['tier_label', 'Tier price'],
  ['qty_label', 'Quantity column'], ['cta_label', 'Send button']];
const COVER = [['issue_title', 'Issue title'], ['headline', 'Headline'], ['letter_heading', 'Letter heading'], ['letter_signoff', 'Letter sign-off']];

function Colour({ value, onChange, disabled }) {
  return (
    <span className="inline-flex items-center gap-2">
      <input type="color" value={/^#[0-9a-f]{6}$/i.test(value || '') ? value : '#000000'} disabled={disabled}
        onChange={(e) => onChange(e.target.value.toUpperCase())} className="w-8 h-8 rounded border border-input p-0.5 bg-transparent" />
      <input className={cn(INPUT, 'w-[92px] font-mono')} value={value || ''} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
    </span>
  );
}

// A small editable table for a child table of the template.
function Rows({ rows, cols, onChange, disabled, addLabel, blank }) {
  const set = (i, patch) => onChange(rows.map((r, n) => (n === i ? { ...r, ...patch } : r)));
  return (
    <div className="grid gap-1.5">
      {rows.map((r, i) => (
        <div key={i} className="flex gap-1.5 items-center">
          {cols.map(([k, label, kind, opts]) => (kind === 'colour'
            ? <Colour key={k} value={r[k]} disabled={disabled} onChange={(v) => set(i, { [k]: v })} />
            : kind === 'select'
              ? <select key={k} className={cn(SELECT, 'h-8 w-[110px] text-[13px]')} value={r[k] || opts[0]} disabled={disabled}
                  onChange={(e) => set(i, { [k]: e.target.value })}>{opts.map((o) => <option key={o}>{o}</option>)}</select>
              : kind === 'check'
                ? <label key={k} className="text-[12px] flex items-center gap-1"><input type="checkbox" checked={!!Number(r[k])} disabled={disabled}
                    onChange={(e) => set(i, { [k]: e.target.checked ? 1 : 0 })} />{label}</label>
                : <input key={k} className={cn(INPUT, kind === 'wide' ? 'flex-[2]' : 'flex-1')} placeholder={label} value={r[k] || ''}
                    disabled={disabled} onChange={(e) => set(i, { [k]: e.target.value })} />))}
          {!disabled && (
            <button type="button" className="text-ink-3 hover:text-bad" title="Remove" onClick={() => onChange(rows.filter((_, n) => n !== i))}>
              <Icon name="close" className="text-[16px]" />
            </button>
          )}
        </div>
      ))}
      {!disabled && (
        <button type="button" className="text-[12.5px] text-gold-text hover:underline justify-self-start" onClick={() => onChange([...rows, { ...blank }])}>
          + {addLabel}
        </button>
      )}
    </div>
  );
}

export default function CatalogueTemplates() {
  const [list, setList] = useState(null);
  const [pick, setPick] = useState('');
  const [draft, setDraft] = useState(null);
  const [saved, setSaved] = useState(null);
  const [catalogues, setCatalogues] = useState([]);
  const [previewCat, setPreviewCat] = useState('');
  const [warnings, setWarnings] = useState([]);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const frame = useRef(null);

  const loadList = useCallback(() => templatesApi().then((d) => { setList(d); return d; })
    .catch((e) => setErr(e.message)), []);
  // Open on the first template once; after a delete nothing is selected, so a
  // second click on Delete can never land on a template you did not pick.
  useEffect(() => { loadList().then((d) => setPick(d?.rows[0]?.name || '')); }, [loadList]);
  useEffect(() => {
    cataloguesApi().then((d) => {
      const rows = (d.rows || []).filter((r) => r.lines);
      setCatalogues(rows);
      setPreviewCat((c) => c || rows[0]?.name || '');
    }).catch(() => setCatalogues([]));
  }, []);
  useEffect(() => {
    if (!pick) return;
    setErr(''); setMsg(''); setWarnings([]);
    templateGetApi(pick).then((d) => { setDraft(d.template); setSaved(d.template); }).catch((e) => setErr(e.message));
  }, [pick]);

  // Post the unsaved draft to the preview (debounced).
  useEffect(() => {
    if (!draft || !frame.current) return undefined;
    const t = setTimeout(() => {
      frame.current?.contentWindow?.postMessage({ type: 'catalogue-preview', template: draft }, window.location.origin);
    }, 300);
    return () => clearTimeout(t);
  }, [draft]);

  const canEdit = !!list?.can_edit;
  const ro = !canEdit;
  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(saved), [draft, saved]);
  const set = (patch) => setDraft((d) => ({ ...d, ...patch }));
  const previewToken = catalogues.find((c) => c.name === previewCat)?.public_token;

  async function save() {
    setBusy(true); setErr(''); setMsg('');
    try {
      const out = await templateSaveApi(draft);
      setDraft(out.template); setSaved(out.template); setWarnings(out.warnings || []);
      setMsg('Saved'); loadList();
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  }
  async function copy() {
    const name = window.prompt('Name for the copy', `${pick} (copy)`);
    if (!name) return;
    try { const out = await templateCopyApi(pick, name); await loadList(); setPick(out.name); } catch (e) { setErr(e.message); }
  }
  async function remove() {
    if (!window.confirm(`Delete the template "${pick}"?`)) return;
    try {
      await templateDeleteApi(pick);
      setPick(''); setDraft(null); setSaved(null); setMsg(`Deleted ${pick}`);
      await loadList();
    } catch (e) { setErr(e.message); }
  }

  if (!list) return <div className="crm-empty">{err || 'Loading…'}</div>;
  const pairs = list.font_pairs || {};

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-[18px]">
      <div>
        <Panel title="Catalogue templates" sub="How catalogues look and read for buyers. Each catalogue picks one."
          aside={canEdit && pick ? (
            <span className="flex gap-2">
              <Button size="sm" variant="outline" className="rounded-full shadow-none" onClick={copy}><Icon name="file_copy" className="text-[15px]" />Copy</Button>
              <Button size="sm" variant="ghost" className="rounded-full shadow-none" onClick={remove}><Icon name="delete" className="text-[15px]" />Delete</Button>
            </span>) : null}>
          <div className="flex flex-wrap gap-2 mb-1">
            {list.rows.map((r) => (
              <button key={r.name} type="button" onClick={() => setPick(r.name)}
                className={cn('rounded-lg border px-3 py-2 text-left text-[13px] flex items-center gap-2',
                  r.name === pick ? 'border-ink bg-surface-2' : 'border-hairline')}>
                <span className="w-4 h-4 rounded-full border border-hairline" style={{ background: r.brand }} />
                <span><b className="font-semibold">{r.name}</b><span className="block text-[11.5px] text-ink-mute">
                  {r.group_by} · {r.catalogues_using} catalogue{r.catalogues_using === 1 ? '' : 's'}</span></span>
              </button>
            ))}
          </div>
          {!pick && <div className="mt-2 text-[12.5px] text-ink-mute">{msg ? `${msg}. ` : ''}Pick a template to edit it.</div>}
          {err && !draft && <div className="mt-2 text-[12.5px] text-bad">{err}</div>}
          {ro && <div className="mt-2 text-[12px] text-ink-mute flex items-center gap-1.5"><Icon name="lock" className="text-[14px]" />Only a sales manager can change templates.</div>}
        </Panel>

        {draft && (
          <>
            <Panel title="Look" sub="Start from a preset, then adjust">
              <Row label="Preset" help="Fills colours and fonts; your wording stays.">
                <select className={cn(SELECT, 'w-[180px]')} disabled={ro} value={draft.preset || 'Almanac'}
                  onChange={(e) => set({ preset: e.target.value, ...PRESETS[e.target.value] })}>
                  {Object.keys(PRESETS).map((p) => <option key={p}>{p}</option>)}
                </select>
              </Row>
              <Row label="Fonts" help="Bundled with the app — buyer pages load nothing from outside.">
                <select className={cn(SELECT, 'w-[260px]')} disabled={ro} value={draft.font_pair} onChange={(e) => set({ font_pair: e.target.value })}>
                  {Object.entries(pairs).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                </select>
              </Row>
              {COLOURS.map(([k, label]) => (
                <Row key={k} label={label}><Colour value={draft[k]} disabled={ro} onChange={(v) => set({ [k]: v })} /></Row>
              ))}
              {warnings.length > 0 && (
                <ul className="mt-2 text-[12px] text-warn list-disc pl-5">{warnings.map((w) => <li key={w}>{w}</li>)}</ul>
              )}
            </Panel>

            <Panel title="Cover and letter">
              <Row label="Cover picture" help="A collage of the catalogue's item photos, or one uploaded image.">
                <select className={cn(SELECT, 'w-[160px]')} disabled={ro} value={draft.cover_mode || 'Collage'} onChange={(e) => set({ cover_mode: e.target.value })}>
                  <option>Collage</option><option>Image</option>
                </select>
              </Row>
              {COVER.map(([k, label]) => (
                <Row key={k} label={label}><input className={cn(INPUT, 'w-[280px]')} disabled={ro} value={draft[k] || ''} onChange={(e) => set({ [k]: e.target.value })} /></Row>
              ))}
              <Row label="Cover line"><textarea className={cn(AREA, 'w-[280px]')} disabled={ro} value={draft.dek || ''} onChange={(e) => set({ dek: e.target.value })} /></Row>
            </Panel>

            <Panel title="Wording" sub="{unit}, {pack}, {packs}, {Packs} and {n} (the tier threshold) are filled in">
              {WORDING.map(([k, label]) => (
                <Row key={k} label={label}><input className={cn(INPUT, 'w-[220px]')} disabled={ro} value={draft[k] || ''} onChange={(e) => set({ [k]: e.target.value })} /></Row>
              ))}
              <Row label="Thank-you text"><textarea className={cn(AREA, 'w-[280px]')} disabled={ro} value={draft.thank_you_text || ''} onChange={(e) => set({ thank_you_text: e.target.value })} /></Row>
              <Row label="Closed-offer text"><textarea className={cn(AREA, 'w-[280px]')} disabled={ro} value={draft.closed_text || ''} onChange={(e) => set({ closed_text: e.target.value })} /></Row>
              <div className="mt-3 text-[12.5px] font-medium text-ink">How often buyers can order</div>
              <div className="text-[11.5px] text-ink-mute mb-2">The first is the default. The period wording is used in the estimate, e.g. "a week".</div>
              <Rows rows={draft.frequencies || []} disabled={ro} addLabel="Add a frequency" blank={{ label: '', period_text: '', recurring: 0 }}
                cols={[['label', 'Label'], ['period_text', 'Period wording'], ['recurring', 'Recurring', 'check']]}
                onChange={(v) => set({ frequencies: v })} />
            </Panel>

            <Panel title="Grouping" sub="How the catalogue is split into sections and tabs">
              <Row label="Group by">
                <select className={cn(SELECT, 'w-[180px]')} disabled={ro} value={draft.group_by} onChange={(e) => set({ group_by: e.target.value })}>
                  <option>Colour</option><option>Item Group</option><option>Grade</option>
                </select>
              </Row>
              <Row label="Group for anything unmatched"><input className={cn(INPUT, 'w-[180px]')} disabled={ro} value={draft.fallback_group_label || ''} onChange={(e) => set({ fallback_group_label: e.target.value })} /></Row>
              {draft.group_by === 'Colour' && (
                <>
                  <div className="mt-3 text-[12.5px] font-medium text-ink">Colour groups</div>
                  <div className="text-[11.5px] text-ink-mute mb-2">In tab order. A line goes to the first group whose words match its colour.</div>
                  <Rows rows={draft.colour_groups || []} disabled={ro} addLabel="Add a colour group" blank={{ label: '', swatch: '#DDDDDD', swatch_ink: '#111111', keywords: '' }}
                    cols={[['label', 'Group'], ['swatch', 'Swatch', 'colour'], ['swatch_ink', 'Text', 'colour'], ['keywords', 'Colour words, comma separated', 'wide']]}
                    onChange={(v) => set({ colour_groups: v })} />
                </>
              )}
            </Panel>

            <Panel title="Spec columns and badges" sub="Crop details, e.g. Cup score, Dry matter, Process">
              <Rows rows={draft.spec_columns || []} disabled={ro} addLabel="Add a spec column" blank={{ key: '', label: '', display: 'Column', import_headers: '' }}
                cols={[['key', 'key (e.g. cup_score)'], ['label', 'Label'], ['display', 'Shows as', 'select', ['Column', 'Badge', 'Subtitle']], ['import_headers', 'Sheet headers to import from', 'wide']]}
                onChange={(v) => set({ spec_columns: v })} />
              <div className="mt-4 text-[12.5px] font-medium text-ink mb-2">Badges</div>
              <Rows rows={draft.badges || []} disabled={ro} addLabel="Add a badge" blank={{ label: '', background: '#1E4D3A', ink: '#FFFFFF' }}
                cols={[['label', 'Badge'], ['background', 'Background', 'colour'], ['ink', 'Text', 'colour']]}
                onChange={(v) => set({ badges: v })} />
            </Panel>

            <Panel title="Sections">
              {SECTIONS.map(([k, label]) => (
                <Row key={k} label={label}><Toggle on={!!Number(draft[k])} disabled={ro} onClick={() => set({ [k]: Number(draft[k]) ? 0 : 1 })} /></Row>
              ))}
            </Panel>

            {canEdit && (
              <div className="sticky bottom-3 z-10 flex items-center gap-3 rounded-full bg-surface border border-hairline shadow-lg px-4 py-2.5 w-fit">
                <Button size="sm" onClick={save} disabled={busy || !dirty}
                  className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5">
                  <Icon name="check" className="text-[16px]" />{busy ? 'Saving…' : 'Save template'}
                </Button>
                {dirty && <button type="button" className="text-[13px] text-ink-3 hover:text-ink" onClick={() => setDraft(saved)}>Discard changes</button>}
                {(err || msg) && <span className={cn('text-[12.5px]', err ? 'text-bad' : 'text-ink-mute')}>{err || msg}</span>}
              </div>
            )}
          </>
        )}
      </div>

      <div className="xl:sticky xl:top-4 self-start">
        <Panel title="Live preview" sub="The real buyer page with your unsaved changes"
          aside={(
            <select className={cn(SELECT, 'w-[220px]')} value={previewCat} onChange={(e) => setPreviewCat(e.target.value)}>
              {catalogues.map((c) => <option key={c.name} value={c.name}>{c.title}</option>)}
            </select>)}>
          {previewToken ? (
            <iframe ref={frame} title="Catalogue preview" src={`/catalogue/${previewToken}?preview=1`}
              onLoad={() => frame.current?.contentWindow?.postMessage({ type: 'catalogue-preview', template: draft }, window.location.origin)}
              className="w-full h-[78vh] rounded-lg border border-hairline bg-white" />
          ) : <div className="crm-empty">Make a catalogue with some lines to preview templates against it.</div>}
        </Panel>
      </div>
    </div>
  );
}
