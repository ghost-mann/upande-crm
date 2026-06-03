import { useStore } from '../store';
import { Card, CardHeader, CardTitle, CardSub } from '@/components/ui/card';
import MailList from '../components/MailList';
import ThreadView from '../components/ThreadView';

const LABELS = {
  unread: 'Unread', inbox: 'All inbox', sent: 'Sent', starred: 'Starred',
  crm_leads: 'Lead emails', crm_opps: 'Opportunity emails',
  crm_customers: 'Customer emails', crm_quotations: 'Quotation emails',
};

function headerCount(table, counts, fallback) {
  const map = {
    unread: 'inbox_unread', inbox: 'inbox', sent: 'sent_ok',
    crm_leads: 'crm_leads', crm_opps: 'crm_opps', crm_customers: 'crm_customers', crm_quotations: 'crm_quotations',
  };
  return counts?.[map[table]] ?? fallback;
}

export default function Mail() {
  const { table, mailFolder, mailLoading, openMsg, starred } = useStore();
  const openMessage = useStore((s) => s.openMessage);
  const t = table || 'unread';

  if (openMsg) return <ThreadView />;
  if (mailLoading) return <div className="crm-empty">Loading mailbox…</div>;

  let rows = mailFolder?.rows || [];
  if (mailFolder?.clientFilter === 'starred') {
    rows = rows.filter((r) => starred.includes(r.name) || String(r._user_tags || '').toLowerCase().includes('starred'));
  }
  const count = headerCount(t, mailFolder?.counts, rows.length);

  return (
    <Card>
      <CardHeader>
        <div><CardTitle>{LABELS[t] || t}</CardTitle><CardSub>Showing {rows.length} of {count} · click to open</CardSub></div>
      </CardHeader>
      {rows.length ? <MailList rows={rows} onOpen={openMessage} /> : <div className="crm-empty">No messages in this folder.</div>}
    </Card>
  );
}
