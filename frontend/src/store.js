import { create } from 'zustand';
import { api } from '@shared/api';
import {
  SECTION_LOADERS, saveEventApi, eventStatusApi, saveTaskApi, taskStatusApi,
  assignApi, unassignApi, calendarApi,
  waConversationsApi, waThreadApi, waSendApi, waSendTemplateApi, waMarkReadApi,
  orgSettingsApi, orgSettingsSaveApi, healthApi,
  themeApi, themeSaveApi, themePresetApi, themeResetApi,
  reportsApi, reportCatalogueApi,
  saveCallApi, deleteCallApi,
  ANALYTICS_LOADERS,
} from './api';

const SETTINGS_KEY = 'crm_settings';
const M = 'upande_crm.api.crm.';

// Per-device view preferences. These are the last layer of a three-deep merge:
// DEFAULT_SETTINGS <- the organisation's defaults <- what this user chose.
// So an org changing its default range moves everyone who never overrode it, and
// leaves everyone who did alone.
export const DEFAULT_SETTINGS = {
  autoRefresh: true,
  refreshIntervalSec: 60,
  defaultDateRange: '30d',
  openInNewTab: true,
};

// Mirrors upande_crm.api.settings.DEFAULTS — used until the server answers, and
// permanently if it never does.
export const DEFAULT_ORG = {
  revenue_target_monthly: 0,
  revenue_target_annual: 0,
  target_basis: 'Billed',
  default_date_range: '30d',
  top_n: 8,
  auto_refresh: 1,
  refresh_interval_sec: 60,
  lead_open_statuses: 'Lead, Open, Replied, Interested',
  opportunity_open_statuses: 'Open, Quotation, Replied',
  default_task_priority: 'Medium',
  default_task_due_days: 3,
  default_event_category: 'Meeting',
  default_event_duration_mins: 60,
  whatsapp_enabled: 1,
  default_whatsapp_template: '',
  whatsapp_fail_rate_alert: 20,
};

// Only these org fields have a per-device counterpart.
function orgPrefLayer(org) {
  if (!org) return {};
  return {
    autoRefresh: !!org.auto_refresh,
    refreshIntervalSec: Number(org.refresh_interval_sec) || DEFAULT_SETTINGS.refreshIntervalSec,
    defaultDateRange: org.default_date_range || DEFAULT_SETTINGS.defaultDateRange,
  };
}

function storedSettings() {
  try {
    return JSON.parse(localStorage.getItem(SETTINGS_KEY)) || {};
  } catch {
    return {};
  }
}

function loadSettings(org) {
  return { ...DEFAULT_SETTINGS, ...orgPrefLayer(org), ...storedSettings() };
}

// The shared range vocabulary. Analytics needs wider windows than the dashboards
// — a funnel over 30 days on a pipeline this size is single digits — so the longer
// presets live here rather than only in that section.
export const RANGE_PRESETS = [
  ['7d', 'Last 7 days'],
  ['30d', 'Last 30 days'],
  ['60d', 'Last 60 days'],
  ['90d', 'Last 90 days'],
  ['6m', 'Last 6 months'],
  ['ytd', 'Year to date'],
  ['1y', 'Last 12 months'],
  ['all', 'All time'],
];

// The earliest date 'All time' reaches back to. A fixed floor rather than a query
// for the oldest record: one less round-trip, and no section behaves differently
// because its own oldest row happens to be later.
const EPOCH = '2000-01-01';

