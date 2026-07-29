// Shared vocabulary for the call log. Mirrors the allowlists in
// upande_crm/api/calls.py — the server rejects anything off-list, so an entry
// added here without one there fails at save time.

export const CALL_DIRECTIONS = ['Incoming', 'Outgoing'];

// The live-telephony states (Ringing, In Progress, Queued) are deliberately
// absent: they describe a call in flight, which one being written down
// afterwards never is.
export const CALL_STATUSES = ['Completed', 'No Answer', 'Busy', 'Failed', 'Cancelled'];

export const MISSED_STATUSES = new Set(['No Answer', 'Busy', 'Failed']);

// Seconds (how Frappe stores a Duration) -> a compact human string.
export function fmtDuration(seconds) {
  const n = Number(seconds);
  if (!Number.isFinite(n) || n <= 0) return '—';
  const m = Math.floor(n / 60);
  const s = Math.round(n % 60);
  if (m >= 60) return `${Math.floor(m / 60)}h ${m % 60}m`;
  return m ? `${m}m ${s ? `${s}s` : ''}`.trim() : `${s}s`;
}
