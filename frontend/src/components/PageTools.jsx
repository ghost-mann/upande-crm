import { useState } from 'react';
import Icon from './Icon';
import { useStore } from '../store';
import { cn } from '@/lib/utils';
import FilterPopover from './FilterPopover';
import { Input } from '@/components/ui/input';

const PRESETS = [['7d', 'Last 7 days'], ['30d', 'Last 30 days'], ['90d', 'Last 90 days'], ['ytd', 'Year to date']];
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const short = (s) => { if (!s) return '—'; const [y, m, d] = String(s).split('-'); return `${+d} ${MON[+m - 1]} ${String(y).slice(2)}`; };

// Page-header date range (from → to) + refresh. Drives every section's content.
export default function PageTools() {
  const { datePreset, dateFrom, dateTo, setDateRange, loadAll } = useStore();
  const [from, setFrom] = useState(dateFrom);
  const [to, setTo] = useState(dateTo);
  const [err, setErr] = useState('');

  function applyCustom(close) {
    if (!from || !to) { setErr('Pick both a “from” and a “to” date.'); return; }
    if (from > to) { setErr('“From” must be on or before “To”.'); return; }
    setErr('');
    setDateRange('custom', { from, to });
    close();
  }

  return (
    <div className="flex items-center gap-2.5 shrink-0">
      <FilterPopover
        width={288}
        trigger={
          <button className="datepill" title="Date range — affects all content">
            <Icon name="date_range" className="text-[15px] text-ink-mute" />
            <span>{short(dateFrom)} → {short(dateTo)}</span>
            <Icon name="expand_more" className="text-[15px] text-ink-mute" />
          </button>
        }
      >
        {({ close }) => (
          <div className="grid gap-2">
            <div className="text-[10px] uppercase tracking-wide text-ink-mute font-medium">Date range</div>
            <div className="flex items-center gap-2 text-[13px]"><span className="w-9 text-ink-mute">From</span><Input type="date" value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} className="h-8 text-[13px]" /></div>
            <div className="flex items-center gap-2 text-[13px]"><span className="w-9 text-ink-mute">To</span><Input type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} className="h-8 text-[13px]" /></div>
            {err && <div className="text-[11px] text-bad">{err}</div>}
            <button onClick={() => applyCustom(close)} className="h-9 rounded-full bg-ink text-white text-[12px] font-medium hover:bg-ink-2 transition-colors">Apply range</button>
            <div className="border-t border-hairline mt-1 pt-2 grid gap-1">
              <div className="text-[10px] uppercase tracking-wide text-ink-mute font-medium mb-0.5">Quick ranges</div>
              {PRESETS.map(([k, lbl]) => (
                <button key={k} onClick={() => { setDateRange(k); close(); }}
                  className={cn('text-left text-[13px] px-2.5 py-2 rounded-xl hover:bg-hover', datePreset === k && 'bg-gold-soft text-gold-text font-medium')}>{lbl}</button>
              ))}
            </div>
          </div>
        )}
      </FilterPopover>
      <button className="iconbtn" aria-label="Refresh now" title="Refresh now" onClick={() => loadAll()}>
        <Icon name="refresh" className="text-[18px]" />
      </button>
    </div>
  );
}
