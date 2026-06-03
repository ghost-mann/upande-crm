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
    label: 'Pipeline',
    items: [
      { type: 'group', section: 'leads', icon: 'person_add', label: 'Leads', newDoctype: 'Lead',
        subs: [{ table: '', label: 'Dashboard' }, { table: 'rows', label: 'All Leads' }, { table: 'emails', label: 'Emails' }] },
      { type: 'group', section: 'opps', icon: 'trending_up', label: 'Opportunities', newDoctype: 'Opportunity',
        subs: [{ table: '', label: 'Dashboard' }, { table: 'rows', label: 'All Opportunities' }, { table: 'emails', label: 'Emails' }] },
      { type: 'group', section: 'prosp', icon: 'travel_explore', label: 'Prospects',
        subs: [{ table: '', label: 'Dashboard' }, { table: 'rows', label: 'All Prospects' }, { table: 'emails', label: 'Emails' }] },
      { type: 'group', section: 'cust', icon: 'storefront', label: 'Customers',
        subs: [{ table: '', label: 'Dashboard' }, { table: 'rows', label: 'All Customers' }, { table: 'top', label: 'Top Revenue (30d)' }, { table: 'emails', label: 'Emails' }] },
    ],
  },
  {
    label: 'Activity',
    items: [
      { type: 'group', section: 'evt', icon: 'event', label: 'Events & Tasks',
        subs: [{ table: '', label: 'Dashboard' }, { table: 'events', label: 'All Events' }, { table: 'todos', label: 'ToDos' }, { table: 'emails', label: 'All Emails' }] },
      { type: 'group', section: 'act', icon: 'bolt', label: 'Activity Log',
        subs: [{ table: '', label: 'Dashboard' }, { table: 'rows', label: 'Recent (500)' }] },
    ],
  },
];
