import { useStore } from '../../store';
import { fmt } from '@shared/utils';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import Icon from '../../components/Icon';
import ChartCard from '../../components/ChartCard';
import { DoughnutStat, BarsChart, HBarsChart, AreaTrendChart } from '../../charts/Charts';
import { PAL } from '../../charts/palette';
import SalesBand from './SalesBand';
import Kpis from './Kpis';
import Upcoming from './Upcoming';
import TrackRecord from './TrackRecord';
import Movers from './Movers';
import MoverDrill from './MoverDrill';
import TopSellers from './TopSellers';
import Demand from './Demand';
import RepScorecard from './RepScorecard';
import RepConversion from './RepConversion';
import Funnel from './Funnel';
import FollowUps from './FollowUps';
import { BandHead } from './parts';

// Capture, in the two moves that matter. Both open the same dialogs the Demand
// card links to, so "there is no demand recorded" and "here is how you record it"
// are one gesture apart.
function CaptureBar() {
  const openLead = useStore((s) => s.openLeadDialog);
  const openConvert = useStore((s) => s.openConvertDialog);
  return (
    <div className="flex items-center gap-2.5 flex-wrap mb-[18px]">
      <Button size="sm" onClick={() => openLead({})}
        className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-4">
        <Icon name="person_add" className="text-[16px]" />New lead
      </Button>
      <Button size="sm" variant="outline" className="rounded-full"
        onClick={() => openConvert({ mode: 'opportunity' })}>
        <Icon name="trending_up" className="text-[16px]" />Convert a lead
      </Button>
      <span className="text-[11.5px] text-ink-mute">
        converting is also where the flowers a client asked for get recorded
      </span>
    </div>
  );
}

// The command centre, in the order a sales manager actually reads it:
//
//   what you can add        → capture bar
//   what came in            → KPIs
//   what has to be done     → upcoming work, follow-ups waiting
//   how sales are going     → track record per flower and per rep
//   what moved and why      → movers, and the drill behind them
//   who buys what           → top sellers, and what is being asked for
//   who sells it            → salesperson performance, and conversion
//   the money               → sales band, funnel, pipeline shape
//
// Revenue used to lead this page. It now sits where it belongs: after the work.
export default function Overview() {
  const { data, status } = useStore();
  const OV = data.overview;
  const C = data.command;

  if (!OV?.kpis && !C?.kpis) {
    return (
      <div className="p-12 text-center text-ink-mute text-[13px]">
        {status === 'loading' ? 'Loading' : status === 'offline' ? 'Failed to load CRM data' : 'No overview data'}
      </div>
    );
  }

  const leadStatus = OV?.lead_status || [];

  return (
    <div>
      <CaptureBar />
      <Kpis />

      <BandHead title="The day" note="from now forward, independent of the date range" />
      <div className="mb-[18px]"><Upcoming /></div>
      <FollowUps />

      <BandHead title="Track record"
        note="how sales have been going, and what changed" />
      <div className="mb-[18px]"><TrackRecord /></div>
      <Movers />

      {/* Sold beside asked-for. Neither number means much alone: a variety that
          tops the sales list and nobody is asking for any more is the expensive
          case this pairing exists to make visible. */}
      <BandHead title="Who buys what" note="what shipped, and what is being asked for" />
      <div className="mb-[18px]"><TopSellers /></div>
      <div className="mb-[18px]"><Demand /></div>

      <BandHead title="Who sells it" note="what they booked, and what they convert" />
      <div className="mb-[18px]"><RepScorecard /></div>
      <div className="mb-[18px]"><RepConversion /></div>

      <SalesBand />

      {/* FUNNEL + LEAD STATUS */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-[18px] mb-[18px]">
        <Funnel />
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
          <AreaTrendChart labels={(OV?.lead_trend || []).map((r) => r.label)} data={(OV?.lead_trend || []).map((r) => r.count)} />
        </ChartCard>
        <ChartCard title="Top Territories" height="h-[240px]">
          <HBarsChart labels={(OV?.top_territories || []).map((r) => r.label)} data={(OV?.top_territories || []).map((r) => r.count)} />
        </ChartCard>
        <ChartCard title="Sales Stages" height="h-[240px]">
          <BarsChart labels={(OV?.sales_stages || []).map((r) => r.label)} data={(OV?.sales_stages || []).map((r) => r.count)} />
        </ChartCard>
      </div>

      <MoverDrill />
    </div>
  );
}
