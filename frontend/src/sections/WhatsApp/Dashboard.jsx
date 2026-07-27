import { fmt } from '@shared/utils';
import { useStore } from '../../store';
import { KpiRow } from '../../components/Kpi';
import ChartCard from '../../components/ChartCard';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { DoughnutChart, GroupedBarsChart, HBarsChart } from '../../charts/Charts';

export default function Dashboard() {
  const W = useStore((s) => s.data.wa);
  if (!W) return <div className="crm-empty">No WhatsApp data</div>;
  if (!W.available) {
    return <div className="crm-empty">WhatsApp is not configured on this site.</div>;
  }

  const k = W.kpis || {};
  const trend = W.trend || [];
  const top = W.top || [];

  return (
    <>
      <KpiRow items={[
        { lbl: 'Sent', val: fmt(k.sent) },
        { lbl: 'Received', val: fmt(k.received) },
        {
          lbl: 'Failed', val: fmt(k.failed),
          chip: `${k.fail_rate ?? 0}% of sends`, chipTone: k.failed ? 'down' : '',
        },
        { lbl: 'Conversations', val: fmt(k.conversations) },
        { lbl: 'Unread', val: fmt(k.unread), chipTone: k.unread ? 'gold' : '' },
      ]} />

      {k.fail_rate > 20 && (
        <div className="mb-[18px] rounded-xl border border-bad/40 bg-bad-soft px-4 py-3 text-[12.5px] text-ink-2">
          <b>{k.fail_rate}% of outgoing messages failed.</b> The usual cause is sending free
          text outside Meta's 24-hour window — only approved templates are deliverable there.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-[18px] mb-[18px]">
        <Card>
          <CardHeader>
            <div><CardTitle>Message volume</CardTitle><CardSub>Sent against received, per day</CardSub></div>
          </CardHeader>
          <CardContent>
            <div className="h-[280px] relative">
              {trend.length ? (
                <GroupedBarsChart labels={trend.map((r) => r.label)}
                  a={trend.map((r) => r.sent)} b={trend.map((r) => r.received)}
                  aLabel="Sent" bLabel="Received" money={false} />
              ) : <div className="crm-empty">No messages in range</div>}
            </div>
          </CardContent>
        </Card>

        <ChartCard title="Delivery status" sub="Outgoing messages" height="h-[280px]">
          <DoughnutChart items={W.status_mix || []} />
        </ChartCard>
      </div>

      <ChartCard title="Most active contacts" sub="By message count · in range" height="h-[260px]">
        <HBarsChart labels={top.map((r) => r.label)} data={top.map((r) => r.count)} />
      </ChartCard>
    </>
  );
}
