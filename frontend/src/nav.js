// Sidebar navigation model — mirrors the source page's static nav exactly.
export const NAV = [
  {
    label: 'Dashboard',
    items: [{ type: 'item', section: 'overview', icon: 'dashboard', label: 'Overview' }],
  },
  {
    label: 'Mail',
    items: [
      {
        type: 'group', section: 'mail', icon: 'mail', label: 'Inbox', countKey: 'mail_unread',
        subs: [
          { table: 'unread', label: 'Unread', countKey: 'mail_unread' },
          { table: 'inbox', label: 'All inbox', countKey: 'mail_inbox' },
          { table: 'sent', label: 'Sent', countKey: 'mail_sent' },
          { table: 'starred', label: 'Starred' },
          { table: 'crm_leads', label: 'Lead emails' },
          { table: 'crm_opps', label: 'Opportunity emails' },
          { table: 'crm_customers', label: 'Customer emails' },
          { table: 'crm_quotations', label: 'Quotation emails' },
        ],
      },
    ],
  },
  {
    label: 'WhatsApp',
    items: [
      {
        type: 'group', section: 'wa', icon: 'chat', label: 'WhatsApp', countKey: 'wa_unread',
        subs: [
          { table: '', label: 'Conversations' },
          { table: 'dash', label: 'Dashboard' },
        ],
      },
    ],
  },
  {
    label: 'Pipeline',
    items: [
      { type: 'group', section: 'leads', icon: 'person_add', label: 'Leads', newDoctype: 'Lead',
        subs: [{ table: '', label: 'Dashboard' }, { table: 'mine', label: 'My leads', mine: true }, { table: 'rows', label: 'All Leads' }, { table: 'emails', label: 'Emails' }] },
      { type: 'group', section: 'opps', icon: 'trending_up', label: 'Opportunities', newDoctype: 'Opportunity',
        subs: [{ table: '', label: 'Dashboard' }, { table: 'mine', label: 'My opportunities', mine: true }, { table: 'rows', label: 'All Opportunities' }, { table: 'emails', label: 'Emails' }] },
      { type: 'group', section: 'prosp', icon: 'travel_explore', label: 'Prospects',
        subs: [{ table: '', label: 'Dashboard' }, { table: 'mine', label: 'My prospects', mine: true }, { table: 'rows', label: 'All Prospects' }, { table: 'emails', label: 'Emails' }] },
      { type: 'group', section: 'cust', icon: 'storefront', label: 'Customers',
        subs: [{ table: '', label: 'Dashboard' }, { table: 'mine', label: 'My customers', mine: true }, { table: 'rows', label: 'All Customers' }, { table: 'top', label: 'Top Revenue' }, { table: 'emails', label: 'Emails' }] },
    ],
  },
  {
    label: 'Activity',
    items: [
      { type: 'group', section: 'evt', icon: 'event', label: 'Events & Tasks', newDoctype: 'Event',
        subs: [{ table: '', label: 'Dashboard' }, { table: 'calendar', label: 'Calendar' }, { table: 'mine_events', label: 'My events', mine: true }, { table: 'mine_todos', label: 'My tasks', mine: true }, { table: 'events', label: 'All Events' }, { table: 'todos', label: 'CRM Tasks' }, { table: 'emails', label: 'All Emails' }] },
      { type: 'group', section: 'act', icon: 'bolt', label: 'Activity Log',
        subs: [{ table: '', label: 'Dashboard' }, { table: 'rows', label: 'Recent (500)' }] },
    ],
  },
  {
    label: 'Reports',
    items: [
      { type: 'group', section: 'rep', icon: 'lab_profile', label: 'Reports',
        subs: [
          { table: '', label: 'Pipeline' },
          { table: 'leads', label: 'Leads' },
          { table: 'customers', label: 'Customers' },
          { table: 'sales', label: 'Sales' },
          { table: 'all', label: 'All reports' },
        ] },
    ],
  },
  {
    label: 'Workspace',
    items: [
      { type: 'group', section: 'set', icon: 'settings', label: 'Settings',
        subs: [
          { table: '', label: 'General' },
          { table: 'targets', label: 'Targets' },
          { table: 'pipeline', label: 'Pipeline' },
          { table: 'activity', label: 'Events & Tasks' },
          { table: 'wa', label: 'WhatsApp' },
          { table: 'theme', label: 'Theme' },
          { table: 'health', label: 'Integrations' },
        ] },
    ],
  },
];

// The nav an organisation's settings actually allow. Today only WhatsApp is
// switchable; keep new toggles here rather than in the components, so the sidebar
// and the tab strip cannot disagree about what exists.
export function visibleNav(org) {
  const waOff = org && !org.whatsapp_enabled;
  if (!waOff) return NAV;
  return NAV
    .map((grp) => ({ ...grp, items: grp.items.filter((it) => it.section !== 'wa') }))
    .filter((grp) => grp.items.length);
}
