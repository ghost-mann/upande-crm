import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { fmt, fmtDate } from '@shared/utils';
import { useStore } from '../../store';
import Icon from '../../components/Icon';
import { KpiRow } from '../../components/Kpi';
import ChartCard from '../../components/ChartCard';
import DataTable from '../../components/DataTable';
import VisitDialog from '../../components/VisitDialog';
import { HBarsChart, DoughnutChart } from '../../charts/Charts';
import { visitsDashboardApi, VISIT_TONE } from '@/lib/service';

// Farm visits by customers and sales visits to them — so relationship work is
// written down, with its outcome and the follow-ups it created.
export function visitColumns(withParty = true) {
  return [
    { key: 'visit_date', label: 'When', cls: 'cell-id', render: (r) => fmtDate(r.visit_date) },
    { key: 'visit_type', label: 'Type', render: (r) => (
      <span className="inline-flex items-center gap-1.5">
        <Icon name={r.visit_type?.startsWith('Customer') ? 'agriculture' : 'directions_car'} className="text-[15px] text-ink-3" />
        {r.visit_type?.startsWith('Customer') ? 'At the farm' : 'At the customer'}
      </span>
    ) },
    ...(withParty ? [{ key: 'party', label: 'Who', render: (r) => (
      <span>{r.party}{r.party_type !== 'Customer' && <span className="text-ink-mute text-[11px]"> · {r.party_type}</span>}</span>
    ) }] : []),
    { key: 'purpose', label: 'Purpose' },
    { key: 'status', label: 'Status', render: (r) => <span className={`bdg ${VISIT_TONE[r.status] || 'bdg-other'}`}>{r.status}</span> },
    { key: 'open_actions', label: 'Follow-ups', cls: 'cell-num', render: (r) => (
      r.actions?.length ? `${r.open_actions} open / ${r.actions.length}` : '—'
    ) },
  ];
}

export default function Visits() {
  const dateFrom = useStore((s) => s.dateFrom);
  const dateTo = useStore((s) => s.dateTo);
  const customer = useStore((s) => s.customerFilter);
  const table = useStore((s) => s.table);
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const [dialog, setDialog] = useState(null);

  const load = useCallback(() => {
    setErr('');
    visitsDashboardApi({ date_from: dateFrom, date_to: dateTo, customer: customer || undefined })
      .then(setData).catch((e) => setErr(e.message || 'Could not load visits'));
  }, [dateFrom, dateTo, customer]);
  useEffect(() => { load(); }, [load]);

  if (err) return <div className="crm-empty">{err}</div>;
  if (!data) return <div className="p-12 text-center text-ink-mute text-[13px]">Loading…</div>;
  if (!data.available) return <div className="crm-empty">Visits are not available — run bench migrate, or ask for access to CRM Visit.</div>;
  const k = data.kpis;
  const open = (r, type) => setDialog(r ? { ...r } : {
    ...(type ? { visit_type: type } : {}),
    ...(customer ? { party_type: 'Customer', party: customer } : {}),
  });

  return (
    <>
      <div className="flex items-center gap-2.5 mb-5 flex-wrap">
        <Button size="sm" onClick={() => open(null, 'Sales visit to customer')}
          className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-4">
          <Icon name="directions_car" className="text-[16px]" />Log a sales visit
        </Button>
        <Button size="sm" variant="outline" className="rounded-full px-4" onClick={() => open(null, 'Customer visit to farm')}>
          <Icon name="agriculture" className="text-[16px]" />Log a farm visit
        </Button>
      </div>

      {table !== 'rows' && (
        <>
          <KpiRow items={[
            { lbl: 'Coming up', val: fmt(k.upcoming) },
            { lbl: 'Completed in range', val: fmt(k.completed) },
            { lbl: 'Farm visits', val: fmt(k.farm_visits) },
            { lbl: 'Sales visits', val: fmt(k.sales_visits) },
            { lbl: 'Open follow-ups', val: fmt(k.open_followups), chip: k.open_followups ? 'in Events & Tasks' : null, chipTone: 'gold' },
          ]} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <ChartCard title="Why we met" sub="Visits in the selected range">
              <HBarsChart labels={data.by_purpose.map((r) => r.label)} data={data.by_purpose.map((r) => r.count)} />
            </ChartCard>
            <ChartCard title="Where" sub="At the farm, or at the customer">
              <DoughnutChart items={data.by_type} />
            </ChartCard>
          </div>
          {!!data.upcoming.length && (
            <div className="mb-4">
              <DataTable title="Coming up" subOverride="Planned visits from today" columns={visitColumns()}
                rows={data.upcoming} onRowClick={(r) => open(r)} />
            </div>
          )}
        </>
      )}

      <DataTable title="Visits" subOverride={`${fmt(data.rows.length)} in range`} columns={visitColumns()} rows={data.rows}
        onRowClick={(r) => open(r)} searchFields={['party', 'purpose', 'status', 'visit_type']}
        emptyText="No visits logged in this range" />

      {dialog && <VisitDialog visit={dialog} purposes={data.purposes} onClose={() => setDialog(null)} onSaved={load} />}
    </>
  );
}
