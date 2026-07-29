import { fmt, fmtMoney, fmtMoneyCompact } from '@shared/utils';
import { useStore } from '../../store';
import { KpiCard } from '../../components/Kpi';
import { BarsChart, HBarsChart, GroupedBarsChart, DoughnutStat } from '../../charts/Charts';
import { PAL } from '../../charts/palette';
import { Panel, RankedBars, DataNote } from './parts';

export default function Revenue() {
  const d = useStore((s) => s.analytics.revenue);
  const loading = useStore((s) => s.analyticsLoading.revenue);
  if (loading || !d) return <div className="crm-empty py-10">{loading ? 'Loading revenue analytics…' : 'No revenue data'}</div>;

  const k = d.kpis;
  const ccy = d.currency;
  const f = d.fulfilment;
  const monthly = d.monthly || [];
  const big = (d.value_distribution || []).find((r) => r.label === '1M+');

  return (
    <div className="grid gap-[18px]">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(178px,1fr))] gap-[18px]">
        <KpiCard compact lbl="Quotations" val={fmt(k.quotations)} sub="raised in range"
          chip={fmtMoneyCompact(k.quotation_value, ccy)} chipTone="gold" />
        <KpiCard compact lbl="Orders" val={fmt(k.orders)} sub="submitted in range" />
        <KpiCard compact lbl="Booked" val={fmtMoneyCompact(k.booked, ccy)} sub={`order value · ${ccy}`} />
        <KpiCard compact lbl="Avg order" val={fmtMoneyCompact(k.avg_order, ccy)} sub="per submitted order" />
        <KpiCard compact lbl="Buyers" val={fmt(k.customers_ordering)} sub="distinct accounts ordering" />
        {/* Only shown when fulfilment is actually recorded; otherwise the slot goes
            to a figure that means something. */}
        {f.recorded ? (
          <KpiCard compact lbl="Fully delivered" val={fmt(f.fully_delivered)} sub={`of ${fmt(k.orders)} orders`}
            chip={`${f.avg_delivered_pct}% avg`} chipTone={f.avg_delivered_pct >= 90 ? 'up' : 'down'} />
        ) : (
          <KpiCard compact lbl="Orders over 1M" val={fmt(big?.count ?? 0)}
            sub={`worth ${fmtMoneyCompact(big?.value ?? 0, ccy)}`}
            chip={k.booked ? `${Math.round(((big?.value ?? 0) / k.booked) * 100)}% of value` : ''}
            chipTone="gold" />
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-[18px]">
        <Panel title="Order value distribution" sub={`How order sizes are spread · ${ccy}`}>
          <RankedBars rows={d.value_distribution} valueKey="count"
            format={(r) => `${fmt(r.count)} · ${fmtMoneyCompact(r.value, ccy)}`} />
          <DataNote tone="info">
            Count of orders in each size band, with the total value they represent. A long
            tail of small orders with most value in one band is a concentration risk.
          </DataNote>
        </Panel>
        {f.recorded ? (
          <Panel title="Fulfilment" sub="Delivery and billing progress on orders in range">
            <div className="grid gap-3 pt-1">
              {[
                ['Average delivered', `${f.avg_delivered_pct}%`, f.avg_delivered_pct],
                ['Average billed', `${f.avg_billed_pct}%`, f.avg_billed_pct],
              ].map(([label, text, pct]) => (
                <div key={label}>
                  <div className="flex items-baseline justify-between mb-1.5">
                    <span className="text-[12px] text-ink-3">{label}</span>
                    <span className="text-[13px] font-semibold text-ink tabular-nums">{text}</span>
                  </div>
                  <div className="h-[10px] rounded-full bg-[rgba(10,10,10,0.05)] overflow-hidden">
                    <div className="h-full rounded-full"
                      style={{ width: `${Math.min(100, Math.max(0, pct))}%`,
                        background: pct >= 90 ? 'var(--good)' : pct >= 60 ? 'var(--gold)' : 'var(--bad)' }} />
                  </div>
                </div>
              ))}
              <div className="pt-2 border-t border-hairline text-[12px] text-ink-mute">
                {fmt(f.unbilled)} orders not fully billed
              </div>
            </div>
          </Panel>
        ) : (
          <Panel title="Top customers" sub={`By order value in range · ${ccy}`}>
            <RankedBars rows={d.top_customers || []} valueKey="value"
              format={(r) => `${fmtMoneyCompact(r.value, ccy)} · ${fmt(r.orders)}`} />
            <DataNote>
              Fulfilment progress is not tracked on this site — delivered and billed
              percentages are zero on all {fmt(k.orders)} orders in range
              {f.dominant_status ? `, and ${fmt(f.dominant_status.count)} of them sit at
              "${f.dominant_status.label}"` : ''}. Two 0% meters would read as a delivery
              crisis rather than as a field nobody updates, so this space shows revenue
              concentration instead.
            </DataNote>
          </Panel>
        )}
      </div>

      <Panel title="Customers per month" sub="Distinct accounts ordering, and how many were new">
        <div className="h-[280px] relative">
          {monthly.length ? (
            <GroupedBarsChart labels={monthly.map((r) => r.label)}
              a={monthly.map((r) => r.customers)} b={monthly.map((r) => r.new_customers)}
              aLabel="Ordering" bLabel="New" />
          ) : <div className="crm-empty">No orders in range</div>}
        </div>
        <DataNote tone="info">
          "New" counts accounts created within 90 days of the order, so it approximates
          first-time buyers rather than reading a flag that does not exist.
        </DataNote>
      </Panel>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-[18px]">
        <Panel title="Quotation status">
          <div className="h-[220px] relative"><DoughnutStat items={d.quotation_status_mix} centerLabel="quotes" /></div>
          <div className="clegend">
            {(d.quotation_status_mix || []).map((r, i) => (
              <span key={r.label}><i style={{ background: PAL[i % PAL.length] }} />{r.label} · {fmt(r.count)}</span>
            ))}
          </div>
        </Panel>
        <Panel title="Order status"><div className="h-[220px] relative">
          <HBarsChart labels={(d.order_status_mix || []).map((r) => r.label)}
            data={(d.order_status_mix || []).map((r) => r.count)} />
        </div></Panel>
        <Panel title="Value by territory" sub={ccy}><div className="h-[220px] relative">
          <HBarsChart labels={(d.territory_value || []).map((r) => r.label)}
            data={(d.territory_value || []).map((r) => r.value)} money ccy={ccy} />
        </div></Panel>
      </div>
    </div>
  );
}
