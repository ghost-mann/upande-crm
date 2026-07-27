import { useEffect, useMemo, useState } from 'react';
import { Card, CardHeader, CardTitle, CardSub } from '@/components/ui/card';
import { useStore } from '../../store';
import Icon from '../../components/Icon';
import { Button } from '@/components/ui/button';
import { PAL } from '../../charts/palette';
import { todayISO } from '@/lib/activity';

// Hand-rolled on purpose. vite.config.js documents that adding libraries to the
// single vendor chunk here has caused blank-screen crashes from circular chunk
// deps; a CSS-grid month view costs nothing and carries no such risk.
// Recurrence expansion happens server-side (core's get_events), so these rows
// are already one-per-occurrence.

const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'];

const p2 = (n) => String(n).padStart(2, '0');
const iso = (d) => `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;

function monthCells(monthStart) {
  const d = new Date(monthStart + 'T00:00:00');
  const y = d.getFullYear();
  const m = d.getMonth();
  const lead = (new Date(y, m, 1).getDay() + 6) % 7;   // Monday-first
  const days = new Date(y, m + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < lead; i++) cells.push(null);
  for (let i = 1; i <= days; i++) cells.push(new Date(y, m, i));
  while (cells.length % 7) cells.push(null);
  return cells;
}

function catColor(cat) {
  const cats = ['Meeting', 'Call', 'Event', 'Sent/Received Email', 'Other'];
  const i = cats.indexOf(cat || 'Other');
  return PAL[(i < 0 ? 4 : i) % PAL.length];
}

export default function Calendar() {
  const calMonth = useStore((s) => s.calMonth);
  const calRows = useStore((s) => s.calRows);
  const calLoading = useStore((s) => s.calLoading);
  const loadCalendar = useStore((s) => s.loadCalendar);
  const openEventDialog = useStore((s) => s.openEventDialog);
  const [expanded, setExpanded] = useState(null);

  // The calendar drives its own month; it deliberately ignores the header's
  // date-range pill.
  useEffect(() => { if (!calMonth) loadCalendar(todayISO()); }, [calMonth, loadCalendar]);

  const byDay = useMemo(() => {
    const m = {};
    for (const r of calRows || []) {
      const key = String(r.starts_on || '').slice(0, 10);
      if (!key) continue;
      (m[key] ||= []).push(r);
    }
    for (const k of Object.keys(m)) {
      m[k].sort((a, b) => String(a.starts_on).localeCompare(String(b.starts_on)));
    }
    return m;
  }, [calRows]);

  if (!calMonth) return <div className="crm-empty">Loading calendar…</div>;

  const cur = new Date(calMonth + 'T00:00:00');
  const cells = monthCells(calMonth);
  const today = todayISO();

  function shift(delta) {
    const d = new Date(cur.getFullYear(), cur.getMonth() + delta, 1);
    setExpanded(null);
    loadCalendar(iso(d));
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{MONTHS[cur.getMonth()]} {cur.getFullYear()}</CardTitle>
          <CardSub>
            {calLoading ? 'Loading…' : `${(calRows || []).length} occurrences · recurring events expanded`}
          </CardSub>
        </div>
        <div className="flex items-center gap-1.5">
          <button className="iconbtn !w-9 !h-9" title="Previous month" onClick={() => shift(-1)}>
            <Icon name="chevron_left" className="text-[18px]" />
          </button>
          <button className="datepill !py-2" onClick={() => { setExpanded(null); loadCalendar(today); }}>Today</button>
          <button className="iconbtn !w-9 !h-9" title="Next month" onClick={() => shift(1)}>
            <Icon name="chevron_right" className="text-[18px]" />
          </button>
          <Button size="sm" onClick={() => openEventDialog({ prefillStart: `${today} 09:00:00` })}
            className="rounded-full bg-gold text-ink hover:bg-gold-2 hover:text-white shadow-none px-4 ml-1">
            <Icon name="add" className="text-[16px]" />New
          </Button>
        </div>
      </CardHeader>

      <div className="px-4 pb-4">
        <div className="grid grid-cols-7 gap-1.5 mb-1.5">
          {DOW.map((d) => (
            <div key={d} className="text-[10px] uppercase tracking-[0.14em] text-ink-mute font-medium text-center py-1.5">
              {d}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7 gap-1.5">
          {cells.map((d, i) => {
            if (!d) return <div key={`pad-${i}`} className="min-h-[104px] rounded-xl bg-[rgba(10,10,10,0.015)]" />;
            const key = iso(d);
            const rows = byDay[key] || [];
            const isToday = key === today;
            const show = expanded === key ? rows : rows.slice(0, 3);
            return (
              <div key={key}
                className={`min-h-[104px] rounded-xl border p-1.5 transition-colors hover:bg-hover ${
                  isToday ? 'border-gold bg-gold-soft' : 'border-hairline bg-surface-2'}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-[11px] font-semibold tabular-nums ${isToday ? 'text-gold-text' : 'text-ink-4'}`}>
                    {d.getDate()}
                  </span>
                  <button className="text-ink-faint hover:text-gold-text" title="New event on this day"
                    onClick={() => openEventDialog({ prefillStart: `${key} 09:00:00` })}>
                    <Icon name="add" className="text-[13px]" />
                  </button>
                </div>
                <div className="grid gap-1">
                  {show.map((r, j) => (
                    <button key={`${r.name}-${j}`} onClick={() => openEventDialog(r)}
                      title={`${r.subject || 'Event'} · ${String(r.starts_on || '').slice(11, 16)}`}
                      className="text-left text-[10.5px] leading-tight rounded-md px-1.5 py-1 text-white truncate hover:opacity-85"
                      style={{ background: r.color || catColor(r.event_category) }}>
                      {String(r.starts_on || '').slice(11, 16)} {r.subject || 'Event'}
                    </button>
                  ))}
                  {rows.length > 3 && expanded !== key && (
                    <button onClick={() => setExpanded(key)}
                      className="text-[10px] text-ink-mute hover:text-gold-text text-left px-1.5">
                      +{rows.length - 3} more
                    </button>
                  )}
                  {expanded === key && rows.length > 3 && (
                    <button onClick={() => setExpanded(null)}
                      className="text-[10px] text-ink-mute hover:text-gold-text text-left px-1.5">
                      Show less
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}
