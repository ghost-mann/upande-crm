import { fmt } from '@shared/utils';
import { useStore } from '../../store';
import { KpiCard } from '../../components/Kpi';
import { BarsChart, HBarsChart, DoughnutStat } from '../../charts/Charts';
import { PAL } from '../../charts/palette';
import { Panel, RankedBars, DataNote } from './parts';

export default function Opportunities() {
  const d = useStore((s) => s.analytics.opps);
  const loading = useStore((s) => s.analyticsLoading.opps);
  if (loading || !d) return <div className="crm-empty py-10">{loading ? 'Loading opportunity analytics…' : 'No opportunity data'}</div>;

  const k = d.kpis;

  return (
    <div className="grid gap-[18px]">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(178px,1fr))] gap-[18px]">
        <KpiCard lbl="Opportunities" val={fmt(k.total)} sub="raised in range" />
        <KpiCard lbl="Open" val={fmt(k.open)} sub="still in play" />
        <KpiCard lbl="Won" val={fmt(k.won)} sub="converted"
          chip={`${k.win_rate}% of decided`} chipTone={k.win_rate >= 50 ? 'up' : 'down'} />
        <KpiCard lbl="Lost" val={fmt(k.lost)} sub="closed lost" chipTone={k.lost ? 'down' : ''} />
        <KpiCard lbl="Avg confidence" val={k.avg_probability} suffix="%"
          sub="mean recorded probability" />
        <KpiCard lbl="From prospects" val={fmt(k.from_prospect)} sub="rest came from leads" />
      </div>

      {/* Value is deliberately absent, and says so: charting zeros would imply the
          pipeline is worth nothing rather than that nobody fills the field in. */}
      {!k.amounts_recorded && (
        <Panel title="Pipeline value is not available" sub="Because the data to compute it is not there">
          <div className="text-[13px] text-ink-2">
            None of the {fmt(k.total)} opportunities in this range has an amount recorded, so
            pipeline value, weighted value and average deal size cannot be shown. Probability
            <em> is</em> recorded on all of them, so confidence appears above and per stage
            below.
          </div>
          <DataNote>
            Filling in <code>opportunity_amount</code> would make weighted pipeline value
            (amount × probability) available with no further work here.
          </DataNote>
        </Panel>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-[18px]">
        <Panel title="Stage distribution" sub="Where open opportunities are sitting">
          <RankedBars rows={d.by_stage} valueKey="count"
            format={(r) => `${fmt(r.count)} · ${r.avg_probability}%`} />
          <DataNote tone="info">
            Right-hand figure is count and the stage's average recorded probability.
          </DataNote>
        </Panel>
        <Panel title="Open opportunity ageing" sub="Days since raised, for those still open">
          <div className="h-[240px] relative">
            <BarsChart labels={(d.age_buckets || []).map((r) => r.label)}
              data={(d.age_buckets || []).map((r) => r.count)} />
          </div>
        </Panel>
      </div>

      <Panel title="By owner" sub="Volume against win rate — the two together say more than either alone">
        <RankedBars rows={d.by_owner} valueKey="count"
          format={(r) => `${fmt(r.count)} · ${r.win_rate}% won`} />
      </Panel>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-[18px]">
        <Panel title="Status">
          <div className="h-[210px] relative"><DoughnutStat items={d.status_mix} centerLabel="opps" /></div>
          <div className="clegend">
            {(d.status_mix || []).map((r, i) => (
              <span key={r.label}><i style={{ background: PAL[i % PAL.length] }} />{r.label} · {fmt(r.count)}</span>
            ))}
          </div>
        </Panel>
        <Panel title="Type"><div className="h-[210px] relative">
          <HBarsChart labels={(d.type_mix || []).map((r) => r.label)} data={(d.type_mix || []).map((r) => r.count)} />
        </div></Panel>
        <Panel title="Source"><div className="h-[210px] relative">
          <HBarsChart labels={(d.source_mix || []).map((r) => r.label)} data={(d.source_mix || []).map((r) => r.count)} />
        </div></Panel>
        <Panel title="Territory"><div className="h-[210px] relative">
          <HBarsChart labels={(d.territory_mix || []).map((r) => r.label)} data={(d.territory_mix || []).map((r) => r.count)} />
        </div></Panel>
      </div>
    </div>
  );
}
