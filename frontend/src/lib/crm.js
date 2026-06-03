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
  const palette = ['#9c3848', '#c87a5a', '#c89e3a', '#7a9b6e', '#4a8a8a', '#5e7ba8', '#8a5a7a', '#888a4a'];
  let h = 0;
  for (const ch of String(s || '')) h = ((h << 5) - h + ch.charCodeAt(0)) | 0;
  return palette[Math.abs(h) % palette.length];
}

export function shortUser(u) {
  return u ? String(u).split('@')[0] : '';
}
