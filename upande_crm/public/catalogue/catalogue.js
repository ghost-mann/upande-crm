// The buyer's catalogue page (/catalogue/<token>): the "colour almanac".
//
// Renders the payload of upande_crm.api.catalogue_public.catalogue_view, which
// is built by api/catalogue_display.build_display from the catalogue and its
// magazine template: theme, wording, section switches, groups (a product
// repeats in each group it has lines in), mixes and frequencies. No framework.
// Every string from the server goes through esc(); the catalogue's terms are
// the one piece of HTML, as before. What the buyer typed lives in `state`, so
// switching currency or opening the form never loses an entry.
//
// Preview mode (data-preview = catalogue name, CRM users only): the template
// editor's iframe. It reads crm_catalogue_preview, re-renders on a
// {type: 'catalogue-preview', template} postMessage from this origin, records
// nothing and cannot submit.
(function () {
  const app = document.getElementById('cat-app');
  const token = app.dataset.token;
  const csrf = app.dataset.csrf;
  const previewName = app.dataset.preview || '';
  const M = '/api/method/upande_crm.api.';
  const state = { data: null, currency: null, picks: {}, view: 'list', error: '', form: null, mixed: {} };

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const safeUrl = (u) => (/^(https?:\/\/|\/)/i.test(String(u || '')) ? String(u) : '');
  const num = (v, d) => (v == null || v === '' ? '' : Number(v).toLocaleString(undefined, { maximumFractionDigits: d }));
  const money = (v, digits = 4) => (v == null ? null : Number(v).toLocaleString(undefined, {
    style: 'currency', currency: state.currency, minimumFractionDigits: Math.min(2, digits), maximumFractionDigits: digits }));
  const day = (iso) => {
    if (!iso) return '';
    const [y, m, d] = iso.split('-').map(Number); // local date: no UTC shift
    return new Date(y, m - 1, d).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  };

  function call(method, args) {
    const headers = { Accept: 'application/json', 'Content-Type': 'application/json' };
    if (csrf) headers['X-Frappe-CSRF-Token'] = csrf;
    return fetch(M + method, { method: 'POST', headers, body: JSON.stringify(args) }).then(async (r) => {
      const body = await r.json().catch(() => ({}));
      if (!r.ok) {
        let msg = 'Something went wrong. Please try again.';
        try { msg = JSON.parse(JSON.parse(body._server_messages)[0]).message || msg; } catch (e) { /* default */ }
        if (r.status === 429) msg = 'Too many attempts from here. Please try again in a while.';
        throw new Error(msg);
      }
      return body.message;
    });
  }

  // ---- the estimate: a port of catalogue_display.estimate (keep in step)
  function estimate(lines, picks, currency, tierQty, frequencies) {
    const byLine = {};
    lines.forEach((l) => { byLine[l.line] = l; });
    const totals = {};
    picks.forEach((p) => {
      const line = byLine[p.line];
      const qty = Number(p.qty) || 0;
      if (!line || qty <= 0 || !line.pack_qty) return;
      const pr = (line.prices || {})[currency] || {};
      const rate = tierQty && qty > tierQty && pr.tier != null ? pr.tier : pr.price;
      if (rate == null) return;
      totals[p.frequency] = (totals[p.frequency] || 0) + qty * Number(line.pack_qty) * Number(rate);
    });
    return frequencies.map((f) => ({ frequency: f.label, period_text: f.period_text || 'once',
      amount: Math.round((totals[f.label] || 0) * 100) / 100 })).filter((e) => e.amount);
  }

  // ---- lookups
  function index() {
    const idx = {};
    state.data.groups.forEach((g) => g.products.forEach((p) => p.lines.forEach((l) => {
      idx[l.line] = { group: g, product: p, line: l };
    })));
    return idx;
  }
  const allLines = () => Object.values(index()).map((x) => x.line);
  const defaultFreq = () => (state.data.frequencies[0] || { label: 'One-off' }).label;
  const picked = () => Object.entries(state.picks).filter(([, p]) => Number(p.qty) > 0);
  const t = () => state.data.text;

  // ---- theme
  let fontsLinked = '';
  function applyTheme(root) {
    const th = state.data.theme;
    ['brand', 'brand_ink', 'paper', 'ink', 'accent', 'accent_ink'].forEach((k) => {
      if (/^#[0-9a-f]{6}$/i.test(th[k] || '')) root.style.setProperty('--' + k.replace('_', '-'), th[k]);
    });
    const f = th.fonts || {};
    root.style.setProperty('--font-head', `'${f.head}', system-ui, sans-serif`);
    root.style.setProperty('--font-text', `'${f.text}', system-ui, sans-serif`);
    root.style.setProperty('--font-note', `'${f.note}', Georgia, serif`);
    document.body.style.background = th.paper;
    if (f.css && fontsLinked !== f.css && safeUrl(f.css)) {
      const old = document.getElementById('cat-fonts');
      if (old) old.remove();
      const link = document.createElement('link');
      link.id = 'cat-fonts'; link.rel = 'stylesheet'; link.href = f.css;
      document.head.appendChild(link);
      fontsLinked = f.css;
    }
  }

  // ---- pieces
  function coverHtml() {
    const d = state.data, th = d.theme, x = t();
    const logo = safeUrl(th.logo) ? `<img class="logo" src="${esc(th.logo)}" alt="${esc(d.company)}">`
      : `<div class="wordmark">${esc(d.company)}</div>`;
    const curs = d.currencies.join(' or ');
    const valid = d.valid_to ? ` · valid ${d.valid_from ? esc(day(d.valid_from)) + ' – ' : 'until '}${esc(day(d.valid_to))}` : '';
    let art = '';
    if (th.cover_mode === 'Image' && safeUrl(th.cover_image)) {
      art = `<div class="cover-img"><img src="${esc(th.cover_image)}" alt=""></div>`;
    } else {
      const imgs = [];
      d.groups.forEach((g) => g.products.forEach((p) => { if (safeUrl(p.image) && !imgs.includes(p.image)) imgs.push(p.image); }));
      // A collage needs pictures or colours; with neither, the headline takes
      // the whole cover rather than sitting next to three empty tiles.
      const swatches = d.groups.map((g) => g.swatch).filter(Boolean);
      if (imgs.length || swatches.length) {
        const tiles = [0, 1, 2].map((i) => (imgs[i]
          ? `<div><img src="${esc(imgs[i])}" alt=""></div>`
          : `<div style="background:${esc(swatches[i] || '')}"></div>`)).join('');
        art = `<div class="collage" aria-hidden="true">${tiles}</div>`;
      }
    }
    return `
      <header class="cover${art ? '' : ' solo'}"><div class="wrap">
        <div class="left">
          ${logo}
          ${x.issue ? `<div class="issue">${esc(x.issue)}</div>` : ''}
          <h1>${esc(x.headline || d.title)}</h1>
          ${x.dek ? `<p class="dek">${esc(x.dek)}</p>` : ''}
          <div class="valid">${esc(d.title)} · prices in ${esc(curs)}${valid}</div>
        </div>
        ${art}
      </div></header>`;
  }

  function mastheadHtml() {
    const d = state.data;
    return `<div class="wrap masthead"><div class="wordmark">${esc(d.company)}</div><h1>${esc(t().headline || d.title)}</h1></div>`;
  }

  function letterHtml() {
    const d = state.data, x = t();
    if (!d.terms) return '';
    return `<section class="wrap letter"><h2>${esc(x.letter_heading)}</h2>
      <div><div class="body">${d.terms}</div>${x.letter_signoff ? `<div class="sig">${esc(x.letter_signoff)}</div>` : ''}</div></section>`;
  }

  function tint(i) {
    const pct = [100, 78, 60, 46, 34, 24][i % 6];
    return `color-mix(in srgb, var(--brand) ${pct}%, var(--paper))`;
  }

  function indexHtml() {
    const d = state.data;
    const tabs = d.sections.tabs && d.groups.length > 1 ? d.groups.map((g, i) => {
      const bg = g.swatch || tint(i);
      const ink = g.swatch_ink || (i < 3 ? 'var(--brand-ink)' : 'var(--ink)');
      const n = g.products.length;
      return `<button type="button" class="tab" data-jump="${i}" style="background:${esc(bg)};color:${esc(ink)}">
        ${esc(g.label)} <small>${n} ${n === 1 ? 'item' : 'items'}</small></button>`;
    }).join('') : '';
    const cur = d.currencies.length > 1 ? `<span class="cur" role="group" aria-label="Currency">${
      d.currencies.map((c) => `<button type="button" data-cur="${esc(c)}" aria-pressed="${c === state.currency}">${esc(c)}</button>`).join('')}</span>` : '';
    if (!tabs && !cur) return '';
    return `<nav class="index" aria-label="Sections"><div class="wrap"><div class="tabs">${tabs}</div>${cur}</div></nav>`;
  }

  function mixesHtml() {
    const d = state.data;
    if (!d.sections.mixes || !d.mixes.length || !d.open) return '';
    const cards = d.mixes.map((m, i) => {
      const boxes = m.items.reduce((s, it) => s + Number(it.boxes || 0), 0);
      return `<div class="mix">
        <div class="stripes">${m.colours.map((c) => `<i style="background:${esc(c)}"></i>`).join('')}</div>
        <b>${esc(m.title)}</b><div class="m">${esc(m.summary)} — ${num(boxes)} ${esc(boxes === 1 ? t().pack : t().packs)}</div>
        <button type="button" data-mix="${i}" class="${state.mixed[i] ? 'done' : ''}">${state.mixed[i] ? 'Added' : 'Add this mix'}</button></div>`;
    }).join('');
    return `<section class="wrap mixes"><h2>Mixes we like this season</h2><div class="mixrow">${cards}</div></section>`;
  }

  function priceCell(l) {
    const p = (l.prices || {})[state.currency] || {};
    if (p.price == null) return '<span class="none">—</span>';
    let h = `<b>${esc(money(p.price))}</b>`;
    if (p.tier != null && state.data.tier_qty) h += ` <span class="tier">${esc(money(p.tier))} ${esc(t().tier.toLowerCase())}</span>`;
    return h;
  }

  function packText(l) {
    const x = t();
    // Priced per pack (unit = pack, e.g. per carton): "1 per carton" says nothing.
    const perPack = l.pack_qty && !(Number(l.pack_qty) === 1 && x.unit === x.pack);
    return [perPack ? `${num(l.pack_qty)} per ${esc(x.pack)}` : '',
      l.bunch && x.bunch ? `${esc(x.bunch.toLowerCase())} ${esc(l.bunch)}` : '',
      l.weight ? `${num(l.weight, 2)} ${esc(x.weight)}` : ''].filter(Boolean).join(' · ');
  }

  function rowHtml(l, open) {
    const d = state.data, x = t();
    const pick = state.picks[l.line] || { qty: '', frequency: defaultFreq() };
    const colSpecs = d.specs.filter((s) => s.display === 'Column');
    const specCells = colSpecs.map((s) => `<td class="xs" data-label="${esc(s.label)}">${
      l.specs && l.specs[s.key] != null ? `<span class="m-only">${esc(s.label)}: </span>${esc(l.specs[s.key])}` : '<span class="none">—</span>'}</td>`).join('');
    const freq = d.frequencies.length > 1 ? `<select data-line="${esc(l.line)}" data-k="frequency" aria-label="How often">${
      d.frequencies.map((f) => `<option ${f.label === pick.frequency ? 'selected' : ''}>${esc(f.label)}</option>`).join('')}</select>` : '';
    const q = open ? `<td class="q"><input type="number" min="0" step="1" inputmode="numeric" placeholder="0"
        aria-label="${esc(x.qty)}" data-line="${esc(l.line)}" data-k="qty" value="${esc(pick.qty)}">${freq}</td>` : '';
    return `<tr class="${Number(pick.qty) > 0 ? 'picked' : ''}">
      <td class="g">${esc(l.grade || '')}${l.box_type ? `<small>${esc(l.box_type)}</small>` : ''}</td>
      <td class="pk">${packText(l)}</td>${specCells}
      <td class="pr">${priceCell(l)}</td>${q}</tr>`;
  }

  function productHtml(g, p) {
    const d = state.data, x = t();
    // No photo yet: a tile in the group's colour with the variety's initial,
    // set large in the headline face — reads as a design choice, not a hole.
    const initial = (p.item_name.replace(/^[^A-Za-z]+/, '')[0] || '•').toUpperCase();
    const photo = safeUrl(p.image) ? `<img src="${esc(p.image)}" alt="" loading="lazy">`
      : `<div class="ph" style="background:${esc(g.swatch || '')};color:${esc(g.swatch_ink || '')}"><span>${esc(initial)}</span></div>`;
    const code = (p.lines.find((l) => l.vbn) || {}).vbn;
    const sw = g.swatch ? `<div class="sw" style="background:${esc(g.swatch)};color:${esc(g.swatch_ink || 'inherit')}">
      <span>${esc(g.label)}</span>${code ? `<span>${esc(code)}</span>` : ''}</div>` : '';
    const more = (p.lines.find((l) => safeUrl(l.info_url) && /^https?:/i.test(l.info_url)) || {}).info_url;
    const colSpecs = d.specs.filter((s) => s.display === 'Column');
    const head = `<thead><tr><th>${esc(x.grade)}</th><th>Pack</th>${colSpecs.map((s) => `<th>${esc(s.label)}</th>`).join('')}
      <th style="text-align:right">${esc(x.price)}</th>${d.open ? `<th style="text-align:right">${esc(x.qty)}</th>` : ''}</tr></thead>`;
    return `<article class="var${sw ? '' : ' nosw'}">
      <div class="photo">${photo}</div>${sw}
      <div class="body">
        <h3>${esc(p.item_name)}</h3>
        ${p.subtitle.length ? `<div class="sub">${p.subtitle.map((s) => `${esc(s.label)}: ${esc(s.value)}`).join(' · ')}</div>` : ''}
        ${p.badges.length ? `<div class="badges">${p.badges.map((b) => `<span class="badge" style="background:${esc(b.background)};color:${esc(b.ink)}">${esc(b.label)}</span>`).join('')}</div>` : ''}
        ${p.note ? `<p class="note">${esc(p.note)}</p>` : ''}
        <table class="specs">${head}<tbody>${p.lines.map((l) => rowHtml(l, d.open)).join('')}</tbody></table>
        ${more ? `<a class="more" href="${esc(more)}" target="_blank" rel="noopener">More about ${esc(p.item_name)}</a>` : ''}
      </div></article>`;
  }

  function groupsHtml() {
    const d = state.data;
    if (!d.groups.length) return '<p class="wrap cat-notice">Nothing in this offer yet.</p>';
    return d.groups.map((g, i) => {
      const lines = g.products.reduce((s, p) => s + p.lines.length, 0);
      return `<section class="wrap">
        <div class="band" id="grp-${i}"><h2>${esc(g.label)}</h2>
          <span>${g.products.length} ${g.products.length === 1 ? 'item' : 'items'} · ${lines} ${lines === 1 ? 'line' : 'lines'}</span></div>
        ${g.products.map((p) => productHtml(g, p)).join('')}</section>`;
    }).join('');
  }

  function barSummary() {
    const d = state.data, x = t();
    const n = picked().length;
    if (!n) return `<span>Enter ${esc(x.packs)} on the lines you want</span>`;
    const boxes = picked().reduce((s, [, p]) => s + Number(p.qty), 0);
    let h = `<b>${n}</b> line${n > 1 ? 's' : ''} · <b>${num(boxes)}</b> ${esc(boxes === 1 ? x.pack : x.packs)}`;
    if (d.sections.estimate) {
      const est = estimate(allLines(), picked().map(([line, p]) => ({ line, qty: p.qty, frequency: p.frequency || defaultFreq() })),
        state.currency, d.tier_qty, d.frequencies);
      if (est.length) h += `<br><span>about ${est.map((e) => `${esc(money(e.amount, 0))} ${esc(e.period_text)}`).join(' + ')}</span>`;
    }
    return h;
  }

  function listHtml() {
    const d = state.data;
    const bar = d.open ? `<div class="bar"><div class="wrap"><div class="sum">${barSummary()}</div>
      <button class="btn" data-act="form" ${picked().length ? '' : 'disabled'}>${esc(t().cta)}</button></div></div>` : '';
    return `${d.sections.cover ? coverHtml() : mastheadHtml()}
      ${d.open ? '' : `<div class="wrap"><div class="closed">${esc(t().closed)}</div></div>`}
      ${d.sections.letter ? letterHtml() : ''}${indexHtml()}${mixesHtml()}${groupsHtml()}${bar}`;
  }

  function formHtml() {
    const d = state.data, x = t();
    const f = state.form || d.prefill || {};
    const idx = index();
    const items = picked().map(([id, pk]) => {
      const { product, line } = idx[id];
      return `<li>${esc(product.item_name)} · ${esc(line.grade || '')} ${esc(line.box_type || '')} — <b>${num(pk.qty)}</b> ${esc(x.packs)} ${esc(pk.frequency || defaultFreq())}</li>`;
    }).join('');
    const field = (k, label, type, wide, req) => `<label class="${wide ? 'wide' : ''}">${label}${req ? ' *' : ''}
      ${type === 'textarea' ? `<textarea data-f="${k}">${esc(f[k] || '')}</textarea>`
        : `<input data-f="${k}" type="${type}" value="${esc(f[k] || '')}" ${req ? 'required' : ''}>`}</label>`;
    return `${mastheadHtml()}
      <div class="wrap"><form class="form" novalidate>
        <h2>${d.personal ? 'Check your details' : 'Your details'}</h2>
        <p class="hint">We'll get back to you about these lines.</p>
        <ul>${items}</ul>
        <div class="fields">
          ${field('name', 'Your name', 'text', false, true)}${field('company', 'Company', 'text')}
          ${field('email', 'Email', 'email', false, !d.personal)}${field('phone', 'Phone / WhatsApp', 'tel')}
          ${field('country', 'Country', 'text')}${field('message', 'Anything we should know?', 'textarea', true)}
        </div>
        <div class="hp" aria-hidden="true"><label>Website<input data-f="website" tabindex="-1" autocomplete="off"></label></div>
        ${state.error ? `<div class="err" role="alert">${esc(state.error)}</div>` : ''}
        <div class="actions">
          <button class="btn" type="submit" ${state.sending || d.preview ? 'disabled' : ''}>${d.preview ? 'Preview — sending is off' : state.sending ? 'Sending…' : esc(x.cta)}</button>
          <button class="btn ghost" type="button" data-act="back">Back to the offer</button>
        </div></form></div>`;
  }

  function render() {
    const d = state.data;
    let root = app.querySelector('.alm');
    if (!root) { app.innerHTML = '<div class="alm"></div>'; root = app.querySelector('.alm'); }
    applyTheme(root);
    if (state.view === 'thanks') {
      root.innerHTML = `<div class="thanks"><h1>Thank you</h1><p>${esc(t().thank_you)}</p>
        <button class="btn ghost" data-act="again">Back to the offer</button></div>`;
    } else {
      root.innerHTML = state.view === 'form' ? formHtml() : listHtml();
    }
    if (d.preview && !document.querySelector('.preview-flag')) {
      document.body.insertAdjacentHTML('beforeend', '<div class="preview-flag">Preview</div>');
    }
  }

  function readForm() {
    const f = {};
    app.querySelectorAll('[data-f]').forEach((el) => { f[el.dataset.f] = el.value; });
    state.form = f;
    return f;
  }

  function refreshBar() {
    const sum = app.querySelector('.bar .sum');
    if (sum) sum.innerHTML = barSummary();
    const btn = app.querySelector('[data-act="form"]');
    if (btn) btn.disabled = !picked().length;
  }

  app.addEventListener('input', (e) => {
    const el = e.target;
    if (!el.dataset.line) return;
    const p = state.picks[el.dataset.line] || (state.picks[el.dataset.line] = { qty: '', frequency: defaultFreq() });
    p[el.dataset.k] = el.value;
    el.closest('tr').classList.toggle('picked', Number(p.qty) > 0);
    refreshBar();
  });

  app.addEventListener('click', (e) => {
    const el = e.target.closest('[data-cur],[data-act],[data-jump],[data-mix]');
    if (!el) return;
    if (el.dataset.cur) { state.currency = el.dataset.cur; render(); return; }
    if (el.dataset.jump != null) {
      const target = document.getElementById(`grp-${el.dataset.jump}`);
      app.querySelectorAll('.tab').forEach((b) => b.setAttribute('aria-current', b === el ? 'true' : 'false'));
      if (target) target.scrollIntoView({ block: 'start' });
      return;
    }
    if (el.dataset.mix != null) {
      const mix = state.data.mixes[Number(el.dataset.mix)];
      mix.items.forEach((it) => {
        const p = state.picks[it.line] || (state.picks[it.line] = { qty: '', frequency: defaultFreq() });
        p.qty = String((Number(p.qty) || 0) + Number(it.boxes || 0));
      });
      state.mixed[el.dataset.mix] = true;
      const y = window.scrollY;
      render();
      window.scrollTo(0, y);
      return;
    }
    const act = el.dataset.act;
    if (act === 'form') { state.view = 'form'; state.error = ''; render(); window.scrollTo(0, 0); }
    if (act === 'back') { readForm(); state.view = 'list'; render(); }
    if (act === 'again') { state.view = 'list'; state.picks = {}; state.mixed = {}; render(); }
  });

  app.addEventListener('submit', (e) => {
    e.preventDefault();
    if (state.data.preview) return;
    const f = readForm();
    if (!f.name || !f.name.trim()) { state.error = 'Please give your name.'; render(); return; }
    if (!state.data.personal && !(f.email || '').includes('@')) { state.error = 'Please give your email address.'; render(); return; }
    state.sending = true; state.error = ''; render();
    const idx = index();
    // item/grade/box ride along so a submission still lands if the catalogue
    // was re-saved while this page was open.
    const lines = picked().map(([line, p]) => ({
      line, qty: Number(p.qty), frequency: p.frequency || defaultFreq(),
      item: idx[line].product.item, grade: idx[line].line.grade, box_type: idx[line].line.box_type }));
    call('catalogue_public.catalogue_submit', {
      token, currency: state.currency, website: f.website || '',
      contact: JSON.stringify({ name: f.name, company: f.company, email: f.email, phone: f.phone,
        country: f.country, message: f.message }),
      lines: JSON.stringify(lines),
    }).then(() => {
      state.sending = false; state.view = 'thanks'; render(); window.scrollTo(0, 0);
    }).catch((err) => { state.sending = false; state.error = err.message; render(); });
  });

  function take(d) {
    state.data = d;
    if (!state.currency || !d.currencies.includes(state.currency)) state.currency = d.currencies[0];
    const allowed = d.frequencies.map((f) => f.label);
    Object.values(state.picks).forEach((p) => { if (!allowed.includes(p.frequency)) p.frequency = allowed[0]; });
    render();
  }

  function unavailable(text) {
    app.innerHTML = `<div class="cat-notice"><h1>This offer isn't available</h1><p>${esc(text)}</p></div>`;
  }

  if (previewName) {
    call('catalogues.crm_catalogue_preview', { name: previewName }).then(take)
      .catch((e) => unavailable(e.message));
    window.addEventListener('message', (e) => {
      if (e.origin !== window.location.origin || !e.data || e.data.type !== 'catalogue-preview') return;
      call('catalogues.crm_catalogue_preview', { name: previewName, template: JSON.stringify(e.data.template) })
        .then(take).catch(() => { /* an invalid draft keeps the last good render */ });
    });
    return;
  }

  // POST, not GET: the view records the open, and Frappe does not commit
  // writes made during a GET request.
  call('catalogue_public.catalogue_view', { token }).then((d) => {
    if (!d.groups.length && !d.open) { unavailable('It may have been withdrawn. Please ask whoever sent you the link.'); return; }
    take(d);
  }).catch((e) => {
    if (window.console) console.error(e); // a render fault, not only a bad link
    unavailable('The link may be mistyped, or the offer withdrawn.');
  });
})();
