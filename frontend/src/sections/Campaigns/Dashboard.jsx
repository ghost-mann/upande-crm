import { fmt } from '@shared/utils';
import { useStore } from '../../store';
import { KpiCard } from '../../components/Kpi';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { DoughnutStat, HBarsChart } from '../../charts/Charts';
import { PAL } from '../../charts/palette';
import Icon from '../../components/Icon';

export default function CampaignsDashboard() {
  const d = useStore((s) => s.data.campaigns);
  const status = useStore((s) => s.status);
  if (!d?.kpis) {
    return <div className="p-12 text-center text-ink-mute text-[13px]">
      {status === 'loading' ? 'Loading campaigns…' : 'No campaign data'}
    </div>;
  }
  if (d.available === false) {
    return <div className="crm-empty py-10">
      Campaigns need ERPNext&apos;s CRM module, which is not installed on this site.
    </div>;
  }

  const k = d.kpis;
  const byAttribution = [...(d.campaigns || [])]
    .filter((c) => c.attributed_leads)
    .sort((a, b) => b.attributed_leads - a.attributed_leads)
    .slice(0, 8);
  const byEnrolment = [...(d.campaigns || [])]
    .filter((c) => c.enrolled)
    .sort((a, b) => b.enrolled - a.enrolled)
    .slice(0, 8);

  return (
    <div className="grid gap-[18px]">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(178px,1fr))] gap-[18px]">
        <KpiCard compact lbl="Campaigns" val={fmt(k.campaigns)} sub="defined"
          chip={k.without_schedule ? `${fmt(k.without_schedule)} can't send` : 'all sendable'}
          chipTone={k.without_schedule ? 'down' : 'up'} />
        <KpiCard compact lbl="Enrolments" val={fmt(k.enrolled)} sub="recipients ever enrolled" />
        <KpiCard compact lbl="Running" val={fmt(k.active)} sub="scheduled or in progress"
          chipTone={k.active ? 'gold' : ''} chip={k.active ? 'sending' : 'idle'} />
        <KpiCard compact lbl="Attributed leads" val={fmt(k.attributed_leads)}
          sub="tagged to a campaign" />
        <KpiCard compact lbl="With a schedule" val={fmt(k.with_schedule)}
          sub={`of ${fmt(k.campaigns)} campaigns`} />
        <KpiCard compact lbl="Created in range" val={fmt(k.in_range)} sub="new campaigns" />
      </div>

      {/* The single most surprising thing about this engine, so it is said up front. */}
      <div className="rounded-2xl border border-hairline bg-surface-2 px-5 py-4 flex items-start gap-2.5">
        <Icon name="schedule" className="text-[18px] text-ink-mute mt-px shrink-0" />
        <div className="text-[12.5px] text-ink-2">
          Campaign emails are sent by the <strong>daily scheduler</strong>, not when you enrol
          someone. A campaign started today sends its first template on the next daily run.
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-[18px]">
        <Card>
          <CardHeader>
            <div><CardTitle>Most enrolled</CardTitle><CardSub>Recipients per campaign</CardSub></div>
          </CardHeader>
          <CardContent>
            {byEnrolment.length ? (
              <div className="h-[250px] relative">
                <HBarsChart labels={byEnrolment.map((c) => c.title)}
                  data={byEnrolment.map((c) => c.enrolled)} />
              </div>
            ) : <div className="crm-empty">Nothing enrolled yet</div>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Leads attributed</CardTitle>
              <CardSub>Leads tagged to each campaign</CardSub>
            </div>
          </CardHeader>
          <CardContent>
            {byAttribution.length ? (
              <div className="pt-1">
                {byAttribution.map((c) => (
                  <div key={c.name} className="grid grid-cols-[1fr_auto] items-center gap-3 py-2 border-b border-hairline last:border-b-0">
                    <div className="min-w-0">
                      <div className="text-[12.5px] text-ink truncate">{c.title}</div>
                      <div className="text-[11px] text-ink-mute">
                        {fmt(c.attributed_converted)} converted
                      </div>
                    </div>
                    <div className="text-[13px] font-semibold text-ink tabular-nums">
                      {fmt(c.attributed_leads)}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="grid gap-2">
                <div className="crm-empty">No leads are tagged to a campaign yet</div>
                <div className="text-[11.5px] text-ink-mute">
                  Enrol leads with attribution on and this fills in — it is what makes
                  campaign performance measurable.
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-[18px]">
        <Card>
          <CardHeader><div><CardTitle>Enrolment status</CardTitle></div></CardHeader>
          <CardContent>
            <div className="h-[210px] relative">
              <DoughnutStat items={d.status_mix} centerLabel="enrolments" />
            </div>
            <div className="clegend">
              {(d.status_mix || []).map((r, i) => (
                <span key={r.label}><i style={{ background: PAL[i % PAL.length] }} />{r.label} · {fmt(r.count)}</span>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><div><CardTitle>Sent to</CardTitle><CardSub>Leads, contacts or groups</CardSub></div></CardHeader>
          <CardContent><div className="h-[210px] relative">
            <HBarsChart labels={(d.target_mix || []).map((r) => r.label)}
              data={(d.target_mix || []).map((r) => r.count)} />
          </div></CardContent>
        </Card>
        <Card>
          <CardHeader><div><CardTitle>Largest audiences</CardTitle><CardSub>Active subscribers</CardSub></div></CardHeader>
          <CardContent><div className="h-[210px] relative">
            <HBarsChart labels={(d.audiences || []).map((a) => a.name)}
              data={(d.audiences || []).map((a) => a.active)} />
          </div></CardContent>
        </Card>
      </div>
    </div>
  );
}
