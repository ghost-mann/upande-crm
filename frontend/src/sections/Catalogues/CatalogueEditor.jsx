import { useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardSub } from '@/components/ui/card';
import { fmt } from '@shared/utils';
import Icon from '../../components/Icon';
import LinkSearch from '../../components/LinkSearch';
import { LABEL } from '../../components/DialogShell';
import ShareDialog from './ShareDialog';
import {
  catalogueGetApi, catalogueSaveApi, catalogueStatusApi, catalogueDuplicateApi, catalogueImportApi,
  uploadPrivate, uploadPublic, copyText, templatesApi, templateGetApi, CATALOGUE_TONE,
} from '@/lib/catalogues';

// One catalogue: its header, its lines grouped by item, the offer-sheet import,
// and sharing. Lines are edited in place and saved together.
const INPUT = 'h-8 w-full rounded-md border border-input bg-transparent px-2 text-[13px] outline-none focus:ring-1 focus:ring-ring';
const NUM = `${INPUT} text-right tabular-nums`;
const AREA = 'w-full rounded-md border border-input bg-transparent px-2 py-1.5 text-[13px] outline-none focus:ring-1 focus:ring-ring h-28';
const W = { grade: 'min-w-[84px]', box: 'min-w-[96px]', colour: 'min-w-[84px]', pack: 'min-w-[72px]', bunch: 'min-w-[64px]', weight: 'min-w-[72px]', price: 'min-w-[84px]', url: 'min-w-[180px]' };

const blank = () => ({ title: '', currencies: 'USD', status: 'Draft', volume_tier_qty: '', terms: '', lines: [],
  template: 'Flowers almanac', products: [], mixes: [] });
const curList = (s) => String(s || '').split(',').map((c) => c.trim().toUpperCase()).filter(Boolean);
let seq = 0;
const key = () => `k${++seq}`;