export function dateRangePreset(preset) {
  const now = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const ymd = (d) => `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  const to = ymd(now);
  const back = (days) => { const d = new Date(now); d.setDate(d.getDate() - days); return ymd(d); };
  const backMonths = (m) => { const d = new Date(now); d.setMonth(d.getMonth() - m); return ymd(d); };
  let from;
  switch (preset) {
    case '7d':  from = back(7); break;
    case '60d': from = back(60); break;
    case '90d': from = back(90); break;
    case '6m':  from = backMonths(6); break;
    case 'ytd': from = `${now.getFullYear()}-01-01`; break;
    case '1y':  from = backMonths(12); break;
    case 'all': from = EPOCH; break;
    case '30d':
    default:    from = back(30); break;
  }
  return { from, to, preset };
}

const _settings = loadSettings(null);
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
  calls:    { title: 'Calls',              sub: 'Incoming · outgoing · outcomes' },
  anl:      { title: 'Sales Analytics',    sub: 'Funnel · leads · opportunities · revenue' },
  act:      { title: 'Activity Log',       sub: 'CRM triggers · audit trail' },
  rep:      { title: 'Reports',            sub: "ERPNext's CRM and sales reports" },
  set:      { title: 'CRM Settings',       sub: 'Targets · defaults · integrations' },
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
  // org settings (server) + integration health
  org: { ...DEFAULT_ORG },
  orgMeta: { can_edit: false, installed: false, currency: 'KES', options: {} },
  orgLoaded: false,
  health: null,
  healthLoading: false,
  // theme: {seeds, tokens, presets, applied, can_edit} — loaded by the Theme tab.
  theme: null,
  // reports registry + catalogue, both loaded lazily by the Reports section.
  reports: null,
  reportCatalogue: null,
  // call dialog — null = closed, object = open ({} means log-a-new-call mode)
  callDialog: null,
  // analytics, one payload per tab, loaded on demand
  analytics: {},
  analyticsLoading: {},

  select(section, table = '') {
    set({ section, table, openMsg: null });
    if (section === 'mail') get().loadMail(table || 'unread');
    if (section === 'wa' && table !== 'dash') get().loadWaConversations();
    // The Integrations tab fetches its own health on mount — doing it here too
    // would fire two requests for one navigation.
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

  // Per-device preferences. Only the keys the user actually touched are stored,
  // so the org layer keeps applying to everything else.
  saveSettings(patch) {
    const stored = { ...storedSettings(), ...patch };
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(stored)); } catch {}
    set({ settings: { ...DEFAULT_SETTINGS, ...orgPrefLayer(get().org), ...stored } });
  },

  // Drop a per-device override and fall back to the organisation's value.
  resetSetting(key) {
    const stored = storedSettings();
    delete stored[key];
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(stored)); } catch {}
    set({ settings: { ...DEFAULT_SETTINGS, ...orgPrefLayer(get().org), ...stored } });
  },

  // ---------------------------------------------------------------- org settings
  // Awaited before the first loadAll(): org defaults decide the opening date
  // range, and resolving them afterwards would mean loading every section twice.
  async loadOrg() {
    let payload = null;
    try { payload = await orgSettingsApi(); } catch {}
    const org = { ...DEFAULT_ORG, ...(payload?.settings || {}) };
    const stored = storedSettings();
    const settings = { ...DEFAULT_SETTINGS, ...orgPrefLayer(org), ...stored };
    const patch = {
      org,
      orgLoaded: true,
      settings,
      orgMeta: {
        can_edit: !!payload?.can_edit,
        installed: !!payload?.installed,
        currency: payload?.currency || 'KES',
        options: payload?.options || {},
      },
    };
    // Re-resolve the header range against the org default, unless the user has
    // pinned one on this device or already moved the picker.
    if (!stored.defaultDateRange && settings.defaultDateRange !== get().datePreset) {
      const r = dateRangePreset(settings.defaultDateRange);
      Object.assign(patch, { dateFrom: r.from, dateTo: r.to, datePreset: r.preset });
    }
    set(patch);
    return org;
  },

  // Throws: the settings form keeps the user's input and shows why.
  async saveOrg(patch) {
    const r = await orgSettingsSaveApi(patch);
    const org = { ...DEFAULT_ORG, ...(r?.settings || {}) };
    set({ org, settings: { ...DEFAULT_SETTINGS, ...orgPrefLayer(org), ...storedSettings() } });
    // Several settings change what the dashboards count, so re-read them.
    get().loadAll({ silent: true });
    if (get().health) get().loadHealth();
    return org;
  },

  // ---------------------------------------------------------------- analytics
  async loadAnalytics(key) {
    const loader = ANALYTICS_LOADERS[key];
    if (!loader) return;
    set({ analyticsLoading: { ...get().analyticsLoading, [key]: true } });
    const args = { date_from: get().dateFrom, date_to: get().dateTo };
    if (get().customerFilter) args.customer = get().customerFilter;
    try {
      const d = await loader(args);
      set({ analytics: { ...get().analytics, [key]: d } });
    } catch {
      set({ analytics: { ...get().analytics, [key]: { error: true } } });
    } finally {
      set({ analyticsLoading: { ...get().analyticsLoading, [key]: false } });
    }
  },

  // ---------------------------------------------------------------- calls
  openCallDialog(call = {}) { set({ callDialog: call }); },
  closeCallDialog() { set({ callDialog: null }); },

  // Throws so the dialog keeps what was typed and shows why.
  async saveCall(payload) {
    const r = await saveCallApi(payload);
    await get().reloadSection('calls');
    // A follow-up task lands in Events & Tasks, so that section is now stale.
    if (r?.follow_up) await get().reloadSection('evt');
    return r;
  },

  async deleteCall(name) {
    const r = await deleteCallApi(name);
    await get().reloadSection('calls');
    return r;
  },

  // ---------------------------------------------------------------- reports
  async loadReports() {
    try {
      const d = await reportsApi({ date_from: get().dateFrom, date_to: get().dateTo });
      set({ reports: d });
    } catch {
      set({ reports: { groups: [], reports: [], error: true } });
    }
  },

  async loadReportCatalogue() {
    try {
      set({ reportCatalogue: await reportCatalogueApi() });
    } catch {
      set({ reportCatalogue: { reports: [], error: true } });
    }
  },

  // ---------------------------------------------------------------- theme
  // Tokens are written onto the document element, which is enough to reskin the
  // whole app: every Tailwind colour here resolves a CSS variable at runtime.
  applyTokens(tokens) {
    if (!tokens || typeof document === 'undefined') return;
    const root = document.documentElement;
    Object.entries(tokens).forEach(([name, value]) => {
      root.style.setProperty(`--${name}`, String(value));
    });
  },

  async loadTheme() {
    try {
      const t = await themeApi();
      set({ theme: t });
      return t;
    } catch {
      set({ theme: { seeds: {}, tokens: {}, presets: [], applied: '', error: true } });
      return null;
    }
  },

  // Throws so the Theme tab can show which colour the server refused.
  async saveTheme(seeds) {
    const t = await themeSaveApi(seeds);
    set({ theme: t });
    get().applyTokens(t?.tokens);
    return t;
  },

  async applyThemePreset(name) {
    const t = await themePresetApi(name);
    set({ theme: t });
    get().applyTokens(t?.tokens);
    return t;
  },

  async resetTheme() {
    const t = await themeResetApi();
    set({ theme: t });
    get().applyTokens(t?.tokens);
    return t;
  },

  async loadHealth() {
    if (get().healthLoading) return;
    set({ healthLoading: true });
    try {
      const h = await healthApi();
      set({ health: h, healthLoading: false });
    } catch {
      set({ health: { checks: [], error: true }, healthLoading: false });
    }
  },

  async loadAll(opts = {}) {
    const silent = !!opts.silent;
    if (!silent) set({ status: 'loading' });
    const args = { date_from: get().dateFrom, date_to: get().dateTo };
    if (get().customerFilter) args.customer = get().customerFilter;
    // A disabled WhatsApp section should not cost a query on every refresh.
    const keys = Object.keys(SECTION_LOADERS)
      .filter((k) => k !== 'wa' || !!get().org?.whatsapp_enabled);
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
