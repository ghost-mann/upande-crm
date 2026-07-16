import { useStore } from '../store';
import { fmt, fmtMoney, fmtMoneyCompact } from '@shared/utils';
import { openFrappe } from '@/lib/crm';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { KpiCard } from '../components/Kpi';
import ChartCard from '../components/ChartCard';
import { DoughnutStat, BarsChart, HBarsChart, SalesOrdersChart, AreaTrendChart } from '../charts/Charts';
import { PAL } from '../charts/palette';

// Funnel bar colours — ink → gold descending ramp.
const FUNNEL_RAMP = ['#2a2a26', '#5a5a52', '#8a6a10', '#a87d0d', '#d9a514'];

function Funnel({ rows }) {
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <div className="funnel">
      {rows.map((f, i) => {
        const pct = Math.max((f.count / max) * 100, 12);
        return (
          <div key={f.label} className="funnel__stage">
            <div className="funnel__bar" style={{ width: `${pct}%`, background: FUNNEL_RAMP[i % FUNNEL_RAMP.length] }}>
              {f.label}
            </div>
            <div className="funnel__meta"><b>{fmt(f.count)}</b>{i > 0 ? `${((f.count / (rows[0].count || 1)) * 100).toFixed(0)}% of leads` : 'entering'}</div>
          </div>
        );
      })}
    </div>
  );
}

export default function Overview() {
  const { data, status, settings } = useStore();
  const OV = data.overview;
  const C = data.cust;

  if (!OV?.kpis) {
    return (
      <div className="p-12 text-center text-ink-mute text-[13px]">
        {status === 'loading' ? 'Loading' : status === 'offline' ? 'Failed to load CRM data' : 'No overview data'}
      </div>
    );
  }

  const k = OV.kpis;
  const kpis = [
    { lbl: 'Leads', val: fmt(k.leads?.total), sub: 'in selected range', chip: `${k.leads?.conv_rate ?? 0}% conversion`, chipTone: 'gold' },
    { lbl: 'Opportunities', val: fmt(k.opps?.total), sub: `${fmt(k.opps?.open)} open`, chip: `${fmt(k.opps?.won)} won`, chipTone: 'up' },
    { lbl: 'Prospects', val: fmt(k.prosp?.total), sub: 'engaged accounts', chip: `${fmt(k.prosp?.territories)} territories` },
    { lbl: 'Customers', val: fmt(k.cust?.active), sub: 'active accounts', chip: `${fmt(k.cust?.companies)} companies` },
    { lbl: 'Revenue', val: fmtMoneyCompact(k.revenue?.usd, 'USD'), sub: 'sales orders', chip: `${fmt(k.revenue?.orders)} orders`, chipTone: 'gold' },
    { lbl: 'Open Tasks', val: fmt(k.tasks?.open), sub: 'to action', chip: `${fmt(k.tasks?.high)} high priority`, chipTone: k.tasks?.high ? 'down' : '' },
  ];

  const soTrend = C?.sales_order_trend;
  const totR = soTrend?.reduce((s, r) => s + (r.revenue || 0), 0) || 0;
  const totC = soTrend?.reduce((s, r) => s + (r.count || 0), 0) || 0;
  const topCust = C?.top_revenue || [];
  const leadStatus = OV.lead_status || [];

  return (
    <div>
      {/* KPI ROW */}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(210px,1fr))] gap-[18px] mb-[18px]">
        {kpis.map((x) => <KpiCard key={x.lbl} {...x} />)}
      </div>

      {/* TREND + TOP CUSTOMERS */}
      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-[18px] mb-[18px]">
        <Card>
          <CardHeader>
            <div><CardTitle>Sales &amp; Orders Trend</CardTitle><CardSub>Daily orders and revenue in range</CardSub></div>
            <div className="text-[12px] text-ink-mute font-medium">{fmt(totC)} orders · ${fmtMoney(totR)}</div>
          </CardHeader>
          <CardContent>
            <div className="h-[300px] relative">
              {soTrend?.length ? <SalesOrdersChart rows={soTrend} />
                : <AreaTrendChart labels={(OV.so_trend || []).map((r) => r.label)} data={(OV.so_trend || []).map((r) => r.count)} />}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><div><CardTitle>Top Customers</CardTitle><CardSub>By revenue · in range</CardSub></div></CardHeader>
          <CardContent>
            {topCust.length ? (
              <div className="list">
                {topCust.slice(0, 6).map((r, i) => (
                  <div key={r.customer} className="list__row" onClick={() => openFrappe('Customer', r.customer, settings.openInNewTab)}>
                    <div className={`list__rank${i === 0 ? ' lead' : ''}`}>{i + 1}</div>
                    <div><div className="list__name truncate">{r.customer}</div><div className="list__meta">Customer</div></div>
                    <div className="list__qty">${fmtMoney(r.usd)}</div>
                  </div>
                ))}
              </div>
            ) : <div className="crm-empty">No revenue in range</div>}
          </CardContent>
        </Card>
      </div>

      {/* FUNNEL + LEAD STATUS */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-[18px] mb-[18px]">
        <Card>
          <CardHeader><div><CardTitle>Sales Funnel</CardTitle><CardSub>Conversion at each stage</CardSub></div></CardHeader>
          <CardContent>{OV.funnel?.length ? <Funnel rows={OV.funnel} /> : <div className="crm-empty">No data</div>}</CardContent>
        </Card>
        <Card>
          <CardHeader><div><CardTitle>Lead Status</CardTitle><CardSub>Distribution</CardSub></div></CardHeader>
          <CardContent>
            <div className="h-[220px] relative"><DoughnutStat items={leadStatus} centerLabel="leads" /></div>
            <div className="clegend">
              {leadStatus.map((r, i) => (
                <span key={r.label}><i style={{ background: PAL[i % PAL.length] }} />{r.label} · {fmt(r.count)}</span>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* SECONDARY CHARTS */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-[18px] mb-[18px]">
        <ChartCard title="Lead Trend" sub="In selected range" height="h-[240px]">
          <AreaTrendChart labels={(OV.lead_trend || []).map((r) => r.label)} data={(OV.lead_trend || []).map((r) => r.count)} />
        </ChartCard>
        <ChartCard title="Top Territories" height="h-[240px]">
          <HBarsChart labels={(OV.top_territories || []).map((r) => r.label)} data={(OV.top_territories || []).map((r) => r.count)} />
        </ChartCard>
        <ChartCard title="Sales Stages" height="h-[240px]">
          <BarsChart labels={(OV.sales_stages || []).map((r) => r.label)} data={(OV.sales_stages || []).map((r) => r.count)} />
        </ChartCard>
      </div>
    </div>
  );
}
