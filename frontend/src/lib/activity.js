// Shared vocabulary for the Event/Task UI. These lists mirror the backend
// allowlists in upande_crm/api/activity.py — keep them in step: the server
// rejects anything off-list with a PermissionError, so an entry added here
// without one there will fail at save time.

export const TASK_REF_DOCTYPES = [
  'Lead', 'Opportunity', 'Prospect', 'Customer',
  'Quotation', 'Contact', 'Sales Order', 'Event',
];

export const PARTICIPANT_DOCTYPES = [
  'Customer', 'Lead', 'Opportunity', 'Prospect', 'Contact',
  'Quotation', 'Sales Order', 'Employee', 'User',
];

// Matches the Event doctype's event_category options.
export const EVENT_CATEGORIES = ['Event', 'Meeting', 'Call', 'Sent/Received Email', 'Other'];
export const EVENT_STATUSES = ['Open', 'Completed', 'Closed', 'Cancelled'];
export const REPEAT_ON = ['Daily', 'Weekly', 'Monthly', 'Quarterly', 'Half Yearly', 'Yearly'];

export const TASK_STATUSES = ['Open', 'Closed', 'Cancelled'];
export const TASK_PRIORITIES = ['High', 'Medium', 'Low'];

// `datetime-local` inputs speak "YYYY-MM-DDTHH:mm"; Frappe stores
// "YYYY-MM-DD HH:mm:ss". Convert at the boundary rather than in each component.
export function toLocalInput(s) {
  return s ? String(s).replace(' ', 'T').slice(0, 16) : '';
}

export function fromLocalInput(s) {
  return s ? `${s.replace('T', ' ')}:00` : null;
}

export function stripHtml(s) {
  return String(s || '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(div|p)>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .trim();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
}

// Text -> the HTML the Text Editor fields expect, with user input escaped.
export function toHtml(s) {
  const t = String(s || '').trim();
  return t ? `<div>${escapeHtml(t).replace(/\n/g, '<br>')}</div>` : '';
}

// A ToDo's `_assign` is a JSON array string; tolerate junk rather than throwing
// inside a render.
export function parseAssign(v) {
  try {
    const a = JSON.parse(v || '[]');
    return Array.isArray(a) ? a.filter(Boolean) : [];
  } catch {
    return [];
  }
}

export function todayISO() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
