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

// section key → loader, used by loadAll()
export const SECTION_LOADERS = {
  leads: getLeads,
  opps: getOpportunities,
  prosp: getProspects,
  cust: getCustomers,
  evt: getEventsTasks,
  act: getActivity,
  overview: getOverview,
};
