import { useStore, RANGE_PRESETS } from '../../store';
import { cn } from '@/lib/utils';

// Analytics needs a wider window than the dashboards — a funnel over 30 days on a
// pipeline this size is single digits — so the range control is put in front of the
// user here rather than left in the header pill they may not think to change.
// Bound to the same store range, so the two never disagree.
export default function RangePicker() {
  const preset = useStore((s) => s.datePreset);
  const setDateRange = useStore((s) => s.setDateRange);
  const from = useStore((s) => s.dateFrom);
  const to = useStore((s) => s.dateTo);

  return (
    <div className="flex items-center gap-3 flex-wrap mb-5">
      <div className="inline-flex gap-1 p-[5px] rounded-full bg-[rgba(10,10,10,0.04)] max-w-full overflow-x-auto">
        {RANGE_PRESETS.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setDateRange(key)}
            className={cn(
              'border-0 text-[12.5px] font-medium px-3.5 py-2 rounded-full whitespace-nowrap transition-all',
              preset === key
                ? 'bg-grad-ink text-white shadow-[0_4px_14px_rgba(10,10,10,0.20)]'
                : 'text-ink-4 hover:text-ink',
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <span className="text-[11.5px] text-ink-mute">
        {preset === 'custom' ? `custom · ${from} → ${to}` : `${from} → ${to}`}
      </span>
    </div>
  );
}
