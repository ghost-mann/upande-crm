import { fmt } from '@shared/utils';
import { useStore } from '../../store';
import { KpiCard } from '../../components/Kpi';
import { Panel, DataNote, FunnelStages } from './parts';

const RAMP = ['#2a2a26', '#8a6a10', '#d9a514'];

export default function Funnel() {
  const d = useStore((s) => s.analytics.funnel);
  const loading = useStore((s) => s.analyticsLoading.funnel);

  if (loading || !d) return <div className="crm-empty py-10">{loading ? 'Measuring the funnel…' : 'No funnel data'}</div>;
  if (d.error) return <div className="crm-empty py-10">Could not load the funnel</div>;

  const k = d.kpis;
  const v = d.velocity;

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

    </div>
  );
}
