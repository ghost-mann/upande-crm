// The buyer's catalogue page (/catalogue/<token>). No framework: one fetch for
// the catalogue, one post for the interest. Layout C: one card per product,
// its grades / box types as rows inside. Everything the buyer typed stays in
// `state`, so switching currency or opening the form never loses an entry.
(function () {
  const app = document.getElementById('cat-app');
  const token = app.dataset.token;
  const csrf = app.dataset.csrf;
  const M = '/api/method/upande_crm.api.catalogue_public.';
  const state = { data: null, currency: null, picks: {}, view: 'list', error: '' };

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = (v, d) => (v == null || v === '' ? '' : Number(v).toLocaleString(undefined, { maximumFractionDigits: d }));
  const money = (v) => (v == null ? null : Number(v).toLocaleString(undefined, {
    style: 'currency', currency: state.currency, minimumFractionDigits: 2, maximumFractionDigits: 4 }));

  function call(method, args, post) {
    const opts = { headers: { Accept: 'application/json' } };
    let url = M + method;
    if (post) {
      opts.method = 'POST';
      opts.headers['Content-Type'] = 'application/json';
      if (csrf) opts.headers['X-Frappe-CSRF-Token'] = csrf;
      opts.body = JSON.stringify(args);
    } else {
      url += '?' + new URLSearchParams(args).toString();
    }
    return fetch(url, opts).then(async (r) => {
      const body = await r.json().catch(() => ({}));
      if (!r.ok) {
        let msg = 'Something went wrong. Please try again.';
        try { msg = JSON.parse(JSON.parse(body._server_messages)[0]).message || msg; } catch (e) { /* keep default */ }
        if (r.status === 429) msg = 'Too many attempts from here. Please try again in a while.';
        throw new Error(msg);
      }
      return body.message;
    });
  }

  function picked() {
    return Object.entries(state.picks).filter(([, p]) => Number(p.qty) > 0);
  }

  function lineIndex() {
    const idx = {};
    (state.data.groups || []).forEach((g) => g.lines.forEach((l) => { idx[l.line] = { group: g, line: l }; }));
    return idx;
  }

  function priceCell(l) {
    const p = (l.prices || {})[state.currency] || {};
    if (p.price == null) return '<span class="cat-noprice">—</span>';
    let h = `<span class="cat-price">${esc(money(p.price))}</span> <span class="cat-box">each</span>`;
    if (p.tier != null && state.data.tier_qty) {
      h += `<div class="cat-tier">${esc(money(p.tier))} above ${esc(state.data.tier_qty)} boxes</div>`;
    }
    return h;
  }

  function rowHtml(l, open) {
    const pick = state.picks[l.line] || { qty: '', frequency: 'One-off' };
    const pack = [l.pack_qty ? `${num(l.pack_qty)} per box` : '', l.bunch ? `bunch ${esc(l.bunch)}` : '',
      l.weight ? `${num(l.weight, 2)} kg` : ''].filter(Boolean).join(' · ');
    const inputs = open ? `
      <div class="cat-inputs">
        <input type="number" min="0" step="1" inputmode="numeric" placeholder="0" aria-label="Boxes"
               data-line="${esc(l.line)}" data-k="qty" value="${esc(pick.qty)}">
        <select data-line="${esc(l.line)}" data-k="frequency" aria-label="How often">
          <option ${pick.frequency === 'One-off' ? 'selected' : ''}>One-off</option>
          <option ${pick.frequency === 'Weekly' ? 'selected' : ''}>Weekly</option>
        </select>
      </div>` : '';
    return `
      <div class="cat-row ${Number(pick.qty) > 0 ? 'picked' : ''}">
        <div><div class="cat-grade">${esc(l.grade || '')} <span class="cat-box">${esc(l.box_type || '')}</span></div>
             <div class="cat-pack">${pack}</div></div>
        <div>${priceCell(l)}</div>
        ${inputs}
      </div>`;
  }

  function listHtml() {
    const d = state.data;
    const groups = d.groups.map((g) => {
      const colors = [...new Set(g.lines.map((l) => l.color).filter(Boolean))];
      const more = (g.lines.find((l) => l.info_url) || {}).info_url;
      const img = g.image ? `<img class="cat-img" src="${esc(g.image)}" alt="" loading="lazy">`
        : '<div class="cat-img" aria-hidden="true"></div>';
      return `
        <section class="cat-group">
          ${img}
          <div class="cat-body">
            <h3 class="cat-name">${esc(g.item_name)}</h3>
            ${colors.length ? `<div class="cat-pills">${colors.map((c) => `<span class="cat-pill">${esc(c)}</span>`).join('')}</div>` : ''}
            ${g.description ? `<p class="cat-desc">${esc(g.description)}</p>` : ''}
            ${more ? `<a class="cat-more" href="${esc(more)}" target="_blank" rel="noopener">More info ↗</a>` : ''}
            <div class="cat-rows">${g.lines.map((l) => rowHtml(l, d.open)).join('')}</div>
          </div>
        </section>`;
    }).join('');
    const n = picked().length;
    const boxes = picked().reduce((s, [, p]) => s + Number(p.qty), 0);
    return `
      ${d.open ? '' : '<div class="cat-closed">This offer has closed, so it can no longer take interest. You can still look through it.</div>'}
      ${d.terms ? `<details class="cat-terms"><summary>Ordering terms</summary><div>${d.terms}</div></details>` : ''}
      ${groups || '<p class="cat-notice">Nothing in this offer yet.</p>'}
      ${d.open ? `<div class="cat-bar"><div class="cat-bar-in">
        <span>${n ? `<b>${n}</b> line${n > 1 ? 's' : ''} · <b>${num(boxes)}</b> box${boxes === 1 ? '' : 'es'}` : 'Enter boxes on the lines you want'}</span>
        <button class="cat-btn" data-act="form" ${n ? '' : 'disabled'}>Send interest</button>
      </div></div>` : ''}`;
  }

  function formHtml() {
    const p = state.data.prefill || {};
    const f = state.form || p;
    const idx = lineIndex();
    const items = picked().map(([id, pk]) => {
      const { group, line } = idx[id];
      return `<li>${esc(group.item_name)} · ${esc(line.grade || '')} ${esc(line.box_type || '')} — <b>${num(pk.qty)}</b> boxes ${esc(pk.frequency)}</li>`;
    }).join('');
    const field = (k, label, type, wide, req) => `
      <label class="${wide ? 'wide' : ''}">${label}${req ? ' *' : ''}
        ${type === 'textarea' ? `<textarea data-f="${k}">${esc(f[k] || '')}</textarea>`
          : `<input data-f="${k}" type="${type}" value="${esc(f[k] || '')}" ${req ? 'required' : ''}>`}
      </label>`;
    return `
      <form class="cat-form" novalidate>
        <h2>${state.data.personal ? 'Check your details' : 'Your details'}</h2>
        <p class="hint">We'll get back to you about these lines.</p>
        <ul class="cat-summary">${items}</ul>
        <div class="cat-fields">
          ${field('name', 'Your name', 'text', false, true)}
          ${field('company', 'Company', 'text')}
          ${field('email', 'Email', 'email', false, !state.data.personal)}
          ${field('phone', 'Phone / WhatsApp', 'tel')}
          ${field('country', 'Country', 'text')}
          ${field('message', 'Anything we should know?', 'textarea', true)}
        </div>
        <div class="cat-hp" aria-hidden="true"><label>Website<input data-f="website" tabindex="-1" autocomplete="off"></label></div>
        ${state.error ? `<div class="cat-err">${esc(state.error)}</div>` : ''}
        <div class="cat-actions">
          <button class="cat-btn" type="submit" ${state.sending ? 'disabled' : ''}>${state.sending ? 'Sending…' : 'Send interest'}</button>
          <button class="cat-btn ghost" type="button" data-act="back">Back to the offer</button>
        </div>
      </form>`;
  }

  function render() {
    const d = state.data;
    if (state.view === 'thanks') {
      app.innerHTML = `<div class="cat-thanks"><h1>Thank you</h1>
        <p>${esc(d.company)} has your interest and will be in touch soon.</p>
        <button class="cat-btn ghost" data-act="again">Back to the offer</button></div>`;
      return;
    }
    const cur = d.currencies.length > 1 ? `<span class="cat-cur" role="group" aria-label="Currency">${
      d.currencies.map((c) => `<button type="button" data-cur="${esc(c)}" aria-pressed="${c === state.currency}">${esc(c)}</button>`).join('')}</span>` : `<span>${esc(state.currency)}</span>`;
    app.innerHTML = `
      <div class="cat-wrap">
        <header class="cat-head">
          ${d.logo ? `<img class="cat-logo" src="${esc(d.logo)}" alt="">` : ''}
          <div><div class="cat-company">${esc(d.company)}</div><h1 class="cat-title">${esc(d.title)}</h1></div>
        </header>
        <div class="cat-meta">${cur}${d.valid_to ? `<span>Valid until ${esc(new Date(d.valid_to).toLocaleDateString())}</span>` : ''}</div>
        ${state.view === 'form' ? formHtml() : listHtml()}
      </div>`;
  }

  function readForm() {
    const f = {};
    app.querySelectorAll('[data-f]').forEach((el) => { f[el.dataset.f] = el.value; });
    state.form = f;
    return f;
  }

  app.addEventListener('input', (e) => {
    const el = e.target;
    if (el.dataset.line) {
      const p = state.picks[el.dataset.line] || (state.picks[el.dataset.line] = { qty: '', frequency: 'One-off' });
      p[el.dataset.k] = el.value;
      const n = picked().length;
      const boxes = picked().reduce((s, [, q]) => s + Number(q.qty), 0);
      el.closest('.cat-row').classList.toggle('picked', Number(p.qty) > 0);
      const bar = app.querySelector('.cat-bar-in span');
      if (bar) bar.innerHTML = n ? `<b>${n}</b> line${n > 1 ? 's' : ''} · <b>${num(boxes)}</b> box${boxes === 1 ? '' : 'es'}` : 'Enter boxes on the lines you want';
      const btn = app.querySelector('[data-act="form"]');
      if (btn) btn.disabled = !n;
    }
  });

  app.addEventListener('click', (e) => {
    const t = e.target.closest('[data-cur],[data-act]');
    if (!t) return;
    if (t.dataset.cur) { state.currency = t.dataset.cur; render(); return; }
    const act = t.dataset.act;
    if (act === 'form') { state.view = 'form'; state.error = ''; render(); window.scrollTo(0, 0); }
    if (act === 'back') { readForm(); state.view = 'list'; render(); }
    if (act === 'again') { state.view = 'list'; state.picks = {}; render(); }
  });

  app.addEventListener('submit', (e) => {
    e.preventDefault();
    const f = readForm();
    if (!f.name || !f.name.trim()) { state.error = 'Please give your name.'; render(); return; }
    if (!state.data.personal && !(f.email || '').includes('@')) { state.error = 'Please give your email address.'; render(); return; }
    state.sending = true; state.error = ''; render();
    const lines = picked().map(([line, p]) => ({ line, qty: Number(p.qty), frequency: p.frequency }));
    call('catalogue_submit', {
      token, currency: state.currency, website: f.website || '',
      contact: JSON.stringify({ name: f.name, company: f.company, email: f.email, phone: f.phone,
        country: f.country, message: f.message }),
      lines: JSON.stringify(lines),
    }, true).then(() => {
      state.sending = false; state.view = 'thanks'; render(); window.scrollTo(0, 0);
    }).catch((err) => { state.sending = false; state.error = err.message; render(); });
  });

  // POST, not GET: the view records the open, and Frappe does not commit
  // writes made during a GET request.
  call('catalogue_view', { token }, true).then((d) => {
    state.data = d;
    state.currency = d.currencies[0];
    if (!d.groups.length && !d.open) {
      app.innerHTML = '<div class="cat-notice"><h1>This offer isn\'t available</h1><p>It may have been withdrawn. Please ask whoever sent you the link.</p></div>';
      return;
    }
    render();
  }).catch(() => {
    app.innerHTML = '<div class="cat-notice"><h1>This offer isn\'t available</h1><p>The link may be mistyped, or the offer withdrawn.</p></div>';
  });
})();
