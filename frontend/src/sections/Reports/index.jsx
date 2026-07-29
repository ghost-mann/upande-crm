import { useStore } from '../../store';
import Group from './Group';
import Catalogue from './Catalogue';

// Tab router for Reports, on the same `table` key the rest of the app uses.
const GROUPS = { '': 'pipeline', leads: 'leads', customers: 'customers', sales: 'sales' };

export default function Reports() {
  const table = useStore((s) => s.table);
  if (table === 'all') return <Catalogue />;
  return <Group group={GROUPS[table] || 'pipeline'} />;
}
