import { useEffect, useState } from 'react';
import FilterPopover from './FilterPopover';
import Icon from './Icon';
import { useStore } from '../store';
import { assignableUsersApi } from '../api';
import { shortUser } from '@/lib/crm';

// Assignment on a record: chips for current assignees, a picker to add more.
// Assignment goes through the backend's crm_assign, which delegates to Frappe's
// assign_to so `_assign`, document sharing, and notifications all stay correct.
export default function AssignControl({ doctype, name, assigned = [] }) {
  const assign = useStore((s) => s.assign);
  const unassign = useStore((s) => s.unassign);
  const [users, setUsers] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    let dead = false;
    assignableUsersApi()
      .then((u) => { if (!dead) setUsers(u || []); })
      .catch(() => { if (!dead) setUsers([]); });
    return () => { dead = true; };
  }, []);

  async function add(u, close) {
    setBusy(true); setErr('');
    try { await assign(doctype, name, [u]); close(); }
    catch (e) { setErr(e.message || 'Could not assign'); }
    finally { setBusy(false); }
  }

  async function drop(u) {
    setBusy(true); setErr('');
    try { await unassign(doctype, name, u); }
    catch (e) { setErr(e.message || 'Could not unassign'); }
    finally { setBusy(false); }
  }

  const free = users.filter((u) => !assigned.includes(u.name));

  // Rows are clickable (they open the desk record), so every control here must
  // stop propagation or assigning would also navigate away.
  return (
    <div className="flex items-center gap-1 flex-wrap" onClick={(e) => e.stopPropagation()}>
      {assigned.map((u) => (
        <span key={u} className="bdg bdg-other inline-flex items-center gap-1 normal-case">
          {shortUser(u)}
          <button disabled={busy} onClick={() => drop(u)} className="hover:text-bad" title={`Unassign ${u}`}>
            <Icon name="close" className="text-[12px]" />
          </button>
        </span>
      ))}
      <FilterPopover
        width={250}
        trigger={
          <button className="text-ink-3 hover:text-gold-text" title="Assign a user">
            <Icon name="person_add" className="text-[16px]" />
          </button>
        }
      >
        {({ close }) => (
          <div className="grid gap-1 max-h-64 overflow-y-auto">
            <div className="text-[10px] uppercase tracking-wide text-ink-mute font-medium">Assign to</div>
            {err && <div className="text-[11px] text-bad">{err}</div>}
            {free.length ? free.map((u) => (
              <button key={u.name} disabled={busy} onClick={() => add(u.name, close)}
                className="text-left text-[13px] px-2 py-1.5 rounded-lg hover:bg-hover truncate">
                {u.full_name}
                <span className="text-ink-mute text-[11px] block truncate">{u.name}</span>
              </button>
            )) : (
              <div className="text-[12px] text-ink-mute px-2 py-1.5">
                {users.length ? 'Everyone is already assigned' : 'No assignable users'}
              </div>
            )}
          </div>
        )}
      </FilterPopover>
    </div>
  );
}
