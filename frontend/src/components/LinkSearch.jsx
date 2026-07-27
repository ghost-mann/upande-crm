import { useEffect, useRef, useState } from 'react';
import { api } from '@shared/api';
import { cn } from '@/lib/utils';
import Icon from './Icon';

// Debounced combobox over Frappe's whitelisted link search. Used for event
// participants, task references, and record pickers — and reused by the WhatsApp
// section for contact lookup, so keep it generic (no CRM-specific assumptions).
export default function LinkSearch({
  doctype, value, onChange, placeholder = 'Search…', className, disabled, filters,
}) {
  const [q, setQ] = useState('');
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0);
  const box = useRef(null);

  useEffect(() => {
    function onDoc(e) { if (box.current && !box.current.contains(e.target)) setOpen(false); }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  useEffect(() => {
    if (!open || !doctype) return;
    let dead = false;
    const t = setTimeout(async () => {
      try {
        const args = { doctype, txt: q, page_length: 10 };
        if (filters) args.filters = JSON.stringify(filters);
        const r = await api('frappe.desk.search.search_link', args);
        if (dead) return;
        setRows(Array.isArray(r) ? r : (r?.results || []));
        setHi(0);
      } catch {
        if (!dead) setRows([]);
      }
    }, 250);
    return () => { dead = true; clearTimeout(t); };
  }, [q, doctype, open, filters]);

  function pick(r) {
    onChange?.(r.value, r);
    setQ('');
    setOpen(false);
  }

  function onKey(e) {
    if (!open) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setHi((h) => Math.min(h + 1, rows.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHi((h) => Math.max(h - 1, 0)); }
    else if (e.key === 'Enter' && rows[hi]) { e.preventDefault(); pick(rows[hi]); }
    else if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); }
  }

  return (
    <div className={cn('relative', className)} ref={box}>
      <div className="flex items-center gap-1.5 rounded-md border border-input px-2.5 h-9">
        <Icon name="search" className="text-[15px] text-ink-mute shrink-0" />
        <input
          disabled={disabled || !doctype}
          value={open ? q : (value || '')}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKey}
          placeholder={doctype ? placeholder : 'Pick a type first'}
          className="flex-1 bg-transparent outline-none text-sm min-w-0"
        />
        {value && !open && (
          <button type="button" onClick={() => onChange?.('', null)} className="text-ink-3 hover:text-bad shrink-0" title="Clear">
            <Icon name="close" className="text-[15px]" />
          </button>
        )}
      </div>
      {open && rows.length > 0 && (
        <div className="absolute z-[70] mt-1 w-full max-h-60 overflow-y-auto rounded-md border border-line bg-surface shadow-lg">
          {rows.map((r, i) => (
            <button
              type="button"
              key={r.value}
              onMouseEnter={() => setHi(i)}
              onClick={() => pick(r)}
              className={cn('w-full text-left px-3 py-2 text-[13px]', i === hi && 'bg-hover')}
            >
              <div className="text-ink truncate">{r.value}</div>
              {r.description && <div className="text-[11px] text-ink-mute truncate">{r.description}</div>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
