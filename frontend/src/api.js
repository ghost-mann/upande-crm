// CRM dashboard endpoints — thin wrappers over the shared Frappe client.
// Method names match the source page exactly (POST /api/method/<name>).
import { api } from '@shared/api';

const M = 'upande_crm.api.crm.';
export const getOverview      = (args) => api(M + 'crm_dashboard_overview', args);
export const getLeads         = (args) => api(M + 'crm_dashboard_leads', args);
export const getOpportunities = (args) => api(M + 'crm_dashboard_opportunities', args);
export const getProspects     = (args) => api(M + 'crm_dashboard_prospects', args);
export const getCustomers     = (args) => api(M + 'crm_dashboard_customers', args);
export const getEventsTasks   = (args) => api(M + 'crm_dashboard_events_tasks', args);
export const getActivity      = (args) => api(M + 'crm_dashboard_activity', args);
export const getSales         = (args) => api('upande_crm.api.analytics.crm_sales_analytics', args);

// ---------------------------------------------------------------- activity (writes)
// Event/Task mutations live in a separate backend module (api/activity.py) that
// throws on failure, unlike the dashboard readers which degrade to empty.
const A = 'upande_crm.api.activity.';
export const saveEventApi       = (payload) => api(A + 'crm_event_save', { event: JSON.stringify(payload) });
export const eventStatusApi     = (name, status) => api(A + 'crm_event_status', { name, status });
export const saveTaskApi        = (payload) => api(A + 'crm_task_save', { task: JSON.stringify(payload) });
export const taskStatusApi      = (name, status) => api(A + 'crm_task_status', { name, status });
export const assignApi          = (doctype, name, users, o = {}) => api(A + 'crm_assign', {
  doctype, name, assign_to: JSON.stringify(users),
  description: o.description || '', date: o.date || '', priority: o.priority || 'Medium',
});
export const unassignApi        = (doctype, name, assign_to) => api(A + 'crm_unassign', { doctype, name, assign_to });
export const calendarApi        = (start, end) => api(A + 'crm_calendar', { start, end });
export const assignableUsersApi = () => api(A + 'crm_assignable_users', {});
export const myCalendarsApi     = () => api(A + 'crm_my_calendars', {});

// ---------------------------------------------------------------- whatsapp
// Surface over the frappe_whatsapp app. Reads degrade; sends throw.
const W = 'upande_crm.api.whatsapp.';
export const waConversationsApi = (search = '', limit = 60) => api(W + 'crm_whatsapp_conversations', { search, limit });
export const waThreadApi        = (party, limit = 200) => api(W + 'crm_whatsapp_thread', { party, limit });
export const waSendApi          = (payload) => api(W + 'crm_whatsapp_send', payload);
export const waSendTemplateApi  = (payload) => api(W + 'crm_whatsapp_send_template', payload);
export const waTemplatesApi     = () => api(W + 'crm_whatsapp_templates', {});
export const waMarkReadApi      = (party) => api(W + 'crm_whatsapp_mark_read', { party });
export const getWhatsapp        = (args) => api(W + 'crm_whatsapp_analytics', args);

// ---------------------------------------------------------------- settings
// Organisation-wide settings + the integration health panel. Reads degrade on
// the server; the save throws so the form can show why.
const S = 'upande_crm.api.settings.';
export const orgSettingsApi     = () => api(S + 'crm_settings', {});
export const orgSettingsSaveApi = (patch) => api(S + 'crm_settings_save', { settings: JSON.stringify(patch) });
export const healthApi          = () => api(S + 'crm_integration_status', {});

// Theme: seeds in, derived tokens out. The tokens are applied to :root straight
// away so the running app reskins without a reload; later page loads get the same
// values from the server-rendered <style> block.
export const themeApi           = () => api(S + 'crm_theme', {});
export const themeSaveApi       = (seeds) => api(S + 'crm_theme_save', { seeds: JSON.stringify(seeds) });
export const themePresetApi     = (name) => api(S + 'crm_theme_apply_preset', { name });
export const themeResetApi      = () => api(S + 'crm_theme_reset', {});

// ---------------------------------------------------------------- reports
// ERPNext's own CRM/Selling reports, run through frappe's report runner and
// rendered with CRM components. Runs with the user's own permissions, unlike the
// dashboards — see api/reports.py.
const RP = 'upande_crm.api.reports.';
export const reportsApi      = (args) => api(RP + 'crm_reports', args);
export const reportRunApi    = ({ key, report, filters, date_from, date_to, customer }) =>
  api(RP + 'crm_report_run', {
    key, report, filters: JSON.stringify(filters || {}), date_from, date_to, customer,
  });
export const reportCatalogueApi = () => api(RP + 'crm_report_catalogue', {});

// section key → loader, used by loadAll()
export const SECTION_LOADERS = {
  leads: getLeads,
  opps: getOpportunities,
  prosp: getProspects,
  cust: getCustomers,
  evt: getEventsTasks,
  act: getActivity,
  sales: getSales,
  wa: getWhatsapp,
  overview: getOverview,
};
