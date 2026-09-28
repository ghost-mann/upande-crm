import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import Icon from '../../components/Icon';
import { cn } from '@/lib/utils';

// A small slice of the real CRM, repainted by the draft theme before it is
// saved. The tokens come from the server's own derivation (crm_theme_preview),
// set as CSS variables on this wrapper only — so what you see here is exactly
// what Save will produce, and the rest of the app is untouched until then.
function vars(tokens) {
  const style = {};
  Object.entries(tokens || {}).forEach(([k, v]) => { style[`--${k}`] = String(v); });
  return style;
}

const BARS = [
  { h: 78, c: 'var(--gold)' }, { h: 54, c: 'var(--info)' }, { h: 92, c: 'var(--good)' }, { h: 36, c: 'var(--ink-4)' },
];

export default function ThemePreview({ tokens }) {
  return (
    <div style={{ ...vars(tokens), fontFamily: 'var(--f)' }}
      className="rounded-card border border-hairline bg-canvas p-4 text-ink shadow-card">
      <div className="text-[10px] uppercase tracking-[0.16em] text-ink-mute mb-3">Live preview</div>

      <div className="grid grid-cols-[112px_minmax(0,1fr)] gap-3">
        <div className="rounded-panel bg-surface border border-hairline p-2 flex flex-col gap-1">
          <div className="h-8 rounded-[var(--r-sm)] bg-[image:var(--nav-active)] bg-[color:var(--nav-active)] text-[color:var(--nav-active-fg)] text-[11.5px] font-medium flex items-center gap-1.5 px-2">
            <Icon name="dashboard" className="text-[14px]" />Overview
          </div>
          <div className="h-8 rounded-[var(--r-sm)] text-[11.5px] text-ink-4 flex items-center gap-1.5 px-2"><Icon name="person_add" className="text-[14px]" />Leads</div>
          <div className="h-8 rounded-[var(--r-sm)] text-[11.5px] text-ink-4 flex items-center gap-1.5 px-2 bg-hover"><Icon name="storefront" className="text-[14px]" />Customers</div>
        </div>

        <div className="min-w-0 flex flex-col gap-3">
          <div style={{ fontFamily: 'var(--display)' }} className="text-[20px] font-semibold leading-tight">Command Center</div>
          <div className="rounded-kpi bg-surface-2 border border-hairline px-4 py-3 shadow-card">
            <div className="text-[9.5px] text-ink-mute uppercase tracking-[0.16em] mb-1.5">Revenue</div>
            <div style={{ fontFamily: 'var(--mono)' }} className="text-[22px] leading-none font-semibold tabular-nums">KES 83.3M</div>
            <div className="text-[11px] text-ink-3 mt-1">1,429 orders</div>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 mt-3">
        <Button size="sm" className="rounded-full bg-primary text-primary-foreground hover:bg-primary/90 shadow-none">Save</Button>
        <Button size="sm" className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 shadow-none">New lead</Button>
        <Button size="sm" variant="outline" className="rounded-full border-line-2">Cancel</Button>
        <span className="bdg bg-gold-soft text-gold-text">Your price</span>
      </div>

      <div className="flex flex-wrap gap-1.5 mt-3">
        <span className="bdg bdg-good">Won</span>
        <span className="bdg bdg-warn">Pending</span>
        <span className="bdg bdg-bad">Lost</span>
        <span className="bdg bdg-info">Note</span>
      </div>

      <div className="rounded-card-in border border-hairline bg-surface mt-3 overflow-hidden text-[12px]">
        <div className="grid grid-cols-[1fr_auto] px-3 py-2 border-b border-line text-[9.5px] uppercase tracking-[0.14em] text-ink-mute bg-surface-2">
          <span>Customer</span><span>Amount</span>
        </div>
        <div className="grid grid-cols-[1fr_auto] px-3 py-2 border-b border-line bg-hover"><span>EFLOWERS B.V.</span><span style={{ fontFamily: 'var(--mono)' }}>KES 17.8M</span></div>
        <div className="grid grid-cols-[1fr_auto] px-3 py-2 bg-selected"><span>Bloomgate Exports</span><span style={{ fontFamily: 'var(--mono)' }}>KES 9.1M</span></div>
      </div>

      <div className="flex items-end gap-2 h-[70px] mt-3 px-1">
        {BARS.map((b, i) => (
          <div key={i} className={cn('flex-1 rounded-t-[3px]')} style={{ height: `${b.h}%`, background: b.c }} />
        ))}
      </div>

      <div className="mt-3">
        <Input placeholder="Search customers…" className="h-9 bg-surface" />
      </div>
      <div className="mt-2 text-[11px] text-ink-mute">Secondary text looks like this.</div>
    </div>
  );
}
