import { fmt } from '@shared/utils';

export function KpiCard({ lbl, val, sub, suffix }) {
  return (
    <div className="rounded-md border border-line bg-surface px-[11px] py-2.5 relative overflow-hidden cursor-pointer hover:border-line-2 transition-colors">
      <div className="font-mono text-[8.5px] text-ink-3 uppercase tracking-[0.1em] font-semibold">{lbl}</div>
      <div className="font-mono text-[18px] font-semibold text-ink -tracking-[0.02em] mt-1 leading-[1.15]">
        {val}{suffix && <small className="text-[11px] text-ink-2 ml-0.5">{suffix}</small>}
      </div>
      {sub && <div className="font-mono text-[9.5px] text-ink-3 mt-0.5">{sub}</div>}
    </div>
  );
}

// items: [{lbl, val, sub?, suffix?}]
export function KpiRow({ items }) {
  return (
    <div className="grid grid-cols-6 gap-2 mb-3.5">
      {items.map((x) => <KpiCard key={x.lbl} {...x} val={x.val == null ? fmt(x.val) : x.val} />)}
    </div>
  );
}
