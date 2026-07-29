import { fmt, fmtMoneyCompact } from '@shared/utils';
import { useStore } from '../../store';
import { KpiCard } from '../../components/Kpi';
import { Panel, DataNote, FunnelStages } from './parts';

const RAMP = ['#2a2a26', '#8a6a10', '#d9a514'];

export default function Funnel() {
  const d = useStore((s) => s.analytics.funnel);
  const loading = useStore((s) => s.analyticsLoading.funnel);
  const select = useStore((s) => s.select);

  if (loading || !d) return <div className="crm-empty py-10">{loading ? 'Measuring the funnel…' : 'No funnel data'}</div>;
  if (d.error) return <div className="crm-empty py-10">Could not load the funnel</div>;

  const k = d.kpis;
  const v = d.velocity;
  const link = d.linkage;
  const ccy = d.currency;

  return (
    <div className="grid gap-[18px]">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(178px,1fr))] gap-[18px]">
        <KpiCard lbl="Leads in range" val={fmt(k.leads)} sub="the cohort measured below" />
        <KpiCard lbl="Became opportunities" val={fmt(k.opportunities)}
          sub="from those leads" chip={`${k.lead_to_opp_rate}% of leads`} chipTone="gold" />
        <KpiCard lbl="Won" val={fmt(k.won)} sub="opportunities converted"
          chip={`${k.win_rate}% win rate`} chipTone={k.win_rate >= 50 ? 'up' : 'down'} />
        <KpiCard lbl="Became customers" val={fmt(k.customers_created)} sub="accounts created from a lead" />
        <KpiCard lbl="Lead → opportunity" val={v.lead_to_opportunity_days ?? '—'} suffix="days"
          sub={`median of ${fmt(v.samples.lead_to_opportunity)}`} />
        <KpiCard lbl="Lead → customer" val={v.lead_to_customer_days ?? '—'} suffix="days"
          sub={`median of ${fmt(v.samples.lead_to_customer)}`} />
      </div>

      <Panel
        title="Cohort funnel"
        sub="Of the leads created in this range, how many progressed — not a count of each stage independently"
      >
        <FunnelStages stages={d.stages} ramp={RAMP} />
        <DataNote tone="info">
          Every stage here follows the <em>same</em> leads forward through their linked
          opportunities. A funnel built by counting each stage separately can show more
          orders than leads, which is why this one does not do that.
        </DataNote>
      </Panel>

      <Panel
        title="Where the document chain stops"
        sub="What the funnel cannot measure on this site, and why"
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-xl border border-hairline p-4">
            <div className="text-[10px] uppercase tracking-[0.16em] text-ink-mute font-medium mb-1.5">
              Opportunities from leads
            </div>
            <div className="text-[22px] font-semibold text-ink tabular-nums">{fmt(link.opp_from_lead)}</div>
            <div className="text-[11.5px] text-good mt-1">linked — usable</div>
          </div>
          <div className="rounded-xl border border-hairline p-4">
            <div className="text-[10px] uppercase tracking-[0.16em] text-ink-mute font-medium mb-1.5">
              Quotations from those opportunities
            </div>
            <div className="text-[22px] font-semibold text-ink tabular-nums">{fmt(link.quote_from_opp)}</div>
            <div className="text-[11.5px] text-warn mt-1">too few to rate</div>
          </div>
          <div className="rounded-xl border border-hairline p-4">
            <div className="text-[10px] uppercase tracking-[0.16em] text-ink-mute font-medium mb-1.5">
              Orders raised from a quotation
            </div>
            <div className="text-[22px] font-semibold text-ink tabular-nums">
              {fmt(link.orders_from_quotation)}<span className="text-ink-mute text-[14px] font-medium"> / {fmt(link.orders)}</span>
            </div>
            <div className="text-[11.5px] text-bad mt-1">chain not used</div>
          </div>
        </div>
        {link.chain_broken_after ? (
          <DataNote>
            Orders are created directly rather than from quotations, so the{' '}
            {fmt(link.orders)} orders worth {fmtMoneyCompact(link.order_value, ccy)} in this
            range cannot be attributed to the funnel above. That is a process fact, not a
            conversion failure — quoting through the Opportunity would make the rest of the
            funnel measurable.
          </DataNote>
        ) : (
          <DataNote tone="info">The document chain is intact for this range.</DataNote>
        )}
        <button
          onClick={() => select('rep', 'sales')}
          className="mt-3 text-[12.5px] font-medium text-gold-text hover:underline"
        >
          See the order book in Reports → Sales →
        </button>
      </Panel>
    </div>
  );
}
