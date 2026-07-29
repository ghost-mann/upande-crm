import { useStore } from '../../store';
import { Button } from '@/components/ui/button';
import Icon from '../../components/Icon';
import CallsDashboard from './Dashboard';
import CallsTable from './CallsTable';

// Tab router for Calls, on the same `table` key the rest of the app uses, with a
// log-a-call action above it.
//
// The action sits at section level rather than only on the dashboard so it is
// reachable from the log and "my calls" views too — the moment you notice a call is
// missing is usually while reading the log.
function Actions() {
  const openCallDialog = useStore((s) => s.openCallDialog);
  const customer = useStore((s) => s.customerFilter);

  // With a customer selected in the header, a call logged from here is about that
  // account: prefill the link rather than making the user pick it again.
  const open = (type) => openCallDialog({
    type,
    ...(customer ? { reference_doctype: 'Customer', reference_name: customer } : {}),
  });

  return (
    <div className="flex items-center gap-2.5 mb-5 flex-wrap">
      <Button
        size="sm" onClick={() => open('Outgoing')}
        className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-4"
      >
        <Icon name="call_made" className="text-[16px]" />Log outgoing call
      </Button>
      <Button size="sm" variant="outline" onClick={() => open('Incoming')} className="rounded-full px-4">
        <Icon name="call_received" className="text-[16px]" />Log incoming call
      </Button>
      {customer ? (
        <span className="text-[12px] text-gold-text flex items-center gap-1.5">
          <Icon name="link" className="text-[14px]" />
          will be linked to {customer}
        </span>
      ) : (
        <span className="text-[12px] text-ink-mute">
          pick a customer in the header to link new calls to it automatically
        </span>
      )}
    </div>
  );
}

export default function Calls() {
  const table = useStore((s) => s.table);
  return (
    <>
      <Actions />
      {table === 'rows' ? <CallsTable />
        : table === 'mine' ? <CallsTable mine />
          : <CallsDashboard />}
    </>
  );
}
