import * as React from 'react';
import { cn } from '@/lib/utils';

const Card = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('rounded-md border border-line bg-surface text-card-foreground overflow-hidden', className)} {...props} />
));
Card.displayName = 'Card';

const CardHeader = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('flex items-center justify-between gap-2.5 px-3.5 py-2.5 border-b border-line', className)} {...props} />
));
CardHeader.displayName = 'CardHeader';

const CardTitle = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('text-xs font-semibold text-ink leading-none', className)} {...props} />
));
CardTitle.displayName = 'CardTitle';

const CardSub = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('mt-1 text-[10px] text-ink-3', className)} {...props} />
));
CardSub.displayName = 'CardSub';

const CardContent = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('p-3.5', className)} {...props} />
));
CardContent.displayName = 'CardContent';

export { Card, CardHeader, CardTitle, CardSub, CardContent };
