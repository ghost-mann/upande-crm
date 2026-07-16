import { useRef, useState } from 'react';
import Icon from './Icon';
import { useStore } from '../store';
import { cn } from '@/lib/utils';
import { api, getBoot } from '@shared/api';
import { openFrappe } from '@/lib/crm';
import FilterPopover from './FilterPopover';
import { UPANDE_LOGO } from '@/lib/logo';

const STATUS_LABEL = { idle: '—', loading: 'Loading', live: 'Live', partial: 'Partial', offline: 'Offline' };

export default function TopBar() {
  const { search, setSearch, status, searchResults, runSearch,
    customerFilter, setCustomerFilter, settings } = useStore();
  const [searchOpen, setSearchOpen] = useState(false);
  const [custRows, setCustRows] = useState(null);
  const deb = useRef();
  const custDeb = useRef();
  const boot = getBoot();

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

  const pill = 'flex items-center gap-1.5 h-9 px-3 rounded-full text-[12px] transition-colors';

  return (
    <header className="flex items-center gap-3 h-16 px-5 md:px-8 bg-surface text-ink sticky top-0 z-30 border-b border-hairline">
      <button onClick={() => { window.location.href = '/app'; }} title="Back to Desk"
        className="flex items-center gap-3 pr-4 mr-1 border-r border-hairline h-9 group">
        <img src={UPANDE_LOGO} alt="Upande" className="h-[26px] w-auto transition-transform group-hover:scale-[1.04]" />
        <div className="flex flex-col leading-[1.15] text-left">
          <b className="text-[15px] font-semibold -tracking-[0.02em]">CRM</b>
          <small className="text-[9.5px] text-ink-mute tracking-[0.16em] uppercase font-medium mt-px">{boot.brandName}</small>
        </div>
      </button>

      <div className="flex-1 max-w-[520px] relative">
        <div className="h-9 bg-[var(--hover)] rounded-full flex items-center px-3.5 gap-2">
          <Icon name="search" className="text-[18px] text-ink-mute" />
          <input
            className="flex-1 bg-transparent border-none outline-none text-ink text-[13px] placeholder:text-ink-mute"
            placeholder="Search leads, opportunities, customers…"
            value={search} onChange={onSearch}
            onFocus={() => search.trim().length >= 2 && setSearchOpen(true)}
            onBlur={() => setTimeout(() => setSearchOpen(false), 150)}
            aria-label="Search CRM"
          />
          {search && <button aria-label="Clear search" onClick={() => { setSearch(''); setSearchOpen(false); }}><Icon name="close" className="text-[16px] text-ink-mute hover:text-ink" /></button>}
        </div>
        {searchOpen && searchResults && (
          <div className="absolute top-[calc(100%+8px)] left-0 right-0 bg-surface text-ink border border-hairline rounded-2xl shadow-hover z-50 max-h-[360px] overflow-y-auto p-1.5">
            {searchResults.length ? searchResults.map((r) => (
              <button key={`${r.doctype}-${r.name}`} onMouseDown={() => openFrappe(r.doctype, r.name, settings.openInNewTab)}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-[13px] cursor-pointer hover:bg-hover rounded-xl text-left">
                <Icon name={r.icon} className="text-[17px] text-ink-mute" />
                <span className="flex-1 truncate">{r.label}</span>
                <span className="text-[9.5px] text-ink-mute uppercase tracking-wide">{r.doctype}</span>
              </button>
            )) : <div className="crm-empty py-4">No matches</div>}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 ml-auto">
        {/* Customer filter */}
        <FilterPopover
          width={288}
          trigger={
            <button className={cn(pill, 'max-w-[190px]', customerFilter ? 'bg-gold-soft text-gold-text font-medium' : 'bg-[var(--hover)] text-ink-2 hover:text-ink')}>
              <Icon name="storefront" className="text-[16px]" />
              <span className="truncate">{customerFilter || 'All customers'}</span>
              <Icon name="expand_more" className="text-[15px]" />
            </button>
          }
        >
          {({ close }) => (
            <>
              <div className="flex items-center gap-2 border border-line rounded-xl px-2.5 mb-2">
                <Icon name="search" className="text-[15px] text-ink-mute" />
                <input autoFocus placeholder="Filter by customer…" onChange={(e) => custSearch(e.target.value)}
                  className="flex-1 h-9 bg-transparent outline-none text-[13px]" aria-label="Filter by customer" />
              </div>
              {customerFilter && (
                <button onClick={() => { setCustomerFilter(null); close(); }} className="w-full flex items-center gap-2 px-2.5 py-2 text-[13px] text-bad cursor-pointer hover:bg-hover rounded-xl text-left">
                  <Icon name="close" className="text-[15px]" />Clear filter
                </button>
              )}
              <div className="max-h-[260px] overflow-y-auto">
                {custRows == null ? <div className="crm-empty py-3">Type to search</div>
                  : custRows.length ? custRows.map((r) => (
                    <button key={r.name} onClick={() => { setCustomerFilter(r.name); close(); }} className="w-full px-2.5 py-2 text-[13px] cursor-pointer hover:bg-hover rounded-xl text-left">
                      <div className="truncate">{r.label}</div>
                      <div className="text-[10px] text-ink-mute">{r.name}</div>
                    </button>
                  )) : <div className="crm-empty py-3">No customers</div>}
              </div>
            </>
          )}
        </FilterPopover>

        <div className={cn('flex items-center gap-1.5 px-2.5 h-9 rounded-full text-[10px] font-semibold tracking-[0.08em] uppercase', status === 'offline' ? 'bg-bad-soft text-bad' : 'bg-[var(--hover)] text-ink-mute')}>
          <span className={cn('w-1.5 h-1.5 rounded-full', status === 'live' ? 'bg-good' : status === 'offline' ? 'bg-bad' : 'bg-gold')} />
          {STATUS_LABEL[status] || '—'}
        </div>
      </div>
    </header>
  );
}
