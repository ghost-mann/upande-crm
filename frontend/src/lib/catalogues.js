// Catalogues: price lists shared with buyers by link, and the interest they send
// back (upande_crm/api/catalogues.py, catalogue_import.py).
import { api } from '@shared/api';

const C = 'upande_crm.api.catalogues.';
const json = (v) => JSON.stringify(v);

export const cataloguesApi = () => api(C + 'crm_catalogues', {});
export const catalogueGetApi = (name) => api(C + 'crm_catalogue_get', { name });
export const catalogueSaveApi = (catalogue) => api(C + 'crm_catalogue_save', { catalogue: json(catalogue) });
export const catalogueStatusApi = (name, status) => api(C + 'crm_catalogue_status', { name, status });
export const catalogueDuplicateApi = (name) => api(C + 'crm_catalogue_duplicate', { name });
export const catalogueImportApi = (file_url, currencies) =>
  api('upande_crm.api.catalogue_import.crm_catalogue_import', { file_url, currencies: json(currencies) });
export const shareOptionsApi = (name, party_type, party) => api(C + 'crm_catalogue_share_options', { name, party_type, party });
export const shareApi = (args) => api(C + 'crm_catalogue_share', args);
export const catalogueLinksApi = (name) => api(C + 'crm_catalogue_links', { name });
export const interestsApi = (args = {}) => api(C + 'crm_catalogue_interests', args);
export const interestGetApi = (name) => api(C + 'crm_catalogue_interest_get', { name });
export const interestStatusApi = (name, status) => api(C + 'crm_catalogue_interest_status', { name, status });
export const makeOpportunityApi = (name) => api(C + 'crm_catalogue_make_opportunity', { name });

export const CATALOGUE_TONE = { Draft: 'bdg-other', Live: 'bdg-good', Closed: 'bdg-bad' };
export const INTEREST_TONE = { New: 'bdg-info', Contacted: 'bdg-warn', Converted: 'bdg-good', Dropped: 'bdg-other' };

// Upload a private file through Frappe's standard endpoint; resolves to its file_url.
export async function uploadPrivate(file) {
  const { getCsrfToken } = await import('@shared/api');
  const fd = new FormData();
  fd.append('file', file, file.name);
  fd.append('is_private', '1');
  fd.append('folder', 'Home');
  const res = await fetch('/api/method/upload_file', {
    method: 'POST', body: fd, credentials: 'same-origin',
    headers: { 'X-Frappe-CSRF-Token': getCsrfToken(), Accept: 'application/json' },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || !body.message?.file_url) {
    let msg = 'Upload failed';
    try { msg = JSON.parse(JSON.parse(body._server_messages)[0]).message || msg; } catch { /* default */ }
    throw new Error(msg);
  }
  return body.message.file_url;
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    window.prompt('Copy this link', text);
    return false;
  }
}
