import { Card, CardHeader, CardTitle, CardSub } from '@/components/ui/card';
import { useStore } from '../store';
import MailList from './MailList';

// Section "Emails" tab — filters the loaded Communications by reference doctype.
export default function EmailsTable({ refType }) {
  const emails = useStore((s) => s.data.evt?.emails || []);
  const search = useStore((s) => s.search);
  const openMessage = useStore((s) => s.openMessage);

  let rows = refType ? emails.filter((e) => (e.reference_doctype || '') === refType) : emails;
  if (search) {
    const q = search.toLowerCase();
    rows = rows.filter((e) =>
      [e.subject, e.sender, e.recipients, e.reference_name].some((v) => String(v || '').toLowerCase().includes(q)));
  }

  return (
    <Card className="mail-card">
      <CardHeader className="px-5 py-4">
        <div>
          <CardTitle className="mail-display text-[19px] font-semibold">Emails</CardTitle>
          <CardSub className="text-[11px] mt-1.5">{rows.length} message{rows.length === 1 ? '' : 's'} · click to open</CardSub>
        </div>
      </CardHeader>
      <div className="px-2 py-1.5">
        <MailList rows={rows.slice(0, 200)} onOpen={(e) => openMessage(e)} />
      </div>
    </Card>
  );
}
