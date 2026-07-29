// Shared vocabulary for campaigns. Mirrors upande_crm/api/campaigns.py — the server
// rejects anything off-list.

export const ENROL_TARGETS = ['Lead', 'Contact', 'Email Group'];

// Email Campaign's own status vocabulary.
export const ENROL_STATUSES = ['Scheduled', 'In Progress', 'Completed', 'Unsubscribed'];

export const TARGET_ICON = {
  Lead: 'person_add',
  Contact: 'contacts',
  'Email Group': 'group',
};

// A campaign with no steps can never send: the core controller refuses to enrol
// against it. Worth flagging in the list rather than at enrol time.
export function isSendable(campaign) {
  return (campaign?.steps || 0) > 0;
}

export function durationLabel(days) {
  const n = Number(days);
  if (!Number.isFinite(n) || n <= 0) return 'same day';
  if (n === 1) return 'over 1 day';
  return `over ${n} days`;
}
