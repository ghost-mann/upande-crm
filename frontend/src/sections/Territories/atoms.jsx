// Shared primitives for the territory map's dark panels.
//
// Every translucent colour here is an inline rgba string rather than a Tailwind
// opacity utility: `bg-x/55` resolves to nothing against this app's CSS-var
// colour tokens, so the modifier silently renders invisible.

export const GOLD = '#d9a514';
export const HAIRLINE = 'rgba(217, 165, 20, 0.28)';
export const SLAB = 'rgba(14, 14, 13, 0.92)';
export const TEXT = '#f4f3ef';
export const DIM = 'rgba(255, 255, 255, 0.52)';
export const FAINT = 'rgba(255, 255, 255, 0.28)';
export const BODY = 'rgba(255, 255, 255, 0.78)';
export const TRACK = 'rgba(255, 255, 255, 0.07)';

/** Short-form number, with an optional currency prefix. */
export function compact(n, currency) {
  const v = Number(n) || 0;
  const abs = Math.abs(v);
  const [scaled, suffix] =
    abs >= 1e9 ? [v / 1e9, 'B'] : abs >= 1e6 ? [v / 1e6, 'M'] : abs >= 1e3 ? [v / 1e3, 'K'] : [v, ''];
  const body = `${scaled.toFixed(suffix ? 1 : 0)}${suffix}`;
  return currency ? `${currency} ${body}` : body;
}

export function Row({ label, value, accent }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-[7px]">
      <span className="text-[10px] uppercase tracking-[0.18em]" style={{ color: DIM }}>
        {label}
      </span>
      <span
        className="font-mono text-[15px] tabular-nums"
        style={{ color: accent ? GOLD : TEXT }}
      >
        {value}
      </span>
    </div>
  );
}

/**
 * One headline figure, stacked label-over-value.
 *
 * The panel carries eight of these now. As full-width rows they consumed most
 * of the slab and left the detail below scrolling in a 130px slot, so they are
 * laid out two-up instead.
 */
export function Stat({ label, value, accent }) {
  return (
    <div className="min-w-0 py-[5px]">
      <div className="truncate text-[9px] uppercase tracking-[0.16em]" style={{ color: DIM }}>
        {label}
      </div>
      <div
        className="truncate font-mono text-[15px] leading-tight tabular-nums"
        style={{ color: accent ? GOLD : TEXT }}
        title={String(value)}
      >
        {value}
      </div>
    </div>
  );
}

export function Bar({ label, sub, value, max, currency }) {
  const pct = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0;
  return (
    <div className="py-[5px]">
      <div className="flex items-baseline justify-between gap-3">
        <span className="truncate text-[11px]" style={{ color: BODY }}>
          {label}
        </span>
        <span className="shrink-0 font-mono text-[11px] tabular-nums" style={{ color: DIM }}>
          {compact(value, currency)}
        </span>
      </div>
      {sub && (
        <div className="truncate text-[9px] uppercase tracking-[0.14em]" style={{ color: FAINT }}>
          {sub}
        </div>
      )}
      <div className="mt-1 h-[3px] w-full" style={{ background: TRACK }}>
        <div className="h-full" style={{ width: `${pct}%`, background: GOLD }} />
      </div>
    </div>
  );
}

export function Section({ title, children }) {
  return (
    <div className="mb-5">
      <div
        className="mb-2 pb-1 text-[9px] uppercase tracking-[0.28em]"
        style={{ color: FAINT, borderBottom: '1px solid rgba(255,255,255,0.08)' }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

export const Empty = ({ children }) => (
  <div className="py-1 text-[11px]" style={{ color: FAINT }}>
    {children}
  </div>
);

/** A caveat about the data above it — always visible, never a tooltip. */
export const Note = ({ children }) => (
  <div
    className="mt-2 pt-1.5 text-[10px] leading-relaxed"
    style={{ color: FAINT, borderTop: '1px dashed rgba(255,255,255,0.10)' }}
  >
    {children}
  </div>
);

/** Corner brackets — the one piece of pure theatre, and it costs four divs. */
export function Brackets() {
  const base = 'absolute h-3 w-3 pointer-events-none';
  const s = { borderColor: HAIRLINE };
  return (
    <>
      <div className={`${base} left-0 top-0 border-l border-t`} style={s} />
      <div className={`${base} right-0 top-0 border-r border-t`} style={s} />
      <div className={`${base} bottom-0 left-0 border-b border-l`} style={s} />
      <div className={`${base} bottom-0 right-0 border-b border-r`} style={s} />
    </>
  );
}
