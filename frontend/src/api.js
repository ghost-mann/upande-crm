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

// ---------------------------------------------------------------- campaigns
// A surface over ERPNext's Campaign / Email Campaign drip engine. Sending is the
// daily scheduler's job — nothing here sends on save. See api/campaigns.py.
const CP = 'upande_crm.api.campaigns.';
export const getCampaigns          = (args) => api(CP + 'crm_dashboard_campaigns', args);
export const campaignSaveApi       = (payload) => api(CP + 'crm_campaign_save', { campaign: JSON.stringify(payload) });
export const campaignDetailApi     = (name) => api(CP + 'crm_campaign_detail', { name });
export const campaignEnrolApi      = (p) => api(CP + 'crm_campaign_enrol', {
  campaign: p.campaign, target: p.target, recipients: JSON.stringify(p.recipients || []),
  start_date: p.start_date, sender: p.sender, attribute: p.attribute ?? 1,
});
export const campaignCancelApi     = (name) => api(CP + 'crm_campaign_cancel', { name });
export const campaignRecipientsApi = (target, search = '') => api(CP + 'crm_campaign_recipients', { target, search });
export const emailTemplatesApi     = () => api(CP + 'crm_email_templates', {});
export const emailGroupsApi        = () => api(CP + 'crm_email_groups', {});

// ---------------------------------------------------------------- analytics
// Purpose-built pipeline analytics — its own queries, not a report viewer.
// One endpoint per tab so a tab nobody opened costs nothing.
const AN = 'upande_crm.api.pipeline.crm_analytics_';
export const ANALYTICS_LOADERS = {
  funnel:  (args) => api(AN + 'funnel', args),
  leads:   (args) => api(AN + 'leads', args),
  opps:    (args) => api(AN + 'opportunities', args),
  revenue: (args) => api(AN + 'revenue', args),
};

// ---------------------------------------------------------------- calls
// Logged into Frappe's core Call Log (Telephony). Writes throw; the dashboard
// read degrades — see api/calls.py.
const CL = 'upande_crm.api.calls.';
export const getCalls        = (args) => api(CL + 'crm_dashboard_calls', args);
export const saveCallApi     = (payload) => api(CL + 'crm_call_save', { call: JSON.stringify(payload) });
export const deleteCallApi   = (name) => api(CL + 'crm_call_delete', { name });
export const callTypesApi    = () => api(CL + 'crm_call_types', {});
export const callTypeAddApi  = (label) => api(CL + 'crm_call_type_add', { label });

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

// ---------------------------------------------------------------- command centre
// The Overview's own endpoints. Split so the KPI row and the day's work are not
// held behind the per-item aggregation, and so the mover drill costs nothing
// until it is opened — see api/command.py.
const CM = 'upande_crm.api.command.';
export const getCommand     = (args) => api(CM + 'crm_command_center', args);
export const getTrack       = (args) => api(CM + 'crm_sales_track_record', args);
export const moverDetailApi = ({ kind, key, date_from, date_to, customer }) =>
  api(CM + 'crm_mover_detail', { kind, key, date_from, date_to, customer });

// ---------------------------------------------------------------- demand
// What clients are asking for, from open opportunity and quotation lines — the
// forward counterpart to command.py's top sellers, which counts what shipped.
export const getDemand = (args) => api('upande_crm.api.demand.crm_demand', args);

// ---------------------------------------------------------------- leads (writes)
// Lead capture and conversion. A write layer: these throw so the dialogs keep
// what was typed and show why. Conversion delegates to ERPNext's own mappers —
// see api/leads.py.
const LD = 'upande_crm.api.leads.';
export const leadSaveApi        = (payload) => api(LD + 'crm_lead_save', { lead: JSON.stringify(payload) });
export const leadToProspectApi  = (lead, o = {}) => api(LD + 'crm_lead_to_prospect', {
  lead, prospect: o.prospect || '', company_name: o.company_name || '',
});
export const leadToOppApi       = (lead, payload) => api(LD + 'crm_lead_to_opportunity', {
  lead, opportunity: JSON.stringify(payload || {}),
});
export const prospectToOppApi   = (prospect, payload) => api(LD + 'crm_prospect_to_opportunity', {
  prospect, opportunity: JSON.stringify(payload || {}),
});
export const leadOptionsApi     = () => api(LD + 'crm_lead_form_options', {});
export const flowerSearchApi    = (query = '', limit = 20) => api(LD + 'crm_flower_search', { query, limit });

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
  calls: getCalls,
  campaigns: getCampaigns,
  overview: getOverview,
  command: getCommand,
  track: getTrack,
  demand: getDemand,
};
