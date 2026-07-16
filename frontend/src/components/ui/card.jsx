import * as React from 'react';
import { cn } from '@/lib/utils';

const Card = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('rounded-[24px] border border-hairline bg-surface-2 text-card-foreground overflow-hidden shadow-card', className)} {...props} />
));
Card.displayName = 'Card';

const CardHeader = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('flex items-center justify-between gap-6 px-8 pt-7 pb-5', className)} {...props} />
));
CardHeader.displayName = 'CardHeader';

const CardTitle = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('text-[18px] font-semibold text-ink -tracking-[0.02em] leading-tight', className)} {...props} />
));
CardTitle.displayName = 'CardTitle';

const CardSub = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('mt-1.5 text-[12px] text-ink-mute font-medium', className)} {...props} />
));
CardSub.displayName = 'CardSub';

const CardContent = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('px-8 pb-7', className)} {...props} />
));
CardContent.displayName = 'CardContent';

export { Card, CardHeader, CardTitle, CardSub, CardContent };
