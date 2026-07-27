import { fmt, fmtMoney, fmtMoneyCompact } from '@shared/utils';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { useStore } from '../../store';
import { KpiCard } from '../../components/Kpi';
import ChartCard from '../../components/ChartCard';
import { GroupedBarsChart, HBarsChart } from '../../charts/Charts';

// Aging is coloured by severity rather than from the categorical palette, so an
// overdue-heavy book reads as a problem instead of as five neutral bars.
const AGING_TONE = {
  Current: 'var(--good)',
  '1-30': 'var(--warn)',
  '31-60': '#b06a10',
  '60+': 'var(--bad)',
};

function Bar({ label, value, max, total, color, ccy }) {
  const pct = max ? Math.max((value / max) * 100, 1.5) : 0;
  const share = total ? ((value / total) * 100).toFixed(0) : '0';
  return (
    <div className="grid grid-cols-[92px_1fr_auto] items-center gap-3 py-1.5">
      <div className="text-[12px] text-ink-3 truncate">{label}</div>
      <div className="h-[22px] rounded-md bg-[rgba(10,10,10,0.04)] overflow-hidden">
        <div className="h-full rounded-md transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="text-[12px] font-semibold text-ink tabular-nums text-right min-w-[86px]">
        {fmtMoneyCompact(value, ccy)}
        <span className="text-ink-mute font-medium ml-1.5">{share}%</span>
      </div>
    </div>
  );
}

