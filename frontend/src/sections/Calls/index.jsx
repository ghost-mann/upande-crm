import { useStore } from '../../store';
import CallsDashboard from './Dashboard';
import CallsTable from './CallsTable';

// Tab router for Calls, on the same `table` key the rest of the app uses.
export default function Calls() {
  const table = useStore((s) => s.table);
  if (table === 'rows') return <CallsTable />;
  if (table === 'mine') return <CallsTable mine />;
  return <CallsDashboard />;
}
