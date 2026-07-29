import { fmt } from '@shared/utils';
import { useStore } from '../../store';
import { KpiCard } from '../../components/Kpi';
import { DoughnutStat, BarsChart, HBarsChart } from '../../charts/Charts';
import { PAL } from '../../charts/palette';
import { Panel, RankedBars, DataNote } from './parts';

export default function Leads() {
  const d = useStore((s) => s.analytics.leads);
  const loading = useStore((s) => s.analyticsLoading.leads);
  if (loading || !d) return <div className="crm-empty py-10">{loading ? 'Loading lead analytics…' : 'No lead data'}</div>;

  const k = d.kpis;
  const sourced = k.total ? Math.round((k.with_source / k.total) * 100) : 0;

  return (
    <div className="grid gap-[18px]">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(178px,1fr))] gap-[18px]">
        <KpiCard lbl="Leads" val={fmt(k.total)} sub="created in range" />
        <KpiCard lbl="Converted" val={fmt(k.converted)} sub="reached customer"
          chip={`${k.conv_rate}%`} chipTone="gold" />
        <KpiCard lbl="Lost" val={fmt(k.lost)} sub="marked lost" chipTone={k.lost ? 'down' : ''} />
        <KpiCard lbl="Source recorded" val={`${sourced}%`} sub={`${fmt(k.with_source)} of ${fmt(k.total)}`}
          chipTone={sourced >= 75 ? 'up' : 'down'} chip={sourced >= 75 ? 'good coverage' : 'patchy'} />
      </div>

      <Panel
        title="Which sources actually convert"
        sub="Leads per source against how many became an opportunity — volume and quality are not the same thing"
      >
        <RankedBars
          rows={d.by_source} valueKey="leads"
          format={(r) => `${fmt(r.leads)} · ${r.rate}%`}
        />
        <DataNote tone="info">
          The right-hand figure is lead count and conversion rate. A big source with a low
          rate is a volume problem, not a win.
        </DataNote>
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-[18px]">
        <Panel title="Qualification" sub="How leads were graded">
          <div className="h-[230px] relative">
            <DoughnutStat items={d.qualification_mix} centerLabel="leads" />
          </div>
          <div className="clegend">
            {(d.qualification_mix || []).map((r, i) => (
              <span key={r.label}><i style={{ background: PAL[i % PAL.length] }} />{r.label} · {fmt(r.count)}</span>
            ))}
          </div>
        </Panel>
        <Panel title="Open lead ageing" sub="How long un-worked leads have been sitting">
          <div className="h-[230px] relative">
            <BarsChart labels={(d.age_buckets || []).map((r) => r.label)}
              data={(d.age_buckets || []).map((r) => r.count)} />
          </div>
          <DataNote tone="info">
            Excludes converted, lost and do-not-contact. A tall 90d+ bar is stale pipeline.
          </DataNote>
        </Panel>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-[18px]">
        <Panel title="Status"><div className="h-[210px] relative">
          <HBarsChart labels={(d.status_mix || []).map((r) => r.label)} data={(d.status_mix || []).map((r) => r.count)} />
        </div></Panel>
        <Panel title="Territory"><div className="h-[210px] relative">
          <HBarsChart labels={(d.territory_mix || []).map((r) => r.label)} data={(d.territory_mix || []).map((r) => r.count)} />
        </div></Panel>
        <Panel title="Market segment"><div className="h-[210px] relative">
          <HBarsChart labels={(d.segment_mix || []).map((r) => r.label)} data={(d.segment_mix || []).map((r) => r.count)} />
        </div></Panel>
        <Panel title="Owner"><div className="h-[210px] relative">
          <HBarsChart labels={(d.owner_mix || []).map((r) => String(r.label).split('@')[0])}
            data={(d.owner_mix || []).map((r) => r.count)} />
        </div></Panel>
      </div>
    </div>
  );
}
