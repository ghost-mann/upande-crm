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

// Target attainment. Deliberately measured over the calendar month/year rather
// than the header date range — 39% of a monthly target means something different
// on the 10th than on the 28th, which is why elapsed time is drawn as a marker.
function TargetRow({ label, actual, target, pct, elapsed, ccy }) {
  const behind = pct < elapsed - 5;
  const ahead = pct > elapsed + 5;
  const fill = behind ? 'var(--bad)' : ahead ? 'var(--good)' : 'var(--gold)';
  return (
    <div className="py-2.5">
      <div className="flex items-baseline justify-between gap-3 mb-1.5">
        <div className="text-[12px] text-ink-3">{label}</div>
        <div className="text-[12px] text-ink font-semibold tabular-nums">
          {fmtMoneyCompact(actual, ccy)}
          <span className="text-ink-mute font-medium"> / {fmtMoneyCompact(target, ccy)}</span>
        </div>
      </div>
      <div className="h-[10px] rounded-full bg-[rgba(10,10,10,0.05)] relative overflow-hidden">
        <div className="h-full rounded-full transition-all"
          style={{ width: `${Math.max(0, Math.min(100, pct))}%`, background: fill }} />
        <span className="absolute top-0 bottom-0 w-px bg-ink-3" title="Time elapsed"
          style={{ left: `${Math.max(0, Math.min(100, elapsed))}%` }} />
      </div>
      <div className="flex items-center justify-between gap-3 mt-1">
        <span className="text-[11px] text-ink-mute">{elapsed}% elapsed</span>
        <span className={`text-[11px] font-medium ${behind ? 'text-bad' : ahead ? 'text-good' : 'text-ink-2'}`}>
          {pct}% · {behind ? 'behind pace' : ahead ? 'ahead' : 'on pace'}
        </span>
      </div>
    </div>
  );
}

function Targets({ t, ccy }) {
  const select = useStore((s) => s.select);
  const hasTarget = t && (t.monthly > 0 || t.annual > 0);

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Target attainment</CardTitle>
          <CardSub>{t?.basis || 'Billed'} · calendar month and year, not the selected range</CardSub>
        </div>
      </CardHeader>
      <CardContent>
        {hasTarget ? (
          <>
            {t.monthly > 0 && (
              <TargetRow label="This month" actual={t.mtd} target={t.monthly}
                pct={t.mtd_pct} elapsed={t.month_elapsed_pct} ccy={ccy} />
            )}
            {t.annual > 0 && (
              <TargetRow label={`${t.year} to date`} actual={t.ytd} target={t.annual}
                pct={t.ytd_pct} elapsed={t.year_elapsed_pct} ccy={ccy} />
            )}
          </>
        ) : (
          <div className="py-3">
            <div className="text-[13px] text-ink-3 mb-3">
              No revenue target is set, so there is nothing to measure attainment against.
            </div>
            <button
              onClick={() => select('set', 'targets')}
              className="text-[12.5px] font-medium text-gold-text hover:underline"
            >
              Set a target in Settings →
            </button>
          </div>
        )}
      </CardContent>
    </Card>
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

      <div className="mb-[18px]">
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
      </div>

      {/* Attainment sits beside the receivables book: what was aimed at, and
          what is still owed on what was achieved. */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-[18px] mb-[18px]">
        <Targets t={S.targets} ccy={ccy} />

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
