import { useRef, useState } from 'react';
import Icon from './Icon';
import { useStore } from '../store';
import { cn } from '@/lib/utils';
import { api } from '@shared/api';
import { openFrappe } from '@/lib/crm';
import FilterPopover from './FilterPopover';
import { Input } from '@/components/ui/input';

const PRESETS = [['7d', 'Last 7 days'], ['30d', 'Last 30 days'], ['90d', 'Last 90 days'], ['ytd', 'Year to date']];
const STATUS_LABEL = { idle: '—', loading: 'Loading', live: 'Live', partial: 'Partial', offline: 'Offline' };

export default function TopBar({ onSettings }) {
  const { search, setSearch, datePreset, dateFrom, dateTo, setDateRange, status, loadAll,
    searchResults, runSearch, customerFilter, setCustomerFilter, settings } = useStore();
  const [from, setFrom] = useState(dateFrom);
  const [to, setTo] = useState(dateTo);
  const [searchOpen, setSearchOpen] = useState(false);
  const [custRows, setCustRows] = useState(null);
  const deb = useRef();
  const custDeb = useRef();

  const label = datePreset === 'custom' ? `${dateFrom} → ${dateTo}`
    : (PRESETS.find((p) => p[0] === datePreset)?.[1] || 'Last 30 days');

  function onSearch(e) {
    const v = e.target.value;
    setSearch(v);
    clearTimeout(deb.current);
    if (v.trim().length >= 2) { setSearchOpen(true); deb.current = setTimeout(() => runSearch(v.trim()), 220); }
    else setSearchOpen(false);
  }

  async function custSearch(q) {
    clearTimeout(custDeb.current);
    if (q.trim().length < 2) { setCustRows(null); return; }
    custDeb.current = setTimeout(async () => {
      try {
        const r = await api('upande_crm.api.crm.crm_search', { query: q.trim() });
        setCustRows((r?.results || []).filter((x) => x.doctype === 'Customer'));
      } catch { setCustRows([]); }
    }, 220);
  }

  return (
    <header className="flex items-center gap-3 h-12 px-3.5 bg-maroon text-white shrink-0 relative z-20">
      <div className="flex items-center gap-2.5 pr-3.5 border-r border-white/15 h-full">
        <div className="w-7 h-7 bg-white text-maroon rounded-[5px] flex items-center justify-center font-mono font-bold text-xs">KR</div>
        <div className="flex flex-col leading-[1.1]">
          <b className="text-[13px] font-semibold -tracking-[0.01em]">CRM</b>
          <small className="font-mono text-[9px] opacity-70 tracking-[0.12em] uppercase mt-px">Karen Roses</small>
        </div>
      </div>

      <div className="flex-1 max-w-[480px] relative">
        <div className="h-[30px] bg-white/[0.12] rounded-[5px] flex items-center px-2.5 gap-2">
          <Icon name="search" className="text-[18px] opacity-80" />
          <input
            className="flex-1 bg-transparent border-none outline-none text-white text-xs placeholder:text-white/60"
            placeholder="Search leads, opportunities, customers…"
            value={search} onChange={onSearch}
            onFocus={() => search.trim().length >= 2 && setSearchOpen(true)}
            onBlur={() => setTimeout(() => setSearchOpen(false), 150)}
          />
          {search && <button onClick={() => { setSearch(''); setSearchOpen(false); }}><Icon name="close" className="text-[15px] opacity-80" /></button>}
        </div>
        {searchOpen && searchResults && (
          <div className="absolute top-[calc(100%+6px)] left-0 right-0 bg-surface text-ink border border-line rounded-md shadow-lg z-50 max-h-[360px] overflow-y-auto py-1">
            {searchResults.length ? searchResults.map((r) => (
              <div key={`${r.doctype}-${r.name}`} onMouseDown={() => openFrappe(r.doctype, r.name, settings.openInNewTab)}
                className="flex items-center gap-2.5 px-3 py-1.5 text-xs cursor-pointer hover:bg-hover">
                <Icon name={r.icon} className="text-[16px] text-ink-3" />
                <span className="flex-1 truncate">{r.label}</span>
                <span className="font-mono text-[9px] text-ink-3 uppercase">{r.doctype}</span>
              </div>
            )) : <div className="crm-empty py-4">No matches</div>}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        {/* Customer filter */}
        <FilterPopover
          width={280}
          trigger={
            <button className={cn('flex items-center gap-1.5 h-[30px] px-2.5 rounded-[5px] text-[11.5px] max-w-[180px]', customerFilter ? 'bg-white text-maroon font-medium' : 'bg-white/[0.12]')}>
              <Icon name="storefront" className="text-[15px]" />
              <span className="truncate">{customerFilter || 'All customers'}</span>
              <Icon name="expand_more" className="text-[14px]" />
            </button>
          }
        >
          {({ close }) => (
            <>
              <div className="flex items-center gap-2 border border-line rounded px-2 mb-1.5">
                <Icon name="search" className="text-[15px] text-ink-3" />
                <input autoFocus placeholder="Filter by customer…" onChange={(e) => custSearch(e.target.value)}
                  className="flex-1 h-8 bg-transparent outline-none text-xs" />
              </div>
              {customerFilter && (
                <div onClick={() => { setCustomerFilter(null); close(); }} className="flex items-center gap-2 px-2 py-1.5 text-xs text-bad cursor-pointer hover:bg-hover rounded">
                  <Icon name="close" className="text-[15px]" />Clear filter
                </div>
              )}
              <div className="max-h-[260px] overflow-y-auto">
                {custRows == null ? <div className="crm-empty py-3">Type to search</div>
                  : custRows.length ? custRows.map((r) => (
                    <div key={r.name} onClick={() => { setCustomerFilter(r.name); close(); }} className="px-2 py-1.5 text-xs cursor-pointer hover:bg-hover rounded">
                      <div className="truncate">{r.label}</div>
                      <div className="font-mono text-[9px] text-ink-3">{r.name}</div>
                    </div>
                  )) : <div className="crm-empty py-3">No customers</div>}
              </div>
            </>
          )}
        </FilterPopover>

        {/* Date range */}
        <FilterPopover
          width={260}
          trigger={
            <button className="flex items-center gap-1.5 h-[30px] px-2.5 bg-white/[0.12] rounded-[5px] text-[11.5px]">
              <Icon name="date_range" className="text-[16px]" />
              <span>{label}</span>
              <Icon name="expand_more" className="text-[14px]" />
            </button>
          }
        >
          {({ close }) => (
            <>
              <div className="grid gap-1">
                {PRESETS.map(([k, lbl]) => (
                  <button key={k} onClick={() => { setDateRange(k); close(); }}
                    className={cn('text-left text-xs px-2 py-1.5 rounded hover:bg-accent', datePreset === k && 'bg-maroon-soft text-maroon-text font-medium')}>{lbl}</button>
                ))}
              </div>
              <div className="border-t border-line mt-2 pt-2 grid gap-1.5">
                <label className="text-[10px] font-mono uppercase text-ink-3">Custom range</label>
                <div className="flex items-center gap-2 text-xs"><span className="w-9 text-ink-3">From</span><Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="h-7 text-xs" /></div>
                <div className="flex items-center gap-2 text-xs"><span className="w-9 text-ink-3">To</span><Input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="h-7 text-xs" /></div>
                <button onClick={() => { setDateRange('custom', { from, to }); close(); }} className="mt-1 h-7 rounded bg-maroon text-white text-xs font-medium">Apply custom range</button>
              </div>
            </>
          )}
        </FilterPopover>

        <div className={cn('flex items-center gap-1.5 px-2 py-1 rounded-[3px] font-mono text-[9.5px] font-medium tracking-[0.08em] uppercase', status === 'offline' ? 'bg-bad/80' : 'bg-white/[0.12]')}>
          <span className={cn('w-1.5 h-1.5 rounded-full', status === 'live' ? 'bg-emerald-300' : status === 'offline' ? 'bg-red-300' : 'bg-amber-300')} />
          {STATUS_LABEL[status] || '—'}
        </div>
        <button onClick={() => loadAll()} className="w-[30px] h-[30px] rounded-[5px] text-white/85 hover:bg-white/10 flex items-center justify-center" title="Refresh now">
          <Icon name="refresh" className="text-[18px]" />
        </button>
      </div>
    </header>
  );
}
