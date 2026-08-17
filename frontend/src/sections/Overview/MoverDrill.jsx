import { fmt, fmtMoney, fmtMoneyCompact } from '@shared/utils';
import { useStore } from '../../store';
import { MoneyDelta, Delta } from './parts';
import { AreaTrendChart } from '../../charts/Charts';
import Icon from '../../components/Icon';

// Why a flower or a salesperson moved.
//
// The claim this panel makes is arithmetic, not inference: a revenue change is
// exactly its volume effect plus its price effect. Both are shown, the larger is
// named as the driver, and the accounts behind it are ranked — so "Giselle
// stopped selling so high" resolves into "fewer stems, mostly from two accounts,
// under one rep" instead of a shrug.

function Stat({ label, value, sub, tone = '' }) {
  return (
    <div className="px-4 py-3 rounded-2xl bg-surface-3">
      <div className="text-[10px] uppercase tracking-[0.14em] text-ink-mute font-medium mb-1.5">{label}</div>
      <div className={`text-[19px] font-semibold tabular-nums leading-none ${tone || 'text-ink'}`}>{value}</div>
      {sub && <div className="text-[11.5px] text-ink-mute mt-1.5">{sub}</div>}
    </div>
  );
}

// The volume/price split as a single bar: which half of the change came from
// selling fewer stems, and which from realising a different price.
function Split({ volume, price, ccy }) {
  const av = Math.abs(volume);
  const ap = Math.abs(price);
  const total = av + ap || 1;
  const vPct = (av / total) * 100;
  return (
    <div>
      <div className="flex h-[26px] rounded-lg overflow-hidden gap-[2px] bg-surface-3">
        <div className="grid place-items-center transition-all" title="Volume effect"
          style={{ width: `${vPct}%`, background: '#3268c4' }}>
          {vPct > 22 && <span className="text-[10.5px] font-semibold text-white">Volume</span>}
        </div>
        <div className="grid place-items-center transition-all flex-1" title="Price effect"
          style={{ background: '#c69210' }}>
          {100 - vPct > 22 && <span className="text-[10.5px] font-semibold text-white">Price</span>}
        </div>
      </div>
      <div className="flex justify-between mt-2 text-[12px]">
        <span className="text-ink-2">
          Volume <MoneyDelta value={volume} ccy={ccy} />
        </span>
        <span className="text-ink-2">
          Price <MoneyDelta value={price} ccy={ccy} />
        </span>
      </div>
    </div>
  );
}

function ContribList({ title, rows, ccy, empty, stopped, started }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.14em] text-ink-mute font-medium mb-2">{title}</div>
      {rows?.length ? (
        <div>
          {rows.map((r) => (
            <div key={r.key} className="flex items-center gap-3 py-2 border-b border-hairline last:border-0">
              <span className="flex-1 min-w-0">
                <span className="block text-[13px] text-ink font-medium truncate" title={r.label}>{r.label}</span>
                <span className="block text-[11.5px] text-ink-mute">
                  {r.stopped ? stopped : r.started ? started
                    : `${fmtMoneyCompact(r.prev, ccy)} → ${fmtMoneyCompact(r.amount, ccy)}`}
                </span>
              </span>
              <MoneyDelta value={r.delta} ccy={ccy} className="text-[13px] shrink-0" />
            </div>
          ))}
        </div>
      ) : <div className="text-[12.5px] text-ink-mute py-3">{empty}</div>}
    </div>
  );
}

// Per dimension: [down heading, up heading, gone, appeared].
//
// The verb has to follow the dimension. A rep who no longer appears did not
// "stop buying" — the same word against the wrong noun makes a correct number
// read as a bug.
const DIM_COPY = {
  customer: ['Accounts that bought less', 'Accounts that bought more',
             'stopped buying this', 'new account this period'],
  rep: ['Reps who sold less', 'Reps who sold more',
        'sold none this period', 'first sold it this period'],
  flower: ['Varieties they sold less of', 'Varieties they sold more of',
           'sold none this period', 'new to their book'],
};

