// Shared formatting/helper utilities for the Upande CRM frontend.
//   import { fmt, fmtMoney, initials } from '@shared/utils';
//
// Superset of what the individual apps used. fmtMoney has two flavours: the
// full 2-decimal form (webshop), and fmtMoneyCompact (k/M abbreviations,
// customer panel) — import whichever the app needs.

export const fmt = (n) =>
  n == null || isNaN(n) ? '—' : Number(n).toLocaleString('en-US');

// Full money: "$1,234.00" / "KES 1,234.00"
export function fmtMoney(n, ccy) {
  if (n == null || isNaN(n)) return '—';
  const v = Number(n);
  const sign = ccy === 'USD' ? '$' : (ccy ? ccy + ' ' : '');
  return sign + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Compact money: "$1.2k" / "$3.4M"
export function fmtMoneyCompact(n, ccy) {
  if (n == null || isNaN(n)) return '—';
  const v = Number(n);
  const sign = ccy === 'USD' ? '$' : (ccy ? ccy + ' ' : '');
  if (Math.abs(v) >= 1e6) return sign + (v / 1e6).toFixed(1) + 'M';
  if (Math.abs(v) >= 1e3) return sign + (v / 1e3).toFixed(1) + 'k';
  return sign + v.toFixed(2);
}

export function fmtDate(s) {
  if (!s) return '—';
  const d = new Date(String(s).replace(' ', 'T'));
  if (isNaN(d)) return String(s).slice(0, 10);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function fmtDateTime(s) {
  if (!s) return '—';
  const d = new Date(String(s).replace(' ', 'T'));
  if (isNaN(d)) return String(s).slice(0, 16);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function fmtRelative(s) {
  if (!s) return '';
  const d = new Date(String(s).replace(' ', 'T'));
  if (isNaN(d)) return s.slice(5, 10);
  const now = new Date();
  if (d.toDateString() === now.toDateString())
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  if (d.getFullYear() === now.getFullYear()) return `${months[d.getMonth()]} ${d.getDate()}`;
  return `${d.getMonth() + 1}/${d.getDate()}/${String(d.getFullYear()).slice(2)}`;
}

export function initials(s) {
  if (!s) return '?';
  const c = String(s).replace(/<[^>]+>/g, '').trim();
  const parts = c.split(/[\s.@_-]+/).filter((x) => x && !x.match(/^\d+$/));
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return (parts[0] || '?')[0].toUpperCase();
}

export function avatarBg(s) {
  const palette = ['#3a5a48', '#c87a5a', '#c89e3a', '#7a9b6e', '#4a8a8a', '#5e7ba8', '#8a5a7a', '#7a1f2b'];
  let h = 0;
  for (const ch of (s || '')) h = ((h << 5) - h + ch.charCodeAt(0)) | 0;
  return palette[Math.abs(h) % palette.length];
}

export function shortUser(u) {
  if (!u) return '';
  return u.split('@')[0];
}

// Map ERPNext statuses → badge class
export function statusClass(s) {
  if (!s) return 'bdg-other';
  const k = String(s).toLowerCase();
  if (k.includes('complet') || k === 'paid' || k === 'closed' || k === 'delivered' || k === 'resolved') return 'bdg-good';
  if (k === 'to deliver' || k === 'to bill' || k.includes('partial')) return 'bdg-info';
  if (k === 'draft' || k === 'submitted' || k === 'open' || k === 'under review') return 'bdg-warn';
  if (k === 'cancelled' || k === 'overdue' || k === 'rejected' || k === 'lost') return 'bdg-bad';
  if (k === 'on hold' || k === 'pending') return 'bdg-warn';
  return 'bdg-accent';
}

export function nameFromAddress(a) {
  if (!a) return '';
  const m = a.match(/^(.+?)\s*<([^>]+)>$/);
  if (m) return m[1].replace(/^["']|["']$/g, '').trim();
  const b = a.split(',')[0].trim();
  return b.includes('@') ? b.split('@')[0] : b;
}
