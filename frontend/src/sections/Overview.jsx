import { useStore } from '../store';
import { fmt, fmtMoney } from '@shared/utils';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { DoughnutChart, BarsChart, HBarsChart, SalesOrdersChart } from '../charts/Charts';
import { FUNNEL_COLORS } from '../charts/palette';

function KpiCard({ lbl, val, sub }) {
  return (
    <div className="rounded-md border border-line bg-surface px-[11px] py-2.5 relative overflow-hidden cursor-pointer hover:border-line-2 transition-colors">
      <div className="font-mono text-[8.5px] text-ink-3 uppercase tracking-[0.1em] font-semibold">{lbl}</div>
      <div className="font-mono text-[18px] font-semibold text-ink -tracking-[0.02em] mt-1 leading-[1.15]">{val}</div>
      <div className="font-mono text-[9.5px] text-ink-3 mt-0.5">{sub}</div>
    </div>
  );
}

function ChartCard({ title, sub, height = 'h-[220px]', children }) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{title}</CardTitle>
          {sub && <CardSub>{sub}</CardSub>}
        </div>
      </CardHeader>
      <CardContent>
        <div className={`relative ${height}`}>{children}</div>
      </CardContent>
    </Card>
  );
}

function Funnel({ rows }) {
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <div className="flex flex-col gap-1.5 py-1">
      {rows.map((f, i) => {
        const pct = (f.count / max) * 100;
        return (
          <div key={f.label} className="flex items-center gap-2.5">
            <div className="w-[100px] font-mono text-[10px] text-ink-2 uppercase">{f.label}</div>
            <div className="flex-1 h-[22px] bg-surface-3 rounded-[3px] relative overflow-hidden">
              <div
                className="absolute left-0 top-0 bottom-0 rounded-[3px] flex items-center px-2 text-white font-mono text-[10px] font-semibold"
                style={{ width: `${pct}%`, background: FUNNEL_COLORS[i % FUNNEL_COLORS.length] }}
              >
                {pct > 14 ? f.count : ''}
              </div>
            </div>
            <div className="w-10 text-right font-mono text-[10.5px] font-semibold">{fmt(f.count)}</div>
          </div>
        );
      })}
    </div>
  );
}

export default function Overview() {
  const { data, status } = useStore();
  const OV = data.overview;
  const C = data.cust;

  if (!OV?.kpis) {
    return (
      <div className="p-10 text-center text-ink-3 font-mono text-[11px]">
        {status === 'loading' ? 'Loading' : status === 'offline' ? 'Failed to load CRM data' : 'No overview data'}
      </div>
    );
  }

  const k = OV.kpis;
  const kpis = [
    { lbl: 'Leads', val: fmt(k.leads?.total), sub: `${fmt(k.leads?.open)} open · ${k.leads?.conv_rate}% conv` },
    { lbl: 'Opportunities', val: fmt(k.opps?.total), sub: `${fmt(k.opps?.open)} open · ${fmt(k.opps?.won)} won` },
    { lbl: 'Prospects', val: fmt(k.prosp?.total), sub: `${fmt(k.prosp?.territories)} territories` },
    { lbl: 'Customers', val: fmt(k.cust?.active), sub: `${fmt(k.cust?.companies)} companies` },
    { lbl: 'Revenue 30d', val: `$${fmtMoney(k.revenue_30d?.usd)}`, sub: `${fmt(k.revenue_30d?.orders)} orders` },
    { lbl: 'Open Tasks', val: fmt(k.tasks?.open), sub: `${fmt(k.tasks?.high)} high priority` },
  ];

  const soTrend = C?.sales_order_trend;
  const totR = soTrend?.reduce((s, r) => s + (r.revenue || 0), 0) || 0;
  const totC = soTrend?.reduce((s, r) => s + (r.count || 0), 0) || 0;

  return (
    <div>
      <div className="grid grid-cols-6 gap-2 mb-3.5">
        {kpis.map((x) => <KpiCard key={x.lbl} {...x} />)}
      </div>

      <div className="grid grid-cols-[2fr_1fr] gap-2.5 mb-2.5">
        <Card>
          <CardHeader><div><CardTitle>Sales Funnel</CardTitle><CardSub>Counts at each stage</CardSub></div></CardHeader>
          <CardContent>{OV.funnel?.length ? <Funnel rows={OV.funnel} /> : <div className="text-ink-3 font-mono text-[11px] py-6 text-center">No data</div>}</CardContent>
        </Card>
        <ChartCard title="Lead Status" sub="Distribution" height="h-[160px]">
          <DoughnutChart items={OV.lead_status} />
        </ChartCard>
      </div>

      <div className="grid grid-cols-2 gap-2.5 mb-2.5">
        <ChartCard title="Lead Trend" sub="Last 12 months">
          <BarsChart labels={(OV.lead_trend || []).map((r) => r.month.slice(2))} data={(OV.lead_trend || []).map((r) => r.count)} />
        </ChartCard>
        <ChartCard title="Sales Orders Trend" sub="Last 6 months">
          <BarsChart labels={(OV.so_trend || []).map((r) => r.month.slice(2))} data={(OV.so_trend || []).map((r) => r.count)} />
        </ChartCard>
      </div>

      <div className="grid grid-cols-3 gap-2.5 mb-2.5">
        <ChartCard title="Top Sources" height="h-[160px]"><DoughnutChart items={OV.top_sources} /></ChartCard>
        <ChartCard title="Top Territories" height="h-[160px]">
          <HBarsChart labels={(OV.top_territories || []).map((r) => r.label)} data={(OV.top_territories || []).map((r) => r.count)} />
        </ChartCard>
        <ChartCard title="Sales Stages" height="h-[160px]">
          <BarsChart labels={(OV.sales_stages || []).map((r) => r.label)} data={(OV.sales_stages || []).map((r) => r.count)} />
        </ChartCard>
      </div>

      {soTrend?.length > 0 && (
        <ChartCard title="Sales Orders (Daily)" sub={`${fmt(totC)} orders · $${fmtMoney(totR)} revenue`} height="h-[280px]">
          <SalesOrdersChart rows={soTrend} />
        </ChartCard>
      )}
    </div>
  );
}
