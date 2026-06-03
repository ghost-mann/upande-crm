import { Card, CardHeader, CardTitle, CardSub } from '@/components/ui/card';
import { useStore } from '../store';
import { openFrappe } from '@/lib/crm';

// columns: [{ key, label, cls?, thStyle?, render?(row) }]
// doctype: string | (row) => string   (omit to make rows non-clickable)
// rowName: (row) => string            (defaults to row.name)
export default function DataTable({
  title, columns, rows = [], searchFields = [], doctype, rowName,
  emptyText = 'No records', subOverride,
}) {
  const search = useStore((s) => s.search);
  const newTab = useStore((s) => s.settings.openInNewTab);

  const filtered = search && searchFields.length
    ? rows.filter((r) => searchFields.some((f) => String(r[f] || '').toLowerCase().includes(search.toLowerCase())))
    : rows;

  const sub = subOverride || `${filtered.length} of ${rows.length}`;
  const getDt = typeof doctype === 'function' ? doctype : () => doctype;

  return (
    <Card>
      <CardHeader>
        <div><CardTitle>{title}</CardTitle><CardSub>{sub}</CardSub></div>
      </CardHeader>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>{columns.map((c) => <th key={c.key} style={c.thStyle}>{c.label}</th>)}</tr>
          </thead>
          <tbody>
            {filtered.length ? filtered.map((r, i) => {
              const dt = getDt(r);
              const nm = rowName ? rowName(r) : r.name;
              return (
                <tr
                  key={nm || i}
                  className={dt ? 'clickable' : ''}
                  onClick={dt ? () => openFrappe(dt, nm, newTab) : undefined}
                >
                  {columns.map((c) => (
                    <td key={c.key} className={c.cls}>{c.render ? c.render(r) : (r[c.key] ?? '—')}</td>
                  ))}
                </tr>
              );
            }) : (
              <tr><td colSpan={columns.length}><div className="crm-empty">{emptyText}</div></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
