import { fmtMoneyCompact } from '@shared/utils';

// Shared pieces for the command centre. Kept here rather than in components/ —
// they encode Overview-specific reading rules (a decline is red, "stopped" is not
// "-100%") that no other section should silently inherit.

// A signed percentage. `invert` is for measures where up is bad.
export function Delta({ pct, prev, invert = false, className = '' }) {
  if (prev === 0 || prev == null) {
    // No base to divide by. "+0%" would be a lie and "∞" is not useful, so say
    // what is actually true.
    return <span className={`text-[11.5px] text-ink-mute font-medium ${className}`}>no prior</span>;
  }
  const up = pct > 0;
  const good = invert ? !up : up;
  const tone = pct === 0 ? 'text-ink-mute' : good ? 'text-good' : 'text-bad';
  return (
    <span className={`text-[11.5px] font-semibold tabular-nums ${tone} ${className}`}>
      {up ? '+' : ''}{pct}%
    </span>
  );
}

// A money delta with its own sign, for the movers band.
export function MoneyDelta({ value, ccy, className = '' }) {
  const tone = value > 0 ? 'text-good' : value < 0 ? 'text-bad' : 'text-ink-mute';
  return (
    <span className={`tabular-nums font-semibold ${tone} ${className}`}>
      {value > 0 ? '+' : value < 0 ? '−' : ''}{fmtMoneyCompact(Math.abs(value), ccy)}
    </span>
  );
}

// Segmented control. Filters sit in one row above the chart they filter.
export function Toggle({ value, onChange, options, size = 'md' }) {
  const pad = size === 'sm' ? 'px-2.5 py-1 text-[11px]' : 'px-3 py-1.5 text-[12px]';
  return (
    <div className="inline-flex rounded-full bg-[rgba(10,10,10,0.04)] p-[3px] gap-[3px]">
      {options.map((o) => (
        <button key={o.value} type="button" onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          className={`${pad} rounded-full font-medium transition-all ${
            value === o.value
              ? 'bg-surface-2 text-ink shadow-card'
              : 'text-ink-mute hover:text-ink-2'}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

// A band heading, matching SalesBand's.
export function BandHead({ title, note, children }) {
  return (
    <div className="flex items-baseline gap-3 mb-3.5 flex-wrap">
      <h2 className="text-[13px] uppercase tracking-[0.18em] text-ink-4 font-medium">{title}</h2>
      {note && <span className="text-[12px] text-ink-mute">{note}</span>}
      {children && <div className="ml-auto">{children}</div>}
    </div>
  );
}

// Tabs within a card.
export function CardTabs({ value, onChange, tabs }) {
  return (
    <div className="flex gap-1 flex-wrap">
      {tabs.map((t) => (
        <button key={t.value} type="button" onClick={() => onChange(t.value)}
          aria-pressed={value === t.value}
          className={`px-3 py-1.5 rounded-full text-[12px] font-medium transition-all ${
            value === t.value
              ? 'bg-ink text-surface'
              : 'text-ink-mute hover:text-ink-2 hover:bg-[rgba(10,10,10,0.04)]'}`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}
