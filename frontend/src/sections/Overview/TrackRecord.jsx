import { useState } from 'react';
import { fmt, fmtMoney } from '@shared/utils';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { useStore } from '../../store';
import { MultiLineChart } from '../../charts/Charts';
import { Toggle } from './parts';

const GRAIN_NOTE = { day: 'daily', week: 'weekly', month: 'monthly' };

// How sales have actually been going, per flower and per salesperson.
//
// One y-axis, always: revenue and stems answer different questions at different
// magnitudes, so they are a toggle rather than two axes on one plot.
export default function TrackRecord() {
  const T = useStore((s) => s.data.track);
  const openMover = useStore((s) => s.openMover);
  const [dim, setDim] = useState('flower');
  const [metric, setMetric] = useState('revenue');

  const tr = T?.track_record;
  const ccy = T?.currency || 'KES';
  const view = tr?.[dim];
  const money = metric === 'revenue';
  const rows = view?.[metric] || [];
  const series = view?.series || [];

  const total = series.reduce((s, x) => s + (money ? x.total : x.stems) || 0, 0);

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Track record</CardTitle>
          <CardSub>
            {dim === 'flower' ? 'Top varieties' : 'Top salespeople'} ·{' '}
            {GRAIN_NOTE[tr?.grain] || 'bucketed'} · click a name to explain its movement
          </CardSub>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Toggle value={dim} onChange={setDim} options={[
            { value: 'flower', label: 'By flower' },
            { value: 'rep', label: 'By salesperson' },
          ]} />
          <Toggle value={metric} onChange={setMetric} size="sm" options={[
            { value: 'revenue', label: ccy },
            { value: 'stems', label: 'Stems' },
          ]} />
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-[12px] text-ink-mute font-medium mb-1">
          {series.length} series ·{' '}
          {money ? fmtMoney(total, ccy) : `${fmt(Math.round(total))} stems`} in range
          {dim === 'flower' && money && (
            <span> · line value, excludes order-level charges</span>
          )}
        </div>
        <div className="h-[360px] relative">
          <MultiLineChart rows={rows} series={series} money={money} ccy={ccy}
            onSelect={(s) => openMover(dim, s.key, s.label)} />
        </div>
      </CardContent>
    </Card>
  );
}
