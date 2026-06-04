import { create } from 'zustand';
import { api } from '@shared/api';
import { SECTION_LOADERS } from './api';

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
  leads:    { title: 'Leads',              sub: 'Inbound · qualification · conversion' },
  opps:     { title: 'Opportunities',      sub: 'Pipeline · stages · win rate' },
  prosp:    { title: 'Prospects',          sub: 'Engaged accounts · conversion' },
  cust:     { title: 'Customers',          sub: 'Active accounts · revenue · segmentation' },
  evt:      { title: 'Events, Tasks & Emails', sub: 'Meetings · ToDos · communications' },
  act:      { title: 'Activity Log',       sub: 'CRM triggers · audit trail' },
};

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
  openMsg: null,
  compose: null,   // null = closed; object = open with prefill {to, cc, subject, body, reference, inReplyTo}
  // search
  searchResults: null,

  select(section, table = '') {
    set({ section, table, openMsg: null });
    if (section === 'mail') get().loadMail(table || 'unread');
  },

  setSearch(search) {
    set({ search });
    if (get().section === 'mail') get().loadMail(get().table || 'unread');
  },

  setDateRange(preset, custom) {
    const r = preset === 'custom' && custom
      ? { from: custom.from, to: custom.to, preset: 'custom' }
      : dateRangePreset(preset);
    set({ dateFrom: r.from, dateTo: r.to, datePreset: r.preset });
    get().loadAll();
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

  async loadMail(table) {
    const [folder, tab, clientFilter] = MAIL_MAP[table] || ['inbox', 'all', null];
    set({ mailLoading: true });
    try {
      const data = await api(M + 'crm_mail_data', { folder, tab, search: get().search || '', limit: 100, offset: 0 });
      set({ mailFolder: { ...data, clientFilter }, mailLoading: false });
    } catch {
      set({ mailFolder: { rows: [], counts: {}, clientFilter }, mailLoading: false });
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
