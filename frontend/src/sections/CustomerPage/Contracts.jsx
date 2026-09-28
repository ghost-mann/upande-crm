import { fmtDate } from '@shared/utils';
import DataTable from '../../components/DataTable';
import StatusBadge from '../../components/StatusBadge';
import { customerContractsApi } from '../../lib/customer';
import useLoad from './useLoad';

const COLUMNS = [
  { key: 'name', label: 'Contract', cls: 'cell-id' },
  { key: 'status', label: 'Status', render: (r) => <StatusBadge value={r.status} /> },
  { key: 'start_date', label: 'Starts', cls: 'cell-id', render: (r) => fmtDate(r.start_date) },
  { key: 'end_date', label: 'Ends', cls: 'cell-id', render: (r) => fmtDate(r.end_date) },
  { key: 'is_signed', label: 'Signed', render: (r) => (r.is_signed ? <span className="bdg bdg-good">Signed</span> : <span className="bdg bdg-other">Not yet</span>) },
  { key: 'contract_template', label: 'Template', render: (r) => r.contract_template || '—' },
];

export default function Contracts({ name }) {
  const { data, err, loading } = useLoad(() => customerContractsApi(name), [name]);
  if (err) return <div className="crm-empty">{err}</div>;
  if (!data) return <div className="crm-empty">{loading ? 'Loading…' : ''}</div>;
  if (data.no_access) return <div className="crm-empty">You don't have access to contracts.</div>;
  if (!data.available) return <div className="crm-empty">Contracts are not available on this site.</div>;
  return (
    <DataTable title="Contracts" subOverride={`${data.rows.length} on record`} columns={COLUMNS} rows={data.rows}
      doctype="Contract"
      emptyText="No contracts recorded — contracts entered in ERPNext against this customer appear here." />
  );
}
