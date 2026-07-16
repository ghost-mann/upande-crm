import { fmt } from '@shared/utils';

// KPI card — matches the UFD-modern reference .kpi exactly: 44px value, uppercase
// tracked label, optional unit + trend chip, subtle hover lift. Not interactive.
export function KpiCard({ lbl, val, sub, suffix, chip, chipTone = '' }) {
  return (
    <div className="rounded-[20px] bg-surface-2 border border-hairline px-[26px] py-7 relative shadow-card transition-all duration-200 hover:-translate-y-[3px] hover:shadow-hover min-w-0">
      <div className="text-[11px] text-ink-mute uppercase tracking-[0.16em] font-medium mb-3.5 truncate">{lbl}</div>
      <div className="text-[clamp(1.9rem,2.4vw,2.6rem)] leading-none font-semibold text-ink -tracking-[0.03em] tabular-nums whitespace-nowrap overflow-hidden text-ellipsis">
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
