import { useState } from 'react';
import { Button } from '@/components/ui/button';
import Icon from '../../components/Icon';
import DataTable from '../../components/DataTable';
import VisitDialog from '../../components/VisitDialog';
import { visitColumns } from '../Visits/index.jsx';
import { customerVisitsApi } from '@/lib/service';
import useLoad from './useLoad';

export default function Visits({ name }) {
  const [tick, setTick] = useState(0);
  const [dialog, setDialog] = useState(null);
  const { data, err } = useLoad(() => customerVisitsApi(name), [name, tick]);
  if (err) return <div className="crm-empty">{err}</div>;
  if (!data) return <div className="crm-empty">Loading…</div>;
  if (!data.available) return <div className="crm-empty">You don't have access to visits.</div>;
  const start = (visit_type) => setDialog({ visit_type, party_type: 'Customer', party: name, lockParty: true });
  return (
    <>
      <div className="flex gap-2 mb-4 flex-wrap">
        <Button size="sm" onClick={() => start('Sales visit to customer')}
          className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-4">
          <Icon name="directions_car" className="text-[16px]" />Log a sales visit
        </Button>
        <Button size="sm" variant="outline" className="rounded-full px-4" onClick={() => start('Customer visit to farm')}>
          <Icon name="agriculture" className="text-[16px]" />Log their farm visit
        </Button>
      </div>
      <DataTable title="Visits" subOverride={`${data.rows.length} on record`} columns={visitColumns(false)} rows={data.rows}
        onRowClick={(r) => setDialog({ ...r, lockParty: true })} emptyText="No visits with this customer yet" />
      {dialog && <VisitDialog visit={dialog} purposes={data.purposes} onClose={() => setDialog(null)} onSaved={() => setTick((t) => t + 1)} />}
    </>
  );
}
