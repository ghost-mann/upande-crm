import { useEffect } from 'react';
import { useStore } from '../../store';
import ReportView from './ReportView';

// One curated group of reports. The registry decides membership, so adding a
// report is a server-side change rather than a UI edit.
export default function Group({ group }) {
  const registry = useStore((s) => s.reports);
  const loadReports = useStore((s) => s.loadReports);

  useEffect(() => { if (!registry) loadReports(); }, [registry, loadReports]);

  if (!registry) return <div className="crm-empty">Loading reports…</div>;
  if (registry.error) return <div className="crm-empty">Could not load the report registry</div>;

  const meta = (registry.groups || []).find((g) => g.key === group);
  const entries = (registry.reports || []).filter((r) => r.group === group);

  return (
    <div>
      {meta && (
        <div className="mb-5">
          <h2 className="text-[13px] uppercase tracking-[0.18em] text-ink-4 font-medium">
            {meta.label}
          </h2>
          <p className="text-[12.5px] text-ink-mute mt-1">
            {meta.blurb} · ERPNext's own reports, {entries.length} of them here
          </p>
        </div>
      )}
      {entries.length
        ? entries.map((entry) => <ReportView key={entry.key} entry={entry} />)
        : <div className="crm-empty">No reports in this group</div>}
    </div>
  );
}
