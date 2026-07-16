import { NAV } from '../nav';
import { useStore } from '../store';
import { cn } from '@/lib/utils';

// Sub-view tabs for the active section, styled to the UFD-modern reference
// `.tabs`/`.tab` (pill group, ink-gradient active). Driven by the same nav model
// the sidebar uses, so tabs and store stay in sync.
function subsFor(section) {
  for (const grp of NAV) {
    for (const it of grp.items) {
      if (it.section === section && it.subs) return it.subs;
    }
  }
  return null;
}

export default function SectionTabs() {
  const section = useStore((s) => s.section);
  const table = useStore((s) => s.table);
  const select = useStore((s) => s.select);

  const subs = subsFor(section);
  if (!subs || subs.length < 2) return null;
  const cur = table || subs[0].table;

  return (
    <div className="inline-flex gap-1 p-[5px] rounded-full bg-[rgba(10,10,10,0.04)] max-w-full overflow-x-auto mb-7">
      {subs.map((sub) => {
        const active = (sub.table || '') === (cur || '');
        return (
          <button
            key={sub.table || 'dash'}
            onClick={() => select(section, sub.table)}
            className={cn(
              'border-0 text-[13px] font-medium px-[18px] py-2.5 rounded-full inline-flex items-center gap-2 whitespace-nowrap transition-all',
              active
                ? 'bg-grad-ink text-white shadow-[0_4px_14px_rgba(10,10,10,0.20)]'
                : 'text-ink-4 hover:text-ink',
            )}
          >
            {sub.label}
          </button>
        );
      })}
    </div>
  );
}
