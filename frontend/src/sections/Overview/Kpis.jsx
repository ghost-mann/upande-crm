import { fmt } from '@shared/utils';
import { useStore } from '../../store';
import { KpiCard } from '../../components/Kpi';

// The command centre's six tiles.
//
// Ordered the way an account actually moves: it arrives as a lead, becomes an
// engaged prospect, and only then becomes an opportunity. Prospects therefore sits
// before "to opportunity" rather than after it — reading the row left to right
// should trace the pipeline, not jump over the middle of it.
//
// Revenue is deliberately absent: it is the sales band's headline further down
// the page, and leading the Overview with it made the top of a *command* centre a
// number nobody can act on. "Open tasks" is gone for the same reason — it has
// been replaced by the upcoming table, which can actually be worked.
export default function Kpis() {
  const C = useStore((s) => s.data.command);
  const k = C?.kpis;
  if (!k) return null;

  const tiles = [
    {
      lbl: 'New leads', val: fmt(k.new_leads?.total), sub: 'in selected range',
      chip: k.new_leads?.prev
        ? `${k.new_leads.delta_pct > 0 ? '+' : ''}${k.new_leads.delta_pct}% vs prior period`
        : 'no prior period',
      chipTone: !k.new_leads?.prev ? '' : k.new_leads.delta_pct >= 0 ? 'up' : 'down',
    },
    {
      lbl: 'Prospects', val: fmt(k.prosp?.total), sub: 'engaged accounts',
    },
    {
      lbl: 'To opportunity', val: fmt(k.to_opp?.total), sub: 'converted in range',
      chip: `${k.to_opp?.conv_rate ?? 0}% of new leads`, chipTone: 'gold',
    },
    {
      lbl: 'Customers', val: fmt(k.cust?.active), sub: 'active accounts',
      chip: `${fmt(k.cust?.companies)} companies`,
    },
    {
      lbl: 'Upcoming', val: fmt(k.upcoming?.total), sub: 'next 7 days',
      chip: k.upcoming?.overdue
        ? `${fmt(k.upcoming.overdue)} overdue`
        : `${fmt(k.upcoming?.tasks)} tasks · ${fmt(k.upcoming?.events)} events`,
      chipTone: k.upcoming?.overdue ? 'down' : '',
    },
    {
      lbl: 'Follow-ups', val: fmt(k.follow_ups?.total), sub: 'awaiting a response',
      chip: k.follow_ups?.oldest_days
        ? `oldest ${fmt(k.follow_ups.oldest_days)}d waiting`
        : 'nothing waiting',
      chipTone: k.follow_ups?.oldest_days > 7 ? 'down' : '',
    },
  ];

  // A fixed column count rather than auto-fit: six tiles into auto-fit wraps
  // 5 + 1 at common widths, leaving a hole the width of four cards. These steps
  // all divide six evenly.
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-[18px] mb-[18px]">
      {tiles.map((t) => <KpiCard key={t.lbl} {...t} compact />)}
    </div>
  );
}
