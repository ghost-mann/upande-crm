import { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';

// Lightweight popover for filter UIs that contain inputs. Unlike a Radix
// DropdownMenu it does NOT capture typeahead/keyboard, so inputs work normally.
export default function FilterPopover({ trigger, children, align = 'end', width = 260, className }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function onDoc(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    function onEsc(e) { if (e.key === 'Escape') setOpen(false); }
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onEsc);
    return () => { document.removeEventListener('mousedown', onDoc); document.removeEventListener('keydown', onEsc); };
  }, []);

  return (
    <div className="relative" ref={ref}>
      <div onClick={() => setOpen((o) => !o)}>{trigger}</div>
      {open && (
        <div
          className={cn(
            'absolute top-[calc(100%+6px)] bg-surface text-ink border border-line rounded-md shadow-lg z-50 p-2.5',
            align === 'end' ? 'right-0' : 'left-0',
            className,
          )}
          style={{ width }}
        >
          {typeof children === 'function' ? children({ close: () => setOpen(false) }) : children}
        </div>
      )}
    </div>
  );
}
