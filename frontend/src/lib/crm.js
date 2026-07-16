// Open a Frappe desk record in a new tab (ported from openFrappe()).
export function openFrappe(doctype, name, newTab = true) {
  if (!doctype || !name) return;
  const url = `/app/${String(doctype).toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(name)}`;
  window.open(url, newTab ? '_blank' : '_self', 'noopener');
}

// status string → .bdg-* class (ported from statusBadge()).
export function badgeClass(s) {
  if (!s) return 'bdg-other';
  const k = String(s).toLowerCase();
  if (k === 'open' || k === 'lead' || k === 'replied') return 'bdg-open';
  if (k === 'converted' || k === 'qualified' || k === 'active' || k === 'high') return 'bdg-good';
  if (k === 'lost' || k.includes('cancel') || k === 'disabled') return 'bdg-bad';
  if (k === 'opportunity' || k === 'quotation' || k === 'in process' || k === 'medium') return 'bdg-warn';
  return 'bdg-other';
}

// avatar background hash (ported from avatarBg()).
export function avatarBg(s) {
  const palette = ['#a87d0d', '#3a3a34', '#228883', '#3f8f4f', '#96650f', '#5a5a52', '#c4302b', '#8a6a10'];
  let h = 0;
  for (const ch of String(s || '')) h = ((h << 5) - h + ch.charCodeAt(0)) | 0;
  return palette[Math.abs(h) % palette.length];
}

export function shortUser(u) {
  return u ? String(u).split('@')[0] : '';
}

// The logged-in user's email, from the Jinja boot block (window.frappe_user).
export function currentUser() {
  if (typeof window === 'undefined') return '';
  return String(window.frappe_user || window.user || '').toLowerCase();
}

// True if `row` belongs to `user` via any of `fields`. Plain link fields match
// on equality; the Frappe `_assign` field is a JSON array string, matched by
// substring. `user` should already be lower-cased.
export function isMine(row, user, fields) {
  if (!user) return false;
  return fields.some((f) => {
    const v = String(row?.[f] || '').toLowerCase();
    if (!v) return false;
    return f === '_assign' ? v.includes(user) : v === user;
  });
}

// Ownership/assignment fields checked per section for the "My …" views.
export const MINE_FIELDS = {
  leads: ['lead_owner', 'owner', '_assign'],
  opps: ['opportunity_owner', 'owner', '_assign'],
  cust: ['account_manager', 'owner', '_assign'],
  prosp: ['owner', '_assign'],
  events: ['owner', '_assign'],
  todos: ['allocated_to', 'owner', '_assign'],
};
