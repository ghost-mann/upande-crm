import { fmt } from '@shared/utils';

// KPI card — matches the UFD-modern reference .kpi exactly: 44px value, uppercase
// tracked label, optional unit + trend chip, subtle hover lift. Not interactive.
// `compact` shrinks the value type and tightens the padding, for tiles holding a
// long money string ("KES 638.1M") in a narrow column — at the default size those
// clip to "KES 63…", which is worse than a smaller number.
export function KpiCard({ lbl, val, sub, suffix, chip, chipTone = '', compact = false }) {
  return (
    <div className={`rounded-[20px] bg-surface-2 border border-hairline ${compact ? 'px-[18px] py-6' : 'px-[26px] py-7'} relative shadow-card transition-all duration-200 hover:-translate-y-[3px] hover:shadow-hover min-w-0`}>
      <div className={`${compact ? 'text-[10px]' : 'text-[11px]'} text-ink-mute uppercase tracking-[0.16em] font-medium mb-3.5 truncate`} title={lbl}>{lbl}</div>
      <div className={`${compact ? 'text-[clamp(1.25rem,1.6vw,1.6rem)]' : 'text-[clamp(1.7rem,2.1vw,2.2rem)]'} leading-none font-semibold text-ink -tracking-[0.03em] tabular-nums whitespace-nowrap overflow-hidden text-ellipsis`}>
        {val}{suffix && <small className="text-[18px] text-ink-mute ml-1 font-medium tracking-normal">{suffix}</small>}
      </div>
      {sub && <div className="text-[13px] text-ink-mute mt-1.5">{sub}</div>}
      {chip && <div className={`k-trend ${chipTone}`}>{chip}</div>}
    </div>
  );
}

// items: [{lbl, val, sub?, suffix?}]
export function KpiRow({ items }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-[18px] mb-6">
      {items.map((x) => <KpiCard key={x.lbl} {...x} val={x.val == null ? fmt(x.val) : x.val} />)}
    </div>
  );
}
