import { useStore } from '../../store';
import Conversations from './Conversations';
import Thread from './Thread';
import Dashboard from './Dashboard';

export default function WhatsApp() {
  const table = useStore((s) => s.table);
  const waParty = useStore((s) => s.waParty);

  if (table === 'dash') return <Dashboard />;
  // A selected conversation takes over the pane, like the mail ThreadView does.
  return waParty ? <Thread /> : <Conversations />;
}
