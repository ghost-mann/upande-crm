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