export default function SalesBand() {
  const S = useStore((s) => s.data.sales);
  const status = useStore((s) => s.status);

  if (!S?.kpis) {
    return (
      <div className="mb-[18px] text-[12.5px] text-ink-mute">
        {status === 'loading' ? 'Loading sales analytics…' : 'Sales analytics unavailable'}
      </div>
    );
  }

  const k = S.kpis;
  const ccy = S.currency || 'KES';
  const trend = S.revenue_trend || [];
  const reps = S.rep_performance || [];
  const products = S.top_products || [];
  const terr = S.territory_revenue || [];
  const aging = S.aging || [];

  const agingTotal = aging.reduce((a, r) => a + (r.amount || 0), 0);
  const agingMax = Math.max(...aging.map((r) => r.amount || 0), 1);

  const tiles = [
    {
      lbl: 'Booked', val: fmtMoneyCompact(k.booked, ccy), sub: 'sales orders in range',
      chip: `${fmt(k.booked_orders)} orders`, chipTone: 'gold',
    },
    {
      lbl: 'Billed', val: fmtMoneyCompact(k.billed, ccy), sub: 'invoiced in range',
      chip: `${fmt(k.billed_invoices)} invoices`,
    },
    {
      lbl: 'Growth', val: `${k.growth_pct > 0 ? '+' : ''}${k.growth_pct}%`, sub: 'billed vs prior period',
      chip: k.growth_pct >= 0 ? 'up on last period' : 'down on last period',
      chipTone: k.growth_pct >= 0 ? 'up' : 'down',
    },
    {
      lbl: 'Avg order value', val: fmtMoneyCompact(k.aov, ccy), sub: `per order · ${ccy}`,
    },
    {
      lbl: 'Outstanding', val: fmtMoneyCompact(k.outstanding, ccy), sub: 'unpaid invoices',
      chip: `${fmt(k.outstanding_count)} open`,
      chipTone: k.outstanding ? 'down' : '',
    },
    {
      lbl: 'Overdue 60+', val: fmtMoneyCompact(aging.find((r) => r.label === '60+')?.amount || 0, ccy),
      sub: 'past 60 days',
      chip: agingTotal
        ? `${(((aging.find((r) => r.label === '60+')?.amount || 0) / agingTotal) * 100).toFixed(0)}% of book`
        : 'nothing overdue',
      chipTone: 'down',
    },
  ];

  return (
    <>
      <div className="flex items-baseline gap-3 mb-3.5">
        <h2 className="text-[13px] uppercase tracking-[0.18em] text-ink-4 font-medium">Sales analytics</h2>
        <span className="text-[12px] text-ink-mute">
          amounts in {ccy} (company currency)
        </span>
      </div>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-[18px] mb-[18px]">
        {tiles.map((t) => <KpiCard key={t.lbl} {...t} />)}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-[18px] mb-[18px]">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Booked vs Billed</CardTitle>
              <CardSub>Order value against invoiced value</CardSub>
            </div>
            <div className="text-[12px] text-ink-mute font-medium">
              {fmtMoney(k.booked, ccy)} booked · {fmtMoney(k.billed, ccy)} billed
            </div>
          </CardHeader>
          <CardContent>
            <div className="h-[290px] relative">
              {trend.length ? (
                <GroupedBarsChart labels={trend.map((r) => r.label)}
                  a={trend.map((r) => r.booked)} b={trend.map((r) => r.billed)}
                  aLabel="Booked" bLabel="Billed" ccy={ccy} />
              ) : <div className="crm-empty">No sales in range</div>}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Receivables aging</CardTitle>
              <CardSub>Outstanding by days overdue · all time</CardSub>
            </div>
          </CardHeader>
          <CardContent>
            {agingTotal ? (
              <>
                <div className="pt-1">
                  {aging.map((r) => (
                    <Bar key={r.label} label={r.label} value={r.amount || 0} max={agingMax}
                      total={agingTotal} color={AGING_TONE[r.label] || 'var(--ink-3)'} ccy={ccy} />
                  ))}
                </div>
                <div className="mt-3 pt-3 border-t border-hairline text-[12px] text-ink-mute">
                  {fmtMoney(agingTotal, ccy)} outstanding across {fmt(k.outstanding_count)} invoices
                </div>
              </>
            ) : <div className="crm-empty">Nothing outstanding</div>}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-[18px] mb-[18px]">
        <Card>
          <CardHeader>
            <div><CardTitle>Sales reps</CardTitle><CardSub>By order value · in range</CardSub></div>
          </CardHeader>
          <CardContent>
            {reps.length ? (
              <div className="list">
                {reps.slice(0, 6).map((r, i) => (
                  <div key={r.label} className="list__row !cursor-default">
                    <div className={`list__rank${i === 0 ? ' lead' : ''}`}>{i + 1}</div>
                    <div>
                      <div className="list__name truncate">{r.label}</div>
                      <div className="list__meta">{fmt(r.orders)} orders</div>
                    </div>
                    <div className="list__qty">{fmtMoneyCompact(r.amount, ccy)}</div>
                  </div>
                ))}
              </div>
            ) : <div className="crm-empty">No rep data in range</div>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div><CardTitle>Top products</CardTitle><CardSub>By revenue · in range</CardSub></div>
          </CardHeader>
          <CardContent>
            {products.length ? (
              <div className="list">
                {products.slice(0, 6).map((r, i) => (
                  <div key={r.label} className="list__row !cursor-default">
                    <div className={`list__rank${i === 0 ? ' lead' : ''}`}>{i + 1}</div>
                    <div>
                      <div className="list__name truncate">{r.label}</div>
                      <div className="list__meta">{fmt(Math.round(r.qty))} units</div>
                    </div>
                    <div className="list__qty">{fmtMoneyCompact(r.amount, ccy)}</div>
                  </div>
                ))}
              </div>
            ) : <div className="crm-empty">No product data in range</div>}
          </CardContent>
        </Card>

        <ChartCard title="Revenue by territory" sub={`Invoiced · ${ccy}`} height="h-[240px]">
          {terr.length ? (
            <HBarsChart labels={terr.map((r) => r.label)} data={terr.map((r) => r.amount)} money ccy={ccy} />
          ) : <div className="crm-empty">No territory data</div>}
        </ChartCard>
      </div>
    </>
  );
}
