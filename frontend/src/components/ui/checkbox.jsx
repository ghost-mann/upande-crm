import { cn } from '@/lib/utils';

// Native checkbox, styled. Deliberately NOT @radix-ui/react-checkbox: every
// library added here lands in the single `vendor` chunk, and vite.config.js
// documents that growing/splitting that chunk has caused blank-screen crashes.
export function Checkbox({ checked, onCheckedChange, label, className, disabled }) {
  return (
    <label
      className={cn(
        'inline-flex items-center gap-2 text-[13px] text-ink-2 select-none',
        disabled ? 'opacity-50' : 'cursor-pointer',
        className,
      )}
    >
      <input
        type="checkbox"
        checked={!!checked}
        disabled={disabled}
        onChange={(e) => onCheckedChange?.(e.target.checked)}
        className="h-3.5 w-3.5 rounded border-input accent-[var(--gold)] cursor-pointer"
      />
      {label}
    </label>
  );
}
