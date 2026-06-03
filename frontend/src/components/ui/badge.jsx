import * as React from 'react';
import { cva } from 'class-variance-authority';
import { cn } from '@/lib/utils';

// Mirrors the source `.bdg` rule: mono 9px, uppercase, soft status colors.
const badgeVariants = cva(
  'inline-block font-mono text-[9px] font-semibold uppercase tracking-[0.04em] px-1.5 py-0.5 rounded-[3px]',
  {
    variants: {
      tone: {
        neutral: 'bg-surface-3 text-ink-2',
        good: 'bg-good-soft text-good',
        warn: 'bg-warn-soft text-warn',
        bad: 'bg-bad-soft text-bad',
        info: 'bg-info-soft text-info',
        maroon: 'bg-maroon-soft text-maroon-text',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
);

function Badge({ className, tone, ...props }) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

// Map an ERPNext/CRM status string → badge tone (ported from statusBadge()).
export function statusTone(s) {
  const k = String(s || '').toLowerCase();
  if (k.includes('complet') || k === 'won' || k === 'converted' || k === 'paid' || k === 'closed' || k === 'active') return 'good';
  if (k === 'open' || k === 'replied' || k === 'in progress' || k.includes('negoti')) return 'info';
  if (k === 'draft' || k === 'submitted' || k === 'pending' || k === 'on hold' || k.includes('qualif')) return 'warn';
  if (k === 'lost' || k === 'cancelled' || k === 'do not contact' || k === 'rejected' || k === 'overdue') return 'bad';
  return 'neutral';
}

export { Badge, badgeVariants };
