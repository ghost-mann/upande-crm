import { fmt } from '@shared/utils';
import { useStore } from '../../store';
import { KpiRow } from '../../components/Kpi';
import ChartCard from '../../components/ChartCard';
import Icon from '../../components/Icon';
import { Button } from '@/components/ui/button';
import { BarsChart, DoughnutChart } from '../../charts/Charts';
import { todayISO } from '@/lib/activity';

export default function Dashboard() {
  const E = useStore((s) => s.data.evt);
  const openEventDialog = useStore((s) => s.openEventDialog);
  const openTaskDialog = useStore((s) => s.openTaskDialog);
  const k = E?.kpis || {};

  return (
    <>
      <div className="flex items-center gap-2.5 mb-5">
        <Button size="sm" onClick={() => openEventDialog({ prefillStart: `${todayISO()} 09:00:00` })}
          className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-4">
          <Icon name="event" className="text-[16px]" />New event
        </Button>
        <Button size="sm" variant="outline" onClick={() => openTaskDialog({})} className="rounded-full px-4">
          <Icon name="add_task" className="text-[16px]" />New task
        </Button>
      </div>

      <KpiRow items={[
        { lbl: 'Events', val: fmt(k.events_total) },
        { lbl: 'Open Events', val: fmt(k.events_open) },
        { lbl: 'Open Tasks', val: fmt(k.tasks_open) },
        { lbl: 'High Priority', val: fmt(k.tasks_high) },
        { lbl: 'Sent', val: fmt(k.emails_sent || 0) },
        { lbl: 'Received', val: fmt(k.emails_recv || 0) },
      ]} />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <ChartCard title="Event Categories" height="h-[260px]">
          <BarsChart labels={(E?.event_categories || []).map((r) => r.label)}
            data={(E?.event_categories || []).map((r) => r.count)} />
        </ChartCard>
        <ChartCard title="Task Priorities" sub="CRM tasks only" height="h-[260px]">
          <DoughnutChart items={E?.task_priorities} />
        </ChartCard>
        <ChartCard title="Emails by Reference" height="h-[260px]">
          <DoughnutChart items={E?.email_by_ref || []} />
        </ChartCard>
      </div>
    </>
  );
}
