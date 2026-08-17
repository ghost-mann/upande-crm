import { fmt } from '@shared/utils';
import { Card, CardHeader, CardTitle, CardSub } from '@/components/ui/card';
import { useStore } from '../../store';

// Effort beside outcome, for the half of the job the scorecard above cannot see.
//
// "Salesperson performance" ranks people by what they sold, keyed on the Sales
// Order's owner. This card ranks them by what they *convert*, keyed on the lead's
// owner. They are deliberately two cards: only six users appear in both fields on
// this site, so folding conversion into the scorecard would have left thirteen of
// nineteen rows showing dashes.
//
// Unassigned is not a footnote. It is the largest row here — most leads on this
// site have nobody's name on them — so it is always shown, never truncated away,
// and separated by a rule so it cannot be mistaken for a person.

function Bar({ pct, muted }) {
  return (
    <span className="flex items-center gap-2 justify-end">
      <span className="text-[12px] font-semibold tabular-nums text-ink w-[42px] text-right">
        {pct}%
      </span>
      <span className="block w-[64px] h-[5px] rounded-full bg-surface-3 overflow-hidden shrink-0">
        <span className={`block h-full rounded-full ${muted ? 'bg-ink-mute' : 'bg-gold'}`}
          style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }} />
      </span>
    </span>
  );
}

function Row({ r }) {
  return (
    <tr className={r.unassigned ? 'border-t border-line' : undefined}>
      <td className={`whitespace-nowrap ${r.unassigned ? 'text-ink-mute italic' : 'text-ink font-medium'}`}>
        {r.label}
      </td>
      <td className="text-right tabular-nums">{fmt(r.leads)}</td>
      <td className="text-right tabular-nums">{fmt(r.to_opp)}</td>
      <td className="text-right tabular-nums text-ink-mute">{r.opp_rate}%</td>
      <td className="text-right tabular-nums">{fmt(r.won)}</td>
      <td className="!text-right"><Bar pct={r.rate} muted={r.unassigned} /></td>
    </tr>
  );
}

export default function RepConversion() {
  const rows = useStore((s) => s.data.track?.rep_conversion) || [];
  if (!rows.length) return null;

  const named = rows.filter((r) => !r.unassigned);
  const unassigned = rows.find((r) => r.unassigned);

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Conversion by salesperson</CardTitle>
          <CardSub>
            Leads they own, and how far those leads got · ordered by lead count, so a
            single conversion cannot top the table
          </CardSub>
        </div>
      </CardHeader>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th>Salesperson</th>
              <th className="!text-right">Leads</th>
              <th className="!text-right" title="Leads that reached an opportunity">→ Opp</th>
              <th className="!text-right">Opp rate</th>
              <th className="!text-right" title="Leads whose opportunity was won">Won</th>
              <th className="!text-right">Conversion</th>
            </tr>
          </thead>
          <tbody>
            {named.map((r) => <Row key={r.key} r={r} />)}
            {unassigned && <Row key={unassigned.key} r={unassigned} />}
          </tbody>
        </table>
      </div>
      {unassigned && unassigned.leads > 0 && (
        <div className="px-4 pb-3.5 -mt-1 text-[11px] text-ink-mute leading-relaxed">
          {fmt(unassigned.leads)} leads have no owner — they arrived through a web form
          or an import and were never picked up. Progression is measured from the
          documents, never from the lead’s status field.
        </div>
      )}
    </Card>
  );
}
