import { fmt, fmtMoneyCompact } from '@shared/utils';
import { Card, CardHeader, CardTitle, CardSub } from '@/components/ui/card';
import { useStore } from '../../store';
import { Delta } from './parts';

// Result beside effort.
//
// Revenue and activity are keyed on the same user, so a rep whose number is
// falling and whose activity columns are empty reads as one row rather than as
// two separate reports nobody joins up.
export default function RepScorecard() {
  const T = useStore((s) => s.data.track);
  const openMover = useStore((s) => s.openMover);
  const rows = T?.rep_performance || [];
  const ccy = T?.currency || 'KES';

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Salesperson performance</CardTitle>
          <CardSub>
            Order value in range, against the prior period · click a row for what moved
          </CardSub>
        </div>
      </CardHeader>
      {rows.length ? (
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>Salesperson</th>
                <th className="!text-right">Booked</th>
                <th className="!text-right">vs prior</th>
                <th className="!text-right">Orders</th>
                <th className="!text-right">Avg order</th>
                <th className="!text-right">Accounts</th>
                <th className="!text-right">Varieties</th>
                <th className="!text-right">Stems</th>
                <th>Activity</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key} className="clickable" onClick={() => openMover('rep', r.key, r.label)}>
                  <td className="text-ink font-medium whitespace-nowrap">{r.label}</td>
                  <td className="text-right tabular-nums text-ink font-semibold whitespace-nowrap">
                    {fmtMoneyCompact(r.amount, ccy)}
                  </td>
                  <td className="text-right whitespace-nowrap">
                    <Delta pct={r.delta_pct} prev={r.prev} />
                  </td>
                  <td className="text-right tabular-nums">{fmt(r.orders)}</td>
                  <td className="text-right tabular-nums whitespace-nowrap">{fmtMoneyCompact(r.aov, ccy)}</td>
                  <td className="text-right tabular-nums">{fmt(r.customers)}</td>
                  <td className="text-right tabular-nums">{fmt(r.varieties)}</td>
                  <td className="text-right tabular-nums">{fmt(Math.round(r.stems))}</td>
                  <td className="whitespace-nowrap">
                    <span className="flex gap-2.5 text-[11.5px] text-ink-mute tabular-nums">
                      <span title="Calls logged in range">{fmt(r.activity?.calls)} calls</span>
                      <span title="Emails sent in range">{fmt(r.activity?.emails)} mail</span>
                      <span title="Open tasks assigned right now">{fmt(r.activity?.tasks)} tasks</span>
                      <span title="Upcoming events they own">{fmt(r.activity?.events)} events</span>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <div className="crm-empty">No rep data in range</div>}
    </Card>
  );
}
