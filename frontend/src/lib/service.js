// Claims, quotations, visits and the pipeline board (upande_crm/api/{claims,
// quotations,visits,board}.py). Each section fetches its own data on mount.
import { api } from '@shared/api';

const A = 'upande_crm.api.';
const json = (v) => JSON.stringify(v);

export const claimsDashboardApi = (args) => api(A + 'claims.crm_dashboard_claims', args);
export const claimSaveApi = (claim) => api(A + 'claims.crm_claim_save', { claim: json(claim) });
export const claimReferencesApi = (customer, kind) => api(A + 'claims.crm_claim_references', { customer, kind });
export const customerClaimsApi = (name) => api(A + 'claims.crm_customer_claims', { name });

export const quotationsDashboardApi = (args) => api(A + 'quotations.crm_dashboard_quotations', args);
export const customerQuotationsApi = (name) => api(A + 'quotations.crm_customer_quotations', { name });

export const visitsDashboardApi = (args) => api(A + 'visits.crm_dashboard_visits', args);
export const visitSaveApi = (visit) => api(A + 'visits.crm_visit_save', { visit: json(visit) });
export const customerVisitsApi = (name) => api(A + 'visits.crm_customer_visits', { name });

export const boardApi = (args) => api(A + 'board.crm_pipeline_board', args);
export const setStageApi = (name, stage) => api(A + 'board.crm_opportunity_set_stage', { name, stage });
export const qualifyLeadApi = (name, status) => api(A + 'board.crm_lead_qualify', { name, status });

export const CLAIM_STATUSES = ['Open', 'Under Review', 'Resolved', 'Rejected'];
export const VISIT_STATUSES = ['Planned', 'Completed', 'Cancelled'];
export const CLAIM_TONE = { Open: 'bdg-warn', 'Under Review': 'bdg-info', Resolved: 'bdg-good', Rejected: 'bdg-bad' };
export const VISIT_TONE = { Planned: 'bdg-info', Completed: 'bdg-good', Cancelled: 'bdg-other' };
