import { fmt, fmtDate, fmtDateTime, fmtMoney } from '@shared/utils';

// Frappe report column types -> CRM cell rendering.
//
// Reports return their own column metadata, so this is the one place that has to
// know Frappe's fieldtype vocabulary. Anything unrecognised falls through to
// plain text rather than rendering "[object Object]".

const RIGHT = new Set(['Currency', 'Float', 'Int', 'Percent', 'Duration']);

export function isNumeric(fieldtype) {
  return RIGHT.has(fieldtype);
}

// Long tables are wide; keep obviously-internal columns out of the way.
export function visibleColumns(columns) {
  return (columns || []).filter((c) => c.fieldname && !String(c.fieldname).startsWith('_'));
}

function duration(seconds) {
  const n = Number(seconds);
  if (!Number.isFinite(n) || n <= 0) return '—';
  const d = Math.floor(n / 86400);
  const h = Math.floor((n % 86400) / 3600);
  const m = Math.floor((n % 3600) / 60);
  if (d) return `${d}d ${h}h`;
  if (h) return `${h}h ${m}m`;
  return `${m}m`;
}

export function renderCell(value, column, ccy) {
  if (value === null || value === undefined || value === '') return '—';
  switch (column.fieldtype) {
    case 'Currency':
      // Report currency columns carry `options` naming a currency field, not a
      // code, so the company currency is the honest choice here.
      return fmtMoney(value, ccy);
    case 'Float':
      return Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 });
    case 'Int':
      return fmt(value);
    case 'Percent':
      return `${Number(value).toFixed(1)}%`;
    case 'Duration':
      return duration(value);
    case 'Date':
      return fmtDate(value);
    case 'Datetime':
      return fmtDateTime(value);
    case 'Check':
      return value ? 'Yes' : 'No';
    default:
      return typeof value === 'object' ? JSON.stringify(value) : String(value);
  }
}

// Link columns become desk links, which is the point of surfacing a report here
// rather than in the desk: the rows stay clickable through to the record.
export function linkFor(value, column) {
  if (!value || column.fieldtype !== 'Link' || !column.options) return null;
  return `/app/${String(column.options).toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(value)}`;
}
