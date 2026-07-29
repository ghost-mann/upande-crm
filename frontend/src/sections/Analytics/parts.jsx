import { fmt } from '@shared/utils';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import Icon from '../../components/Icon';

// Shared building blocks for the Analytics tabs.

export function Panel({ title, sub, aside, children, className }) {
  return (
    <Card className={className}>
      <CardHeader>
        <div><CardTitle>{title}</CardTitle>{sub && <CardSub>{sub}</CardSub>}</div>
        {aside}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

// A note about the data itself, not the numbers. Used where a metric is missing
// because the field is not filled in — saying so beats drawing a flat line.
export function DataNote({ tone = 'warn', children }) {
  const cls = tone === 'bad' ? 'text-bad' : tone === 'info' ? 'text-ink-2' : 'text-warn';
  return (
    <div className={`flex items-start gap-2 text-[12px] ${cls} mt-3`}>
      <Icon name={tone === 'info' ? 'info' : 'warning'} className="text-[15px] mt-px shrink-0" />
      <span>{children}</span>
    </div>
  );
}

// Horizontal ranked bar list with a right-hand metric. Used everywhere a "top N by
// something" appears, so the tabs stay visually consistent.
export function RankedBars({ rows, labelKey = 'label', valueKey = 'count', format, tone }) {
  const max = Math.max(...rows.map((r) => Number(r[valueKey]) || 0), 1);
  if (!rows.length) return <div className="crm-empty">No data in range</div>;
  return (
    <div className="pt-1">
      {rows.map((r) => {
        const v = Number(r[valueKey]) || 0;
        return (
          <div key={r[labelKey]} className="grid grid-cols-[130px_1fr_auto] items-center gap-3 py-1.5">
            <div className="text-[12px] text-ink-3 truncate" title={r[labelKey]}>{r[labelKey]}</div>
            <div className="h-[20px] rounded-md bg-[rgba(10,10,10,0.04)] overflow-hidden">
              <div className="h-full rounded-md transition-all"
                style={{ width: `${Math.max((v / max) * 100, 1.5)}%`, background: tone || 'var(--gold)' }} />
            </div>
            <div className="text-[12px] font-semibold text-ink tabular-nums text-right min-w-[76px]">
              {format ? format(r) : fmt(v)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// A funnel that narrows. Each stage shows its own count, its conversion from the
// previous stage, and its share of the first — the three numbers you actually want.
export function FunnelStages({ stages, ramp }) {
  const first = stages[0]?.count || 1;
  return (
    <div className="grid gap-3 pt-1">
      {stages.map((s, i) => {
        const width = Math.max((s.count / first) * 100, 14);
        return (
          <div key={s.key} className="grid grid-cols-[1fr_auto] items-center gap-5">
            <div className="h-[52px] rounded-[14px] flex items-center px-5 text-white font-semibold text-[14px]"
              style={{ width: `${width}%`, background: ramp[i % ramp.length] }}>
              {s.label}
            </div>
            <div className="text-right min-w-[150px]">
              <div className="text-[20px] font-semibold text-ink tabular-nums leading-none">
                {fmt(s.count)}
              </div>
              <div className="text-[11.5px] text-ink-mute mt-1">
                {i === 0 ? 'entering' : `${s.of_previous}% of previous · ${s.of_first}% of leads`}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
