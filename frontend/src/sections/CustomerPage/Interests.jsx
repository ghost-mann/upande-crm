import { useState } from 'react';
import DataTable from '../../components/DataTable';
import InterestDetail from '../Catalogues/InterestDetail';
import { interestColumns } from '../Catalogues/index.jsx';
import { interestsApi } from '@/lib/catalogues';
import useLoad from './useLoad';

// What this customer has asked for through catalogue links.
export default function Interests({ name }) {
  const [tick, setTick] = useState(0);
  const [detail, setDetail] = useState(null);
  const { data, err } = useLoad(() => interestsApi({ party_type: 'Customer', party: name }), [name, tick]);
  if (err) return <div className="crm-empty">{err}</div>;
  if (!data) return <div className="crm-empty">Loading…</div>;
  return (
    <>
      <DataTable title="Catalogue interest" subOverride={`${data.rows.length} submissions`}
        columns={interestColumns(false)} rows={data.rows} onRowClick={(r) => setDetail(r.name)}
        emptyText="Nothing from this customer through a catalogue yet" />
      {detail && <InterestDetail name={detail} onClose={() => setDetail(null)} onChanged={() => setTick((t) => t + 1)} />}
    </>
  );
}