export default function CatalogueEditor({ name, onBack, onOpen }) {
  const [doc, setDoc] = useState(name ? null : blank());
  const [url, setUrl] = useState('');
  const [err, setErr] = useState('');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [unmatched, setUnmatched] = useState([]);
  const [importing, setImporting] = useState(false);
  const [share, setShare] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [tpl, setTpl] = useState(null);
  const file = useRef(null);
  const cover = useRef(null);

  function take(res) {
    const c = res.catalogue;
    setDoc({ ...c, lines: c.lines.map((l) => ({ ...l, _k: key() })) });
    setUrl(res.public_url);
    setDirty(false);
  }

  useEffect(() => {
    if (name) catalogueGetApi(name).then(take).catch((e) => setErr(e.message || 'Could not load'));
  }, [name]);
  useEffect(() => { templatesApi().then((d) => setTemplates(d.rows)).catch(() => setTemplates([])); }, []);
  useEffect(() => {
    if (doc?.template) templateGetApi(doc.template).then((d) => setTpl(d.template)).catch(() => setTpl(null));
  }, [doc?.template]);

  const currencies = useMemo(() => curList(doc?.currencies), [doc?.currencies]);
  const groups = useMemo(() => {
    const out = [];
    const at = {};
    (doc?.lines || []).forEach((l, i) => {
      if (at[l.item] == null) { at[l.item] = out.length; out.push({ item: l.item, item_name: l.item_name || l.item, rows: [] }); }
      out[at[l.item]].rows.push(i);
    });
    return out;
  }, [doc?.lines]);

  if (!doc) return <div className="crm-empty">{err || 'Loading…'}</div>;
  const editable = doc.can_edit !== false;
  const lineSpecs = (tpl?.spec_columns || []).filter((c) => c.display === 'Column');
  const productSpecs = (tpl?.spec_columns || []).filter((c) => c.display !== 'Column');
  const colourGroups = tpl?.group_by === 'Colour' ? (tpl.colour_groups || []) : [];
  const extraCols = lineSpecs.length + 1;
  const products = doc.products || [];
  const productOf = (item) => products.find((p) => p.item === item) || { item, badges: [], note: '', specs: {} };
  const setProduct = (item, patch) => {
    const has = products.some((p) => p.item === item);
    set({ products: has ? products.map((p) => (p.item === item ? { ...p, ...patch } : p))
      : [...products, { ...productOf(item), ...patch }] });
  };
  const mixes = doc.mixes || [];
  const setMix = (i, patch) => set({ mixes: mixes.map((m, n) => (n === i ? { ...m, ...patch } : m)) });
  const lineLabel = (l) => `${l.item_name || l.item} · ${l.grade || '—'} · ${l.box_type || ''}`;

  const set = (patch) => { setDoc((d) => ({ ...d, ...patch })); setDirty(true); };
  const setLine = (i, patch) => set({ lines: doc.lines.map((l, n) => (n === i ? { ...l, ...patch } : l)) });
  const setPrice = (i, cur, field, v) => {
    const prices = { ...(doc.lines[i].prices || {}) };
    const entry = { ...(prices[cur] || {}) };
    if (v === '') delete entry[field]; else entry[field] = Number(v);
    if (Object.keys(entry).length) prices[cur] = entry; else delete prices[cur];
    setLine(i, { prices });
  };
  const removeLine = (i) => set({ lines: doc.lines.filter((_, n) => n !== i) });
  const addLine = (item, row) => {
    if (!item) return;
    set({ lines: [...doc.lines, { _k: key(), item, item_name: row?.description || item, box_type: 'Standard', prices: {} }] });
  };

  async function save() {
    setSaving(true); setErr(''); setNote('');
    try {
      // Lines keep their `name`: buyers with the page open submit against it.
      const payload = { ...doc, lines: doc.lines.map(({ _k, item_name, ...l }) => l) };
      delete payload.can_edit;
      const res = await catalogueSaveApi(payload);
      take(res);
      setNote('Saved');
      if (!name) onOpen(res.catalogue.name);
      return true;
    } catch (e) { setErr(e.message); return false; } finally { setSaving(false); }
  }

  async function status(next) {
    if (dirty && !(await save())) return;
    setErr('');
    try {
      await catalogueStatusApi(doc.name, next);
      setDoc((d) => ({ ...d, status: next }));
    } catch (e) { setErr(e.message); }
  }

  async function duplicate() {
    try { onOpen((await catalogueDuplicateApi(doc.name)).name); } catch (e) { setErr(e.message); }
  }

  async function runImport(f) {
    if (!f) return;
    if (!currencies.length) { setErr('Set the currencies first (e.g. USD, EUR).'); return; }
    if (doc.lines.length && !window.confirm(`Replace the ${doc.lines.length} current lines with the offer sheet?`)) return;
    setImporting(true); setErr(''); setNote('');
    try {
      const fileUrl = await uploadPrivate(f);
      const res = await catalogueImportApi(fileUrl, currencies, doc.name, doc.template);
      const lines = res.lines.map((l) => ({ ...l, item_name: l.product, _k: key() }));
      // Badge/Subtitle specs come back per item: merge them onto the products.
      const prods = [...products];
      (res.products || []).forEach((rp) => {
        const at = prods.findIndex((p) => p.item === rp.item);
        if (at >= 0) prods[at] = { ...prods[at], specs: { ...(prods[at].specs || {}), ...rp.specs } };
        else prods.push({ item: rp.item, badges: [], note: '', specs: rp.specs });
      });
      set({ lines, products: prods, ...(res.terms && !doc.terms ? { terms: res.terms } : {}) });
      setUnmatched(res.unmatched.map((u) => ({ ...u, _k: key() })));
      setNote(`Imported ${fmt(lines.length)} lines${res.unmatched.length ? ` · ${res.unmatched.length} need an item` : ''} — review, then Save.`);
    } catch (e) { setErr(e.message); } finally { setImporting(false); if (file.current) file.current.value = ''; }
  }

  function mapUnmatched(u, item) {
    if (!item) return;
    set({ lines: [...doc.lines, { ...u, item, item_name: u.product, _k: key() }] });
    setUnmatched((rows) => rows.filter((r) => r._k !== u._k));
  }

  const btn = 'rounded-full shadow-none px-4';
  const gold = `${btn} bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white`;
  return (
    <>
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <button type="button" onClick={onBack} className="text-[13px] text-ink-3 hover:text-ink inline-flex items-center gap-1">
          <Icon name="arrow_back" className="text-[16px]" />Catalogues
        </button>
        {doc.name && <span className={`bdg ${CATALOGUE_TONE[doc.status]}`}>{doc.status}</span>}
        <div className="flex-1" />
        {editable && <Button size="sm" onClick={save} disabled={saving} className={gold}><Icon name="check" className="text-[16px]" />{saving ? 'Saving…' : 'Save'}</Button>}
        {editable && (
          <>
            <input ref={file} type="file" accept=".xlsx" className="hidden" onChange={(e) => runImport(e.target.files[0])} />
            <Button size="sm" variant="outline" className={btn} disabled={importing} onClick={() => file.current?.click()}>
              <Icon name="upload_file" className="text-[16px]" />{importing ? 'Importing…' : 'Import offer sheet'}
            </Button>
          </>
        )}
        {doc.name && editable && doc.status !== 'Live' && <Button size="sm" variant="outline" className={btn} onClick={() => status('Live')}><Icon name="public" className="text-[16px]" />Go live</Button>}
        {doc.name && editable && doc.status === 'Live' && <Button size="sm" variant="outline" className={btn} onClick={() => status('Closed')}><Icon name="block" className="text-[16px]" />Close</Button>}
        {doc.status === 'Live' && url && (
          <>
            <Button size="sm" variant="outline" className={btn} onClick={async () => { await copyText(url); setNote('Public link copied'); }}>
              <Icon name="content_copy" className="text-[16px]" />Public link
            </Button>
            <Button size="sm" className={gold} onClick={() => setShare(true)}><Icon name="ios_share" className="text-[16px]" />Send to…</Button>
          </>
        )}
        {doc.name && doc.public_token && (
          <Button size="sm" variant="outline" className={btn} title="Opens the buyer's page in preview mode (nothing is recorded)"
            onClick={() => window.open(`/catalogue/${doc.public_token}?preview=1`, '_blank', 'noopener')}>
            <Icon name="visibility" className="text-[16px]" />Preview
          </Button>
        )}
        {doc.name && <Button size="sm" variant="ghost" className={btn} onClick={duplicate}><Icon name="file_copy" className="text-[16px]" />Duplicate</Button>}
      </div>
      {(err || note) && <div className={`mb-3 text-[12.5px] ${err ? 'text-bad' : 'text-ink-mute'}`}>{err || note}</div>}

      <Card className="mb-4">
        <div className="p-5 grid grid-cols-1 md:grid-cols-3 gap-4">
          <label className="md:col-span-2"><span className={LABEL}>Title</span>
            <input className={INPUT} value={doc.title || ''} disabled={!editable} onChange={(e) => set({ title: e.target.value })} placeholder="e.g. FOB offer Oct–Dec 2026" /></label>
          <label><span className={LABEL}>Company</span>
            <LinkSearch doctype="Company" value={doc.company} disabled={!editable} onChange={(v) => set({ company: v })} /></label>
          <label><span className={LABEL}>Currencies</span>
            <input className={INPUT} value={doc.currencies || ''} disabled={!editable} onChange={(e) => set({ currencies: e.target.value })} placeholder="USD, EUR" /></label>
          <label><span className={LABEL}>Valid from</span>
            <input type="date" className={INPUT} value={doc.valid_from || ''} disabled={!editable} onChange={(e) => set({ valid_from: e.target.value || null })} /></label>
          <label><span className={LABEL}>Valid to</span>
            <input type="date" className={INPUT} value={doc.valid_to || ''} disabled={!editable} onChange={(e) => set({ valid_to: e.target.value || null })} /></label>
          <label><span className={LABEL}>Magazine template</span>
            <select className={INPUT} value={doc.template || ''} disabled={!editable} onChange={(e) => set({ template: e.target.value })}>
              {templates.map((t) => <option key={t.name} value={t.name}>{t.name}</option>)}
            </select></label>
          <label><span className={LABEL}>Cover picture (overrides the template's)</span>
            <span className="flex items-center gap-2">
              <input ref={cover} type="file" accept="image/*" className="hidden" onChange={async (e) => {
                const f = e.target.files[0]; if (!f) return;
                try { set({ cover_image: await uploadPublic(f) }); } catch (x) { setErr(x.message); }
              }} />
              <Button size="sm" variant="outline" className={btn} disabled={!editable} onClick={() => cover.current?.click()}>
                <Icon name="image" className="text-[16px]" />{doc.cover_image ? 'Replace' : 'Upload'}
              </Button>
              {doc.cover_image && <>
                <img src={doc.cover_image} alt="" className="h-8 w-12 object-cover rounded" />
                {editable && <button type="button" className="text-ink-3 hover:text-bad text-[12px]" onClick={() => set({ cover_image: null })}>Remove</button>}
              </>}
            </span></label>
          <label><span className={LABEL}>Tier price above (boxes)</span>
            <input type="number" min="0" className={NUM} value={doc.volume_tier_qty || ''} disabled={!editable} onChange={(e) => set({ volume_tier_qty: e.target.value === '' ? null : Number(e.target.value) })} placeholder="e.g. 4" /></label>
          <label className="md:col-span-3"><span className={LABEL}>Ordering terms (shown to buyers)</span>
            <textarea className={AREA} value={(doc.terms || '').replace(/<\/p>\s*<p>/g, '\n').replace(/<\/?p>/g, '')} disabled={!editable}
              onChange={(e) => set({ terms: e.target.value.split('\n').filter((t) => t.trim()).map((t) => `<p>${t.replace(/</g, '&lt;')}</p>`).join('') })} /></label>
        </div>
      </Card>

      {unmatched.length > 0 && (
        <Card className="mb-4">
          <CardHeader><div><CardTitle>Rows without an item</CardTitle><CardSub>Pick the item each one is, or skip it</CardSub></div></CardHeader>
          <div className="px-5 pb-4 grid gap-2">
            {unmatched.map((u) => (
              <div key={u._k} className="flex items-center gap-3 text-[13px]">
                <span className="w-[320px] truncate">{u.product} · {u.grade} · {u.box_type}</span>
                <LinkSearch doctype="Item" className="w-[280px]" value="" onChange={(v) => mapUnmatched(u, v)} placeholder="Map to item…" />
                <button type="button" className="text-ink-3 hover:text-bad text-[12px]" onClick={() => setUnmatched((r) => r.filter((x) => x._k !== u._k))}>Skip</button>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div><CardTitle>Lines</CardTitle><CardSub>{fmt(doc.lines.length)} lines · {fmt(groups.length)} items · prices per unit</CardSub></div>
          {editable && <LinkSearch doctype="Item" className="w-[260px]" value="" onChange={addLine} placeholder="Add an item…" />}
        </CardHeader>
        <div className="tbl-wrap overflow-x-auto">
          <table className="tbl">
            <thead>
              <tr>
                <th>Grade</th><th>Box</th><th>Colour</th><th>Group</th>{lineSpecs.map((c) => <th key={c.key}>{c.label}</th>)}
                <th className="cell-num">Pack</th><th>Bunch</th><th className="cell-num">Weight</th>
                {currencies.map((c) => <th key={c} className="cell-num" colSpan={2}>{c} price · tier</th>)}
                <th>Info link</th><th />
              </tr>
            </thead>
            <tbody>
              {groups.length ? groups.map((g) => [
                <tr key={`${g.item}-h`}><td colSpan={8 + extraCols + currencies.length * 2} className="!bg-surface-2 font-semibold text-ink">{g.item_name}</td></tr>,
                ...g.rows.map((i) => {
                  const l = doc.lines[i];
                  return (
                    <tr key={l._k}>
                      <td><input className={`${INPUT} ${W.grade}`} disabled={!editable} value={l.grade || ''} onChange={(e) => setLine(i, { grade: e.target.value })} /></td>
                      <td><input className={`${INPUT} ${W.box}`} disabled={!editable} value={l.box_type || ''} onChange={(e) => setLine(i, { box_type: e.target.value })} /></td>
                      <td><input className={`${INPUT} ${W.colour}`} disabled={!editable} value={l.color || ''} onChange={(e) => setLine(i, { color: e.target.value })} /></td>
                      <td>{colourGroups.length ? (
                        <select className={`${INPUT} min-w-[120px]`} disabled={!editable} value={l.colour_group || ''} onChange={(e) => setLine(i, { colour_group: e.target.value || null })}>
                          <option value="">{l.group ? `Auto: ${l.group}` : 'Auto'}</option>
                          {colourGroups.map((cg) => <option key={cg.label}>{cg.label}</option>)}
                        </select>) : <span className="text-ink-mute text-[12px] whitespace-nowrap">{l.group || '—'}</span>}</td>
                      {lineSpecs.map((c) => (
                        <td key={c.key}><input className={`${INPUT} min-w-[90px]`} disabled={!editable} value={l.specs?.[c.key] ?? ''}
                          onChange={(e) => setLine(i, { specs: { ...(l.specs || {}), [c.key]: e.target.value } })} /></td>
                      ))}
                      <td><input className={`${NUM} ${W.pack}`} disabled={!editable} type="number" value={l.pack_qty ?? ''} onChange={(e) => setLine(i, { pack_qty: e.target.value === '' ? null : Number(e.target.value) })} /></td>
                      <td><input className={`${INPUT} ${W.bunch}`} disabled={!editable} value={l.bunch || ''} onChange={(e) => setLine(i, { bunch: e.target.value })} /></td>
                      <td><input className={`${NUM} ${W.weight}`} disabled={!editable} type="number" value={l.weight ?? ''} onChange={(e) => setLine(i, { weight: e.target.value === '' ? null : Number(e.target.value) })} /></td>
                      {currencies.map((c) => [
                        <td key={`${c}p`}><input className={`${NUM} ${W.price}`} disabled={!editable} type="number" step="any" value={l.prices?.[c]?.price ?? ''} onChange={(e) => setPrice(i, c, 'price', e.target.value)} /></td>,
                        <td key={`${c}t`}><input className={`${NUM} ${W.price}`} disabled={!editable} type="number" step="any" value={l.prices?.[c]?.tier ?? ''} onChange={(e) => setPrice(i, c, 'tier', e.target.value)} /></td>,
                      ])}
                      <td><input className={`${INPUT} ${W.url}`} disabled={!editable} value={l.info_url || ''} onChange={(e) => setLine(i, { info_url: e.target.value })} /></td>
                      <td>{editable && <button type="button" className="text-ink-3 hover:text-bad" title="Remove line" onClick={() => removeLine(i)}><Icon name="close" className="text-[16px]" /></button>}</td>
                    </tr>
                  );
                }),
              ]) : (
                <tr><td colSpan={8 + extraCols + currencies.length * 2}><div className="crm-empty">No lines — import an offer sheet or add an item</div></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {groups.length > 0 && (
        <Card className="mt-4">
          <CardHeader><div><CardTitle>Products on the page</CardTitle>
            <CardSub>A photo, badges, a note and {productSpecs.length ? productSpecs.map((c) => c.label).join(', ') : 'details'} — shown once per product</CardSub></div></CardHeader>
          <div className="px-5 pb-4 grid gap-3">
            {groups.map((g) => {
              const p = productOf(g.item);
              return (
                <div key={g.item} className="grid grid-cols-1 md:grid-cols-[220px_1fr_1fr] gap-3 items-start border-t border-hairline pt-3">
                  <div>
                    <div className="font-semibold text-[13px] text-ink">{g.item_name}</div>
                    <span className="mt-1.5 flex items-center gap-2">
                      {p.image && <img src={p.image} alt="" className="h-10 w-10 object-cover rounded bg-surface-2" />}
                      <label className={`text-[12px] text-gold-text ${editable ? 'cursor-pointer hover:underline' : 'opacity-50'}`}
                        title="This catalogue's photo; blank uses the item's image">
                        {p.image ? 'Replace photo' : 'Add photo'}
                        <input type="file" accept="image/*" className="hidden" disabled={!editable} onChange={async (e) => {
                          const f = e.target.files[0]; if (!f) return;
                          try { setProduct(g.item, { image: await uploadPublic(f) }); } catch (x) { setErr(x.message); }
                        }} />
                      </label>
                      {p.image && editable && <button type="button" className="text-[12px] text-ink-3 hover:text-bad"
                        onClick={() => setProduct(g.item, { image: null })}>Remove</button>}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(tpl?.badges || []).map((b) => {
                      const on = (p.badges || []).includes(b.label);
                      return (
                        <button key={b.label} type="button" disabled={!editable}
                          onClick={() => setProduct(g.item, { badges: on ? p.badges.filter((x) => x !== b.label) : [...(p.badges || []), b.label] })}
                          className="rounded px-2 py-0.5 text-[11.5px] font-semibold border"
                          style={on ? { background: b.background, color: b.ink, borderColor: b.background } : { opacity: 0.55 }}>
                          {b.label}
                        </button>
                      );
                    })}
                    {productSpecs.map((c) => (
                      <input key={c.key} className={`${INPUT} w-[150px]`} placeholder={c.label} disabled={!editable} value={p.specs?.[c.key] ?? ''}
                        onChange={(e) => setProduct(g.item, { specs: { ...(p.specs || {}), [c.key]: e.target.value } })} />
                    ))}
                  </div>
                  <textarea className={`${INPUT} h-14 py-1`} placeholder="Note — blank uses the item's description" disabled={!editable}
                    value={p.note || ''} onChange={(e) => setProduct(g.item, { note: e.target.value })} />
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {doc.lines.length > 0 && (
        <Card className="mt-4">
          <CardHeader><div><CardTitle>Mixes</CardTitle><CardSub>Ready-made combinations buyers add in one tap</CardSub></div>
            {editable && <Button size="sm" variant="outline" className={btn} onClick={() => set({ mixes: [...mixes, { title: '', items: [] }] })}>
              <Icon name="add" className="text-[16px]" />Add a mix</Button>}
          </CardHeader>
          <div className="px-5 pb-4 grid gap-4">
            {!mixes.length && <div className="text-[12.5px] text-ink-mute">No mixes yet.</div>}
            {mixes.map((m, i) => (
              <div key={i} className="grid gap-2 border-t border-hairline pt-3">
                <div className="flex gap-2 items-center">
                  <input className={`${INPUT} w-[240px] font-semibold`} placeholder="Mix name, e.g. Cool whites" disabled={!editable}
                    value={m.title || ''} onChange={(e) => setMix(i, { title: e.target.value })} />
                  <input className={`${INPUT} flex-1`} placeholder="Summary (blank: the variety names)" disabled={!editable}
                    value={m.summary || ''} onChange={(e) => setMix(i, { summary: e.target.value })} />
                  {editable && <button type="button" className="text-ink-3 hover:text-bad" title="Remove mix" onClick={() => set({ mixes: mixes.filter((_, n) => n !== i) })}>
                    <Icon name="delete" className="text-[16px]" /></button>}
                </div>
                {(m.items || []).map((it, j) => (
                  <div key={j} className="flex gap-2 items-center pl-4">
                    <select className={`${INPUT} flex-1`} disabled={!editable} value={it.line}
                      onChange={(e) => setMix(i, { items: m.items.map((x, n) => (n === j ? { ...x, line: e.target.value } : x)) })}>
                      {!doc.lines.some((l) => l.name === it.line) && <option value={it.line}>(removed line)</option>}
                      {doc.lines.filter((l) => l.name).map((l) => <option key={l.name} value={l.name}>{lineLabel(l)}</option>)}
                    </select>
                    <input type="number" min="1" className={`${NUM} w-[80px]`} disabled={!editable} value={it.boxes ?? 1}
                      onChange={(e) => setMix(i, { items: m.items.map((x, n) => (n === j ? { ...x, boxes: Number(e.target.value) || 1 } : x)) })} />
                    {editable && <button type="button" className="text-ink-3 hover:text-bad" onClick={() => setMix(i, { items: m.items.filter((_, n) => n !== j) })}>
                      <Icon name="close" className="text-[16px]" /></button>}
                  </div>
                ))}
                {editable && (doc.lines.some((l) => l.name) ? (
                  <button type="button" className="text-[12.5px] text-gold-text hover:underline justify-self-start pl-4"
                    onClick={() => setMix(i, { items: [...(m.items || []), { line: doc.lines.find((l) => l.name).name, boxes: 1 }] })}>+ Add a line</button>
                ) : <div className="text-[12px] text-ink-mute pl-4">Save the catalogue first to pick its lines.</div>)}
              </div>
            ))}
          </div>
        </Card>
      )}

      {share && <ShareDialog catalogue={doc} onClose={() => setShare(false)} />}
    </>
  );
}
