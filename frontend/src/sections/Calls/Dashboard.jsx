import { fmt } from '@shared/utils';
import { useStore } from '../../store';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { KpiCard } from '../../components/Kpi';
import ChartCard from '../../components/ChartCard';
import { DoughnutStat, BarsChart, HBarsChart, AreaTrendChart } from '../../charts/Charts';
import { PAL } from '../../charts/palette';

export default function CallsDashboard() {
  const d = useStore((s) => s.data.calls);
  const status = useStore((s) => s.status);

  if (!d?.kpis) {
    return (
      <div className="p-12 text-center text-ink-mute text-[13px]">
        {status === 'loading' ? 'Loading calls…' : 'No call data'}
      </div>
    );
  }
  if (d.available === false) {
    return (
      <div className="crm-empty py-10">
        Call logging needs Frappe&apos;s Telephony module, which is not installed on this site.
      </div>
    );
  }

  const k = d.kpis;
  const outcome = d.outcome_mix || [];
  const kpis = [
    { lbl: 'Calls', val: fmt(k.total), sub: 'in selected range',
      chip: `${k.connect_rate}% connected`, chipTone: k.connect_rate >= 50 ? 'up' : 'down' },
    { lbl: 'Outgoing', val: fmt(k.outgoing), sub: 'placed' },
    { lbl: 'Incoming', val: fmt(k.incoming), sub: 'received' },
    { lbl: 'Missed', val: fmt(k.missed), sub: 'no answer, busy or failed',
      chipTone: k.missed ? 'down' : '', chip: k.missed ? 'needs a retry' : 'none' },
    { lbl: 'Talk time', val: `${fmt(k.talk_minutes)}`, suffix: 'min', sub: 'total connected' },
    { lbl: 'Avg call', val: `${k.avg_minutes}`, suffix: 'min', sub: 'per connected call' },
  ];

  return (
    <div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(210px,1fr))] gap-[18px] mb-[18px]">
        {kpis.map((x) => <KpiCard key={x.lbl} {...x} />)}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-[18px] mb-[18px]">
        <Card>
          <CardHeader>
            <div><CardTitle>Call volume</CardTitle><CardSub>Calls logged per day in range</CardSub></div>
          </CardHeader>
          <CardContent>
            <div className="h-[280px] relative">
              {d.trend?.length
                ? <AreaTrendChart labels={d.trend.map((r) => r.label)} data={d.trend.map((r) => r.count)} />
                : <div className="crm-empty">No calls in range</div>}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <div><CardTitle>Outcomes</CardTitle><CardSub>How calls ended</CardSub></div>
          </CardHeader>
          <CardContent>
            <div className="h-[220px] relative">
              <DoughnutStat items={outcome} centerLabel="calls" />
            </div>
            <div className="clegend">
              {outcome.map((r, i) => (
                <span key={r.label}><i style={{ background: PAL[i % PAL.length] }} />{r.label} · {fmt(r.count)}</span>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-[18px] mb-[18px]">
        <ChartCard title="Direction" sub="Incoming against outgoing" height="h-[240px]">
          <BarsChart labels={(d.direction_mix || []).map((r) => r.label)}
            data={(d.direction_mix || []).map((r) => r.count)} />
        </ChartCard>
        <ChartCard title="Call types" sub="Dispositions recorded" height="h-[240px]">
          {d.type_mix?.length
            ? <HBarsChart labels={d.type_mix.map((r) => r.label)} data={d.type_mix.map((r) => r.count)} />
            : <div className="crm-empty">No call types recorded yet</div>}
        </ChartCard>
        <ChartCard title="By rep" sub="Who logged them" height="h-[240px]">
          {d.by_user?.length
            ? <HBarsChart labels={d.by_user.map((r) => String(r.label).split('@')[0])}
                data={d.by_user.map((r) => r.count)} />
            : <div className="crm-empty">No calls in range</div>}
        </ChartCard>
      </div>
    </div>
  );
}
