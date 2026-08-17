import { fmt, fmtMoneyCompact } from '@shared/utils';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { useStore } from '../../store';
import { MoneyDelta } from './parts';
import Icon from '../../components/Icon';

// The one-line cause, from the arithmetic rather than from a guess.
//
// A revenue change is exactly a volume effect plus a price effect (see
// _decompose in api/command.py), so naming the larger one is a statement of fact.
// "Stopped" is called out separately because "-100%" understates what happened.
export function cause(r) {
  if (r.stopped) return 'sold nothing this period';
  if (r.started) return 'new this period';
  const dir = r.delta < 0 ? 'fewer' : 'more';
  if (r.driver === 'volume') {
    return `${dir} stems — volume ${r.qty_delta_pct > 0 ? '+' : ''}${r.qty_delta_pct}%`;
  }
  const rate = r.prev_rate ? Math.round((r.rate - r.prev_rate) / r.prev_rate * 100) : 0;
  return `price per stem ${rate > 0 ? '+' : ''}${rate}%, volume held`;
}

function MoverRow({ r, ccy, i }) {
  const openMover = useStore((s) => s.openMover);
  return (
    <button type="button" onClick={() => openMover('flower', r.key, r.label)}
      className="w-full text-left grid grid-cols-[26px_1fr_auto] gap-3 items-center px-2 py-3
                 border-b border-hairline last:border-0 rounded-xl hover:bg-hover transition-colors">
      <span className="w-[26px] h-[26px] rounded-full bg-[rgba(10,10,10,0.05)] grid place-items-center
                       text-[12px] font-semibold text-ink-mute tabular-nums">{i + 1}</span>
      <span className="min-w-0">
        <span className="block text-[14px] font-semibold text-ink truncate">{r.label}</span>
        <span className="block text-[11.5px] text-ink-mute truncate">{cause(r)}</span>
      </span>
      <span className="text-right shrink-0">
        <MoneyDelta value={r.delta} ccy={ccy} className="text-[14px]" />
        <span className="block text-[11.5px] text-ink-mute tabular-nums">
          {fmtMoneyCompact(r.prev, ccy)} → {fmtMoneyCompact(r.amount, ccy)}
        </span>
      </span>
    </button>
  );
}

function Band({ title, sub, rows, ccy, empty, icon, tone }) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle className="flex items-center gap-2">
            <Icon name={icon} className={`!text-[18px] ${tone}`} />
            {title}
          </CardTitle>
          <CardSub>{sub}</CardSub>
        </div>
      </CardHeader>
      <CardContent>
        {rows.length
          ? rows.map((r, i) => <MoverRow key={r.key} r={r} ccy={ccy} i={i} />)
          : <div className="crm-empty">{empty}</div>}
      </CardContent>
    </Card>
  );
}

// Which flowers moved, against the immediately preceding window of equal length.
export default function Movers() {
  const T = useStore((s) => s.data.track);
  const M = T?.movers;
  if (!M) return null;
  const ccy = T?.currency || 'KES';
  const range = T?.range;

  const sub = range
    ? `vs ${range.prev_from} → ${range.prev_to} · ${fmt(M.count)} varieties compared`
    : 'vs prior period';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-[18px] mb-[18px]">
      <Band title="Falling" sub={sub} rows={M.declines} ccy={ccy} icon="trending_down"
        tone="text-bad" empty="Nothing fell against the prior period" />
      <Band title="Rising" sub={sub} rows={M.gains} ccy={ccy} icon="trending_up"
        tone="text-good" empty="Nothing rose against the prior period" />
    </div>
  );
}
