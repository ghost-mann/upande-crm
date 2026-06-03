import { cn } from '@/lib/utils';

// Material Symbols icon (matches the source page's iconography).
export default function Icon({ name, className, style }) {
  return (
    <span className={cn('material-symbols-outlined', className)} style={style}>
      {name}
    </span>
  );
}