export default function MoverDrill() {
  const mover = useStore((s) => s.mover);
  const detail = useStore((s) => s.moverDetail);
  const loading = useStore((s) => s.moverLoading);
  const close = useStore((s) => s.closeMover);

  if (!mover) return null;
  const ccy = detail?.currency || 'KES';
  const t = detail?.totals;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4"
      onClick={close}>
      <div className="flex flex-col w-[860px] max-w-[96vw] max-h-[92vh] rounded-2xl shadow-2xl
                      border border-hairline bg-surface overflow-hidden"
        onClick={(e) => e.stopPropagation()}>
        <div className="h-11 shrink-0 bg-grad-ink text-white flex items-center gap-1 pl-4 pr-1.5">
          <span className="text-[14px] font-semibold truncate flex-1">
            {mover.kind === 'flower' ? 'Flower' : 'Salesperson'} · {detail?.label || mover.label}
          </span>
          <button onClick={close} title="Close"
            className="w-7 h-7 rounded flex items-center justify-center hover:bg-white/15">
            <Icon name="close" className="!text-[18px]" />
          </button>
        </div>

        <div className="overflow-y-auto px-6 py-5">
          {loading && <div className="crm-empty">Working out what moved…</div>}
          {!loading && detail?.error && (
            <div className="crm-empty">Could not load the explanation</div>
          )}
          {!loading && t && (
            <>
              {/* The headline claim */}
              <div className="mb-5">
                <div className="flex items-baseline gap-3 flex-wrap">
                  <span className="text-[28px] font-semibold text-ink tabular-nums leading-none">
                    <MoneyDelta value={t.delta} ccy={ccy} />
                  </span>
                  <Delta pct={t.delta_pct} prev={t.prev} className="!text-[14px]" />
                  <span className="text-[12.5px] text-ink-mute">
                    {fmtMoney(t.prev, ccy)} → {fmtMoney(t.amount, ccy)}
                  </span>
                </div>
                <div className="text-[12.5px] text-ink-3 mt-2">
                  {detail.range.from} → {detail.range.to}, against{' '}
                  {detail.range.prev_from} → {detail.range.prev_to}
                  {mover.kind === 'flower' && ' · line value, excludes order-level charges'}
                </div>
              </div>

              {/* What actually changed */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
                <Stat label="Stems" value={fmt(Math.round(t.qty))}
                  sub={`was ${fmt(Math.round(t.prev_qty))} · ${t.qty_delta_pct > 0 ? '+' : ''}${t.qty_delta_pct}%`} />
                <Stat label={`Price / stem`} value={fmtMoneyCompact(t.rate, ccy)}
                  sub={`was ${fmtMoneyCompact(t.prev_rate, ccy)}`} />
                <Stat label="Orders" value={fmt(t.orders)} sub={`was ${fmt(t.prev_orders)}`} />
                <Stat label="Driver" value={t.driver === 'volume' ? 'Volume' : 'Price'}
                  sub={t.driver === 'volume' ? 'stems moved it' : 'realised rate moved it'} />
              </div>

              <div className="mb-6">
                <div className="text-[11px] uppercase tracking-[0.14em] text-ink-mute font-medium mb-2">
                  What explains the change
                </div>
                <Split volume={t.volume_effect} price={t.price_effect} ccy={ccy} />
                <div className="text-[11.5px] text-ink-mute mt-2">
                  Volume and price sum to the whole change by construction — this is the
                  change decomposed, not an estimate of it.
                </div>
              </div>

              {/* Who moved */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5 mb-6">
                {Object.entries(detail.contributions || {}).map(([dim, c]) => {
                  const [down, up, gone, appeared] = DIM_COPY[dim] || [dim, dim, '', ''];
                  return [
                    <ContribList key={`${dim}-down`} title={down} rows={c.down} ccy={ccy}
                      stopped={gone} started={appeared} empty="Nothing down here" />,
                    <ContribList key={`${dim}-up`} title={up} rows={c.up} ccy={ccy}
                      stopped={gone} started={appeared} empty="Nothing up here" />,
                  ];
                })}
              </div>

              {/* Its own history, so a seasonal trough is not read as a lost account */}
              {detail.monthly?.length > 1 && (
                <div className="mb-5">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-ink-mute font-medium mb-1">
                    Monthly history
                  </div>
                  <div className="text-[11.5px] text-ink-mute mb-2">
                    The last {detail.monthly.length} months, so a seasonal dip reads as one
                  </div>
                  <div className="h-[150px] relative">
                    <AreaTrendChart labels={detail.monthly.map((m) => m.label)}
                      data={detail.monthly.map((m) => m.amount)} />
                  </div>
                </div>
              )}

              {detail.year_ago ? (
                <div className="text-[12.5px] text-ink-3 border-t border-hairline pt-3">
                  Same window a year earlier: {fmtMoney(detail.year_ago.amount, ccy)}{' '}
                  <span className="text-ink-mute">
                    (invoiced — a different measure from the order values above, and the only
                    one reaching that far back)
                  </span>
                </div>
              ) : (
                <div className="text-[12.5px] text-ink-mute border-t border-hairline pt-3">
                  No comparable window a year earlier — sales history on this site does not
                  reach back that far.
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
