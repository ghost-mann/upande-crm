import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { fmtDate } from '@shared/utils';
import ChartCard from '../../components/ChartCard';
import { AreaTrendChart, HBarsChart } from '../../charts/Charts';
import { useStore } from '../../store';
import { openFrappe, shortUser } from '@/lib/crm';
import { customerOverviewApi } from '../../lib/customer';
import useLoad from './useLoad';

export default function Overview({ name, currency }) {
  const { data, err, loading } = useLoad(() => customerOverviewApi(name), [name]);
  const newTab = useStore((s) => s.settings.openInNewTab);
  if (err) return <div className="crm-empty">{err}</div>;
  if (!data) return <div className="crm-empty">{loading ? 'Loading…' : 'Nothing to show'}</div>;
  const top = data.top_items || [];
  const noRevenue = data.no_access?.revenue;

  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-[18px] mb-[18px]">
        <ChartCard title="Revenue by month" sub={`Last 12 months · invoiced · ${currency}`}>
          {noRevenue
            ? <div className="crm-empty">You don't have access to sales invoices.</div>
            : <AreaTrendChart labels={data.trend.map((r) => r.label)} data={data.trend.map((r) => r.amount)} />}
        </ChartCard>
        <ChartCard title="What they buy" sub="Top 10 items by invoiced amount, all time">
          {top.length
            ? <HBarsChart labels={top.map((r) => r.item_name || r.item_code)} data={top.map((r) => r.amount)} money ccy={currency} />
            : <div className="crm-empty">{noRevenue ? "You don't have access to sales invoices." : 'No invoiced items yet'}</div>}
        </ChartCard>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-[18px]">
        <Card>
          <CardHeader><div><CardTitle>Next event</CardTitle><CardSub>Meetings, visits and calls booked</CardSub></div></CardHeader>
          <CardContent>
            {data.next_event ? (
              <button type="button" className="text-left" onClick={() => openFrappe('Event', data.next_event.name, newTab)}>
                <div className="text-[14px] text-ink font-medium">{data.next_event.subject}</div>
                <div className="text-[12.5px] text-ink-3">{fmtDate(data.next_event.starts_on)}</div>
              </button>
            ) : <div className="crm-empty">Nothing booked</div>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><div><CardTitle>Open tasks</CardTitle><CardSub>{data.open_todos.length} waiting</CardSub></div></CardHeader>
          <CardContent>
            {data.open_todos.length ? data.open_todos.map((t) => (
              <button key={t.name} type="button" onClick={() => openFrappe('ToDo', t.name, newTab)}
                className="w-full text-left py-2 border-b border-hairline last:border-b-0 flex items-start justify-between gap-3">
                <span className="text-[13px] text-ink-2 line-clamp-2" >{String(t.description || '').replace(/<[^>]+>/g, ' ')}</span>
                <span className="text-[11.5px] text-ink-mute shrink-0">{t.date ? fmtDate(t.date) : ''}{t.allocated_to ? ` · ${shortUser(t.allocated_to)}` : ''}</span>
              </button>
            )) : <div className="crm-empty">No open tasks</div>}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
