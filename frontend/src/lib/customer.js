// Customer page endpoints (upande_crm/api/customer.py). One per tab; each tab
// fetches its own data when it is first opened.
import { api } from '@shared/api';

const C = 'upande_crm.api.customer.';
export const customerHeaderApi = (name, date_from, date_to) => api(C + 'crm_customer_header', { name, date_from, date_to });
export const customerOverviewApi = (name) => api(C + 'crm_customer_overview', { name });
export const customerOrdersApi = (name, args = {}) => api(C + 'crm_customer_orders', { name, ...args });
export const customerPricingApi = (name, args = {}) => api(C + 'crm_customer_pricing', { name, ...args });
export const customerContractsApi = (name) => api(C + 'crm_customer_contracts', { name });
export const customerTimelineApi = (name, args = {}) => api(C + 'crm_customer_timeline', { name, ...args });
export const customerAddNoteApi = (name, content) => api(C + 'crm_customer_add_note', { name, content });
