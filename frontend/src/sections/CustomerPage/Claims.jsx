import { useState } from 'react';
import { Button } from '@/components/ui/button';
import Icon from '../../components/Icon';
import DataTable from '../../components/DataTable';
import ClaimDialog from '../../components/ClaimDialog';
import { claimColumns } from '../Claims/index.jsx';
import { customerClaimsApi } from '@/lib/service';
import useLoad from './useLoad';

export default function Claims({ name, currency }) {
  const [tick, setTick] = useState(0);
  const [dialog, setDialog] = useState(null);
  const { data, err } = useLoad(() => customerClaimsApi(name), [name, tick]);
  if (err) return <div className="crm-empty">{err}</div>;
  if (!data) return <div className="crm-empty">Loading…</div>;
  if (!data.available) return <div className="crm-empty">You don't have access to claims.</div>;
  return (
    <>
      <div className="mb-4">
        <Button size="sm" onClick={() => setDialog({ customer: name, lockCustomer: true })}
          className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-4">
          <Icon name="report" className="text-[16px]" />Log a claim for this customer
        </Button>
      </div>
      <DataTable title="Claims" subOverride={`${data.rows.length} on record · overdue after ${data.sla_days} days`}
        columns={claimColumns(data.currency || currency, false)} rows={data.rows}
        onRowClick={(r) => setDialog({ ...r, lockCustomer: true })}
        emptyText="No claims from this customer" />
      {dialog && <ClaimDialog claim={dialog} types={data.types} onClose={() => setDialog(null)} onSaved={() => setTick((t) => t + 1)} />}
    </>
  );
}
