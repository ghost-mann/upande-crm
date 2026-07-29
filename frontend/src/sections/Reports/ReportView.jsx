import { useEffect, useState } from 'react';
import { fmt } from '@shared/utils';
import { useStore } from '../../store';
import { reportRunApi } from '../../api';
import Icon from '../../components/Icon';
import { KpiCard } from '../../components/Kpi';
import { BarsChart, HBarsChart, AreaTrendChart } from '../../charts/Charts';
import { isNumeric, linkFor, renderCell, visibleColumns } from './columns';
import { cn } from '@/lib/utils';

// One report: ERPNext's own output, rendered with the CRM's tiles, chart and table.
//
// Loads on expand rather than on tab open — `Item-wise Sales History` returns
// 39,232 rows for a year on this site, so firing five reports in parallel because
// a tab was clicked would be a poor trade.

function Summary({ summary, ccy }) {
  if (!summary?.length) return null;
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3 mb-4">
      {summary.map((s, i) => (
        <KpiCard
          key={`${s.label}-${i}`}
          lbl={s.label || '—'}
          val={renderCell(s.value, { fieldtype: s.datatype || 'Data' }, ccy)}
          chip={s.indicator || ''}
          chipTone={s.indicator === 'Red' ? 'down' : s.indicator === 'Green' ? 'up' : ''}
        />
      ))}
    </div>
  );
}

// Frappe charts declare {data: {labels, datasets}, type}. Map onto the CRM's own
// chart components rather than pulling in frappe-charts.
function ReportChart({ chart }) {
  const labels = chart?.data?.labels || [];
  const sets = chart?.data?.datasets || [];
  if (!labels.length || !sets.length) return null;
  const values = (sets[0].values || []).map((v) => Number(v) || 0);
  if (!values.length) return null;
  const type = String(chart.type || 'bar').toLowerCase();
  return (
    <div className="h-[240px] relative mb-4">
      {type === 'line' ? <AreaTrendChart labels={labels} data={values} />
        : labels.length > 8 ? <HBarsChart labels={labels} data={values} />
          : <BarsChart labels={labels} data={values} />}
    </div>
  );
}

function Table({ columns, rows, ccy }) {
  const cols = visibleColumns(columns);
  if (!cols.length) return <div className="crm-empty">This report returned no columns</div>;
  if (!rows.length) return <div className="crm-empty">No rows for this range</div>;
  return (
    <div className="tbl-wrap crm-scroll">
      <table className="tbl">
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c.fieldname} className={isNumeric(c.fieldtype) ? 'text-right' : undefined}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {cols.map((c) => {
                const value = row[c.fieldname];
                const href = linkFor(value, c);
                const text = renderCell(value, c, ccy);
                return (
                  <td key={c.fieldname}
                    className={cn(isNumeric(c.fieldtype) && 'text-right tabular-nums')}>
                    {href ? (
                      <a href={href} target="_blank" rel="noopener noreferrer"
                        className="text-gold-text hover:underline">{text}</a>
                    ) : text}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ReportView({ entry }) {
  const dateFrom = useStore((s) => s.dateFrom);
  const dateTo = useStore((s) => s.dateTo);
  const customer = useStore((s) => s.customerFilter);
  const ccy = useStore((s) => s.orgMeta.currency);

  const [open, setOpen] = useState(false);
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [overrides, setOverrides] = useState({});

  async function load(extra) {
    setLoading(true);
    try {
      const d = await reportRunApi({
        key: entry.key,
        filters: { ...overrides, ...(extra || {}) },
        date_from: dateFrom,
        date_to: dateTo,
        customer: customer || undefined,
      });
      setPayload(d);
    } catch (e) {
      setPayload({ error: e.message || 'Could not run this report' });
    } finally {
      setLoading(false);
    }
  }

  // Re-run an open report when the header range moves, but only if it is actually
  // date-scoped — re-fetching a report that ignores the range would be waste.
  useEffect(() => {
    if (open && entry.date_scoped) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateFrom, dateTo, customer]);

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !payload) load();
  }

  return (
    <div className="rounded-2xl border border-hairline bg-surface-2 mb-3 overflow-hidden">
      <button
        onClick={toggle}
        className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-hover transition-colors"
      >
        <Icon name={open ? 'expand_less' : 'expand_more'} className="text-[20px] text-ink-mute shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="text-[14px] font-semibold text-ink">{entry.label}</div>
          <div className="text-[12px] text-ink-mute mt-0.5">{entry.blurb}</div>
        </div>
        <div className="shrink-0 flex items-center gap-2">
          {!entry.date_scoped && (
            <span className="bdg bdg-other" title="This report ignores the header date range">
              not date-scoped
            </span>
          )}
          {payload?.total_rows != null && !payload.error && (
            <span className="text-[11.5px] text-ink-mute tabular-nums">
              {fmt(payload.total_rows)} rows
            </span>
          )}
          {!entry.permitted && <span className="bdg bdg-bad">no access</span>}
        </div>
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-hairline pt-4">
          {loading && <div className="crm-empty">Running {entry.label}…</div>}

          {!loading && payload?.error && (
            <div className="grid gap-2">
              <div className="text-[12.5px] text-bad flex items-start gap-2">
                <Icon name="error" className="text-[15px] mt-px shrink-0" />
                <span>{payload.error}</span>
              </div>
              <a href={payload.desk_url} target="_blank" rel="noopener noreferrer"
                className="text-[12.5px] text-gold-text hover:underline">
                Open in desk, where its filters can be set →
              </a>
            </div>
          )}

          {!loading && payload && !payload.error && (
            <>
              <Summary summary={payload.summary} ccy={ccy} />
              <ReportChart chart={payload.chart} />

              {entry.editable?.length > 0 && (
                <div className="flex flex-wrap items-end gap-3 mb-4">
                  {entry.editable.map((field) => (
                    <label key={field} className="grid gap-1">
                      <span className="text-[10px] uppercase tracking-[0.14em] text-ink-mute font-medium">
                        {field.replace(/_/g, ' ')}
                      </span>
                      <input
                        defaultValue={payload.filters?.[field] ?? ''}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            const next = { ...overrides, [field]: e.target.value };
                            setOverrides(next);
                            load(next);
                          }
                        }}
                        className="h-8 w-[160px] rounded-md border border-input bg-transparent px-2.5 text-[12.5px] outline-none focus:ring-1 focus:ring-ring"
                      />
                    </label>
                  ))}
                  <span className="text-[11px] text-ink-mute pb-1.5">press Enter to re-run</span>
                </div>
              )}

              <Table columns={payload.columns} rows={payload.rows || []} ccy={ccy} />

              <div className="mt-3 flex items-center gap-3 flex-wrap text-[11.5px] text-ink-mute">
                {payload.truncated && (
                  <span className="text-warn font-medium">
                    Showing the first {fmt(payload.row_cap)} of {fmt(payload.total_rows)} rows
                  </span>
                )}
                {payload.execution_time != null && (
                  <span>ran in {Number(payload.execution_time).toFixed(2)}s</span>
                )}
                <a href={payload.desk_url} target="_blank" rel="noopener noreferrer"
                  className="text-gold-text hover:underline ml-auto">
                  Open in desk →
                </a>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
