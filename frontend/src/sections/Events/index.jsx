import { useStore } from '../../store';
import EmailsTable from '../../components/EmailsTable';
import Dashboard from './Dashboard';
import EventsTable from './EventsTable';
import TasksTable from './TasksTable';
import Calendar from './Calendar';

// Routes the Events & Tasks section on the active sub-table. Each view is its
// own focused component; this file only decides which one is on screen.
export default function Events() {
  const { data, table } = useStore();
  const E = data.evt;
  if (!E) return <div className="crm-empty">No data</div>;

  if (table === 'calendar') return <Calendar />;
  if (table === 'events' || table === 'mine_events') return <EventsTable mine={table === 'mine_events'} />;
  if (table === 'todos' || table === 'mine_todos') return <TasksTable mine={table === 'mine_todos'} />;
  if (table === 'emails') return <EmailsTable refType={null} />;
  return <Dashboard />;
}
