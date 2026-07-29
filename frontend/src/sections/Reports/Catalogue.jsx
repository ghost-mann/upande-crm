import { useEffect } from 'react';
import { useStore } from '../../store';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import Icon from '../../components/Icon';

// Every CRM and Selling report this user may see — nothing hidden.
//
// The ones marked "desk filters" are honest about a real limitation: a Script
// Report declares its filters in client-side JavaScript, so the server cannot
// discover what they need. Rather than run them into a traceback, they link out
// to the desk report view where the filter form exists.

function Row({ row }) {
  return (
    <div className="py-3 border-b border-hairline last:border-b-0 flex items-center gap-3">
      <Icon
        name={row.runnable ? 'play_circle' : 'open_in_new'}
        className={`text-[17px] shrink-0 ${row.runnable ? 'text-good' : 'text-ink-mute'}`}
      />
      <div className="min-w-0 flex-1">
        <div className="text-[13px] text-ink font-medium truncate">
          {row.report}
          {row.custom && <span className="bdg bdg-warn ml-2">site-specific</span>}
        </div>
        <div className="text-[11.5px] text-ink-mute mt-0.5">
          {row.module} · {row.type}{row.ref_doctype ? ` · ${row.ref_doctype}` : ''}
        </div>
      </div>
      {row.registered ? (
        <span className="bdg bdg-good shrink-0">in {row.group}</span>
      ) : row.runnable ? (
        <span className="bdg bdg-open shrink-0">runnable</span>
      ) : (
        <span className="bdg bdg-other shrink-0" title="Its filters are declared in client-side JS">
          desk filters
        </span>
      )}
      <a
        href={row.desk_url} target="_blank" rel="noopener noreferrer"
        className="text-[11.5px] text-gold-text hover:underline shrink-0"
      >
        desk →
      </a>
    </div>
  );
}

export default function Catalogue() {
  const catalogue = useStore((s) => s.reportCatalogue);
  const loadCatalogue = useStore((s) => s.loadReportCatalogue);

  useEffect(() => { if (!catalogue) loadCatalogue(); }, [catalogue, loadCatalogue]);

  if (!catalogue) return <div className="crm-empty">Loading catalogue…</div>;
  const rows = catalogue.reports || [];
  const curated = rows.filter((r) => r.registered).length;
  const deskOnly = rows.filter((r) => !r.runnable).length;

  const byModule = rows.reduce((acc, r) => {
    (acc[r.module] = acc[r.module] || []).push(r);
    return acc;
  }, {});

  return (
    <div>
      <Card className="mb-[18px]">
        <CardHeader>
          <div>
            <CardTitle>All reports</CardTitle>
            <CardSub>
              {rows.length} reports you may run · {curated} presented in the tabs above
              {deskOnly ? ` · ${deskOnly} need their filters set in desk` : ''}
            </CardSub>
          </div>
        </CardHeader>
        <CardContent>
          {deskOnly > 0 && (
            <div className="mb-3 text-[11.5px] text-ink-mute flex items-start gap-2">
              <Icon name="info" className="text-[14px] mt-px shrink-0" />
              <span>
                A report's filters live in its client-side script, which the server cannot read.
                Those marked <em>desk filters</em> would fail if run blind, so they link out
                instead of pretending.
              </span>
            </div>
          )}
          {Object.keys(byModule).sort().map((module) => (
            <div key={module} className="mb-4 last:mb-0">
              <div className="text-[10px] uppercase tracking-[0.16em] text-ink-mute font-semibold mb-1 pt-2">
                {module}
              </div>
              {byModule[module].map((row) => <Row key={row.report} row={row} />)}
            </div>
          ))}
          {!rows.length && <div className="crm-empty">No reports available to you</div>}
        </CardContent>
      </Card>
    </div>
  );
}
