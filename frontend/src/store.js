import { create } from 'zustand';
import { api } from '@shared/api';
import {
  SECTION_LOADERS, saveEventApi, eventStatusApi, saveTaskApi, taskStatusApi,
  assignApi, unassignApi, calendarApi,
  waConversationsApi, waThreadApi, waSendApi, waSendTemplateApi, waMarkReadApi,
} from './api';

const SETTINGS_KEY = 'crm_settings';
const M = 'upande_crm.api.crm.';

export const DEFAULT_SETTINGS = {
  autoRefresh: true,
  refreshIntervalSec: 60,
  defaultDateRange: '30d',
  openInNewTab: true,
};

function loadSettings() {
  try {
    return { ...DEFAULT_SETTINGS, ...(JSON.parse(localStorage.getItem(SETTINGS_KEY)) || {}) };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export function dateRangePreset(preset) {
  const now = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const ymd = (d) => `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  const to = ymd(now);
  let from;
  switch (preset) {
    case '7d':  { const d = new Date(now); d.setDate(d.getDate() - 7);  from = ymd(d); break; }
    case '90d': { const d = new Date(now); d.setDate(d.getDate() - 90); from = ymd(d); break; }
    case 'ytd': { from = `${now.getFullYear()}-01-01`; break; }
    case '30d':
    default:    { const d = new Date(now); d.setDate(d.getDate() - 30); from = ymd(d); break; }
  }
  return { from, to, preset };
}

const _settings = loadSettings();
const _initialRange = dateRangePreset(_settings.defaultDateRange === 'custom' ? '30d' : _settings.defaultDateRange);

export const SECTION_META = {
  overview: { title: 'CRM Command Center', sub: 'Pipeline · activity · revenue' },
  mail:     { title: 'Inbox',              sub: 'Email · folders · threads' },
  wa:       { title: 'WhatsApp',            sub: 'Conversations · templates · delivery' },
  leads:    { title: 'Leads',              sub: 'Inbound · qualification · conversion' },
  opps:     { title: 'Opportunities',      sub: 'Pipeline · stages · win rate' },
  prosp:    { title: 'Prospects',          sub: 'Engaged accounts · conversion' },
  cust:     { title: 'Customers',          sub: 'Active accounts · revenue · segmentation' },
  evt:      { title: 'Events, Tasks & Emails', sub: 'Meetings · ToDos · communications' },
  act:      { title: 'Activity Log',       sub: 'CRM triggers · audit trail' },
};

// Inbox page size (rows fetched per request).
const MAIL_PAGE_SIZE = 50;

// mail sub-table → [folder, tab, clientFilter]
const MAIL_MAP = {
  unread: ['inbox', 'unread', null], inbox: ['inbox', 'all', null], sent: ['sent', 'all', null],
  starred: ['inbox', 'all', 'starred'], crm_leads: ['crm_leads', 'all', null],
  crm_opps: ['crm_opps', 'all', null], crm_customers: ['crm_customers', 'all', null],
  crm_quotations: ['crm_quotations', 'all', null],
};

export const useStore = create((set, get) => ({
  data: {},
  section: 'overview',
  table: '',
  search: '',
  settings: _settings,
  dateFrom: _initialRange.from,
  dateTo: _initialRange.to,
  datePreset: _initialRange.preset,
  status: 'idle',
  lastUpdated: null,
  customerFilter: null,
  // mail
  starred: [],
  mailFolder: null,
  mailLoading: false,
  mailOffset: 0,
  openMsg: null,
  compose: null,   // null = closed; object = open with prefill {to, cc, subject, body, reference, inReplyTo}
  // search
  searchResults: null,
  // activity dialogs — null = closed, object = open ({} means create mode)
  eventDialog: null,
  taskDialog: null,
  // calendar owns its own month, independent of the header date-range pill: a
  // pill reading "Last 30 days" must not constrain a calendar paged to March.
  calMonth: null,
  calRows: [],
  calLoading: false,
  // whatsapp
  waConvos: null,
  waThread: null,
  waParty: null,
  waLoading: false,

  select(section, table = '') {
    set({ section, table, openMsg: null });
    if (section === 'mail') get().loadMail(table || 'unread');
    if (section === 'wa' && table !== 'dash') get().loadWaConversations();
  },

  setSearch(search) {
    set({ search });
    if (get().section === 'mail') get().loadMail(get().table || 'unread');
    if (get().section === 'wa') get().loadWaConversations();
  },

  setDateRange(preset, custom) {
    const r = preset === 'custom' && custom
      ? { from: custom.from, to: custom.to, preset: 'custom' }
      : dateRangePreset(preset);
    set({ dateFrom: r.from, dateTo: r.to, datePreset: r.preset });
    get().loadAll();
    if (get().section === 'mail') get().loadMail(get().table || 'unread');
  },

  setCustomerFilter(name) {
    set({ customerFilter: name || null });
    get().loadAll();
  },

  saveSettings(patch) {
    const settings = { ...get().settings, ...patch };
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings)); } catch {}
    set({ settings });
  },

  async loadAll(opts = {}) {
    const silent = !!opts.silent;
    if (!silent) set({ status: 'loading' });
    const args = { date_from: get().dateFrom, date_to: get().dateTo };
    if (get().customerFilter) args.customer = get().customerFilter;
    const keys = Object.keys(SECTION_LOADERS);
    const results = await Promise.allSettled(keys.map((k) => SECTION_LOADERS[k](args)));
    const data = { ...get().data };
    let failed = 0;
    results.forEach((r, i) => {
      if (r.status === 'fulfilled' && r.value && !r.value.error) data[keys[i]] = r.value;
      else failed++;
    });
    if (failed === results.length) { set({ status: 'offline' }); return; }
    set({ data, status: failed ? 'partial' : 'live', lastUpdated: new Date() });
  },

  async loadMail(table, offset = 0) {
    const [folder, tab, clientFilter] = MAIL_MAP[table] || ['inbox', 'all', null];
    set({ mailLoading: true });
    try {
      const data = await api(M + 'crm_mail_data', {
        folder, tab, search: get().search || '', limit: MAIL_PAGE_SIZE, offset,
        date_from: get().dateFrom, date_to: get().dateTo,
      });
      set({ mailFolder: { ...data, clientFilter }, mailLoading: false, mailOffset: offset });
    } catch {
      set({ mailFolder: { rows: [], counts: {}, clientFilter }, mailLoading: false, mailOffset: offset });
    }
  },

  async openMessage(row) {
    set({ openMsg: row });
    try {
      const full = await api('frappe.client.get', { doctype: 'Communication', name: row.name });
      if (full) set({ openMsg: { ...row, ...full } });
    } catch {}
    // Mark received-and-unread messages as read, and reflect it in the list/counts.
    const unread = !!row.unread || (row.sent_or_received === 'Received' && row.status === 'Open' && !row.seen);
    if (unread) {
      try { await api(M + 'crm_mark_read', { name: row.name, seen: 1 }); } catch {}
      const mf = get().mailFolder;
      if (mf?.rows) {
        const rows = mf.rows.map((r) => (r.name === row.name ? { ...r, seen: 1, unread: 0 } : r));
        const counts = { ...(mf.counts || {}) };
        if (typeof counts.inbox_unread === 'number') counts.inbox_unread = Math.max(0, counts.inbox_unread - 1);
        set({ mailFolder: { ...mf, rows, counts } });
      }
    }
  },
  closeMessage() { set({ openMsg: null }); },

  // Toggle read/unread from the list (Gmail-style), updating the row + count locally.
  async markRead(name, seen) {
    const mf = get().mailFolder;
    if (mf?.rows) {
      const rows = mf.rows.map((r) => (r.name === name ? { ...r, seen: seen ? 1 : 0, unread: seen ? 0 : 1 } : r));
      const counts = { ...(mf.counts || {}) };
      if (typeof counts.inbox_unread === 'number') counts.inbox_unread = Math.max(0, counts.inbox_unread + (seen ? -1 : 1));
      set({ mailFolder: { ...mf, rows, counts } });
    }
    try { await api(M + 'crm_mark_read', { name, seen: seen ? 1 : 0 }); } catch {}
  },

  // Bulk-delete Communications (best-effort; skips rows the user can't delete).
  async deleteMessages(names) {
    const list = Array.isArray(names) ? names : [names];
    let ok = 0, failed = 0;
    for (const name of list) {
      try { await api('frappe.client.delete', { doctype: 'Communication', name }); ok += 1; }
      catch { failed += 1; }
    }
    if (get().section === 'mail') await get().loadMail(get().table || 'unread', get().mailOffset);
    return { ok, failed };
  },

  openCompose(ctx = {}) { set({ compose: ctx }); },
  closeCompose() { set({ compose: null }); },

  async toggleStar(name, makeStarred) {
    const cur = new Set(get().starred);
    if (makeStarred) cur.add(name); else cur.delete(name);
    set({ starred: [...cur] });
    try {
      const v = await api('frappe.client.get_value', {
        doctype: 'Communication', filters: JSON.stringify({ name }), fieldname: '_user_tags',
      });
      const tags = new Set(String(v?._user_tags || '').split(',').map((t) => t.trim()).filter(Boolean));
      if (makeStarred) tags.add('Starred'); else tags.delete('Starred');
      await api('frappe.client.set_value', {
        doctype: 'Communication', name, fieldname: '_user_tags', value: [...tags].join(','),
      });
    } catch {
      const roll = new Set(get().starred);
      if (makeStarred) roll.delete(name); else roll.add(name);
      set({ starred: [...roll] });
    }
  },

  async sendEmail(payload) {
    const r = await api(M + 'crm_send_email', payload);
    // Reflect the new message immediately: refresh the open mail folder.
    if (get().section === 'mail') get().loadMail(get().table || 'unread');
    return r;
  },

  // ---------------------------------------------------------------- activity
  openEventDialog(ev = {}) { set({ eventDialog: ev }); },
  closeEventDialog() { set({ eventDialog: null }); },
  openTaskDialog(t = {}) { set({ taskDialog: t }); },
  closeTaskDialog() { set({ taskDialog: null }); },

  // Refetch one section after a write instead of the whole dashboard.
  async reloadSection(key) {
    const loader = SECTION_LOADERS[key];
    if (!loader) return;
    const args = { date_from: get().dateFrom, date_to: get().dateTo };
    if (get().customerFilter) args.customer = get().customerFilter;
    try {
      const v = await loader(args);
      if (v && !v.error) set({ data: { ...get().data, [key]: v }, lastUpdated: new Date() });
    } catch {}
  },

  async saveEvent(payload) {
    const r = await saveEventApi(payload);
    await get().reloadSection('evt');
    if (get().calMonth) await get().loadCalendar(get().calMonth);
    return r;
  },

  async saveTask(payload) {
    const r = await saveTaskApi(payload);
    await get().reloadSection('evt');
    return r;
  },

  // Optimistic: flip the row locally, revert if the server refuses (e.g. the
  // "only the assignee or a manager" rule). Mirrors markRead/toggleStar.
  async setTaskStatus(name, status) {
    const E = get().data.evt;
    const prev = E?.todos?.find((t) => t.name === name)?.status;
    if (E?.todos) {
      set({ data: { ...get().data, evt: {
        ...E, todos: E.todos.map((t) => (t.name === name ? { ...t, status } : t)),
      } } });
    }
    try {
      await taskStatusApi(name, status);
      await get().reloadSection('evt');
    } catch (e) {
      const cur = get().data.evt;
      if (cur?.todos && prev) {
        set({ data: { ...get().data, evt: {
          ...cur, todos: cur.todos.map((t) => (t.name === name ? { ...t, status: prev } : t)),
        } } });
      }
      throw e;
    }
  },

  async setEventStatus(name, status) {
    const E = get().data.evt;
    const prev = E?.events?.find((e) => e.name === name)?.status;
    if (E?.events) {
      set({ data: { ...get().data, evt: {
        ...E, events: E.events.map((e) => (e.name === name ? { ...e, status } : e)),
      } } });
    }
    try {
      await eventStatusApi(name, status);
      await get().reloadSection('evt');
      if (get().calMonth) await get().loadCalendar(get().calMonth);
    } catch (e) {
      const cur = get().data.evt;
      if (cur?.events && prev) {
        set({ data: { ...get().data, evt: {
          ...cur, events: cur.events.map((x) => (x.name === name ? { ...x, status: prev } : x)),
        } } });
      }
      throw e;
    }
  },

  async assign(doctype, name, users, opts) {
    const r = await assignApi(doctype, name, users, opts);
    await get().reloadSection('evt');
    return r;
  },

  async unassign(doctype, name, user) {
    const r = await unassignApi(doctype, name, user);
    await get().reloadSection('evt');
    return r;
  },

  // `monthStart` is any YYYY-MM-DD inside the month to show.
  async loadCalendar(monthStart) {
    const d = new Date(monthStart + 'T00:00:00');
    if (isNaN(d)) return;
    const first = new Date(d.getFullYear(), d.getMonth(), 1);
    const last = new Date(d.getFullYear(), d.getMonth() + 1, 0);
    const p = (n) => String(n).padStart(2, '0');
    const iso = (x) => `${x.getFullYear()}-${p(x.getMonth() + 1)}-${p(x.getDate())}`;
    set({ calLoading: true, calMonth: iso(first) });
    try {
      const rows = await calendarApi(iso(first), iso(last));
      set({ calRows: rows || [], calLoading: false });
    } catch {
      set({ calRows: [], calLoading: false });
    }
  },

  // ---------------------------------------------------------------- whatsapp
  async loadWaConversations() {
    set({ waLoading: true });
    try {
      const d = await waConversationsApi(get().search || '');
      set({ waConvos: d, waLoading: false });
    } catch {
      set({ waConvos: { rows: [], unread_total: 0, available: false }, waLoading: false });
    }
  },

  async openWaThread(party) {
    set({ waParty: party, waThread: null, waLoading: true });
    try {
      const t = await waThreadApi(party);
      set({ waThread: t, waLoading: false });
      // Mirror the desk chat UI: opening a thread marks its inbound messages read.
      if (t?.messages?.some((m) => m.type === 'Incoming' && m.status !== 'marked as read')) {
        try { await waMarkReadApi(party); await get().loadWaConversations(); } catch {}
      }
    } catch {
      set({ waThread: null, waLoading: false });
    }
  },

  closeWaThread() { set({ waParty: null, waThread: null }); },

  // Sends throw on purpose — the composer keeps the user's text and shows why.
  async sendWhatsapp(payload) {
    const r = await waSendApi(payload);
    if (get().waParty) await get().openWaThread(get().waParty);
    await get().loadWaConversations();
    return r;
  },

  async sendWhatsappTemplate(payload) {
    const r = await waSendTemplateApi(payload);
    if (get().waParty) await get().openWaThread(get().waParty);
    await get().loadWaConversations();
    return r;
  },

  async runSearch(q) {
    if (!q || q.length < 2) { set({ searchResults: null }); return; }
    try {
      const r = await api(M + 'crm_search', { query: q });
      set({ searchResults: r?.results || [] });
    } catch {
      set({ searchResults: [] });
    }
  },
}));

let _timer = null;
export function setupAutoRefresh() {
  const { settings, loadAll } = useStore.getState();
  if (_timer) { clearInterval(_timer); _timer = null; }
  if (settings.autoRefresh) {
    const ms = Math.max(15, settings.refreshIntervalSec) * 1000;
    _timer = setInterval(() => loadAll({ silent: true }), ms);
  }
}
