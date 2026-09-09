import { useEffect, useMemo, useState } from 'react';
import { apiGet } from '@shared/api';
import { useStore } from '../../store';

/**
 * Who on our side is talking to whom.
 *
 * The desk shows a mailbox. This shows the relationship behind it: for each
 * colleague, which accounts they correspond with, and for each account, who is
 * actually in the conversation. Built from sent email rather than `Sales Team`,
 * which holds one person on this site and answers nothing.
 *
 * Deliberately plain — cream shell, not the map's ink register. This is a
 * working list you scan, not a display.
 */
export default function Correspondence() {
  const dateFrom = useStore((s) => s.dateFrom);
  const dateTo = useStore((s) => s.dateTo);

  const [data, setData] = useState(null);
  const [state, setState] = useState('loading');
  const [focus, setFocus] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setState('loading');
    apiGet('upande_crm.api.correspondence.crm_correspondence', {
      date_from: dateFrom,
      date_to: dateTo,
    })
      .then((d) => {
        if (cancelled) return;
        setData(d || null);
        setState('ready');
      })
      .catch(() => !cancelled && setState('error'));
    return () => {
      cancelled = true;
    };
  }, [dateFrom, dateTo]);

  const rows = data?.rows || [];
  const staff = data?.staff || [];
  const shown = useMemo(
    () => (focus ? rows.filter((r) => r.staff === focus) : rows),
    [rows, focus]
  );

  if (state === 'loading') {
    return <div className="p-12 text-center text-[13px] text-ink-mute">Loading correspondence…</div>;
  }
  if (state === 'error') {
    return <div className="p-12 text-center text-[13px] text-ink-mute">Could not load correspondence.</div>;
  }
  if (!rows.length) {
    return (
      <div className="rounded-lg border border-hairline bg-surface p-10 text-center">
        <p className="text-[14px] text-ink">No attributable correspondence in this range.</p>
        <p className="mx-auto mt-2 max-w-md text-[12px] leading-relaxed text-ink-mute">
          A thread is attributed when an outgoing email reaches an address on a Contact
          that is linked to a Customer, Lead or Prospect. Widen the date range, or check
          that your contacts carry email addresses.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside>
        <SectionTitle>People</SectionTitle>
        <div className="rounded-lg border border-hairline bg-surface">
          <button
            type="button"
            onClick={() => setFocus(null)}
            className={`flex w-full items-baseline justify-between gap-3 px-3 py-2.5 text-left ${!focus ? 'bg-selected' : ''}`}
          >
            <span className="text-[13px] font-medium text-ink">Everyone</span>
            <span className="font-mono text-[11px] tabular-nums text-ink-mute">{rows.length}</span>
          </button>
          {staff.map((s) => (
            <button
              key={s.staff}
              type="button"
              onClick={() => setFocus(focus === s.staff ? null : s.staff)}
              className={`flex w-full items-center justify-between gap-3 border-t border-hairline px-3 py-2.5 text-left ${focus === s.staff ? 'bg-selected' : ''}`}
            >
              <span className="min-w-0">
                <span className="block truncate text-[13px] text-ink">
                  {s.staff_name}
                  {s.shared && <SharedTag />}
                </span>
                <span className="block truncate text-[11px] text-ink-mute">{s.staff}</span>
              </span>
              <span className="shrink-0 text-right">
                <span className="block font-mono text-[12px] tabular-nums text-ink">{s.accounts}</span>
                <span className="block text-[9px] uppercase tracking-[0.14em] text-ink-mute">accts</span>
              </span>
            </button>
          ))}
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-ink-mute">
          Attribution comes from who sends the email, not from Sales Team — that field
          holds a single person on this site.
        </p>
      </aside>

      <div className="min-w-0">
        <SectionTitle>
          {focus ? `Accounts handled by ${staff.find((s) => s.staff === focus)?.staff_name || focus}` : 'Every conversation'}
        </SectionTitle>
        <div className="overflow-hidden rounded-lg border border-hairline bg-surface">
          <table className="w-full">
            <thead>
              <tr className="border-b border-hairline text-ink-mute">
                <Th>Account</Th>
                <Th>Type</Th>
                <Th>Handled by</Th>
                <Th right>Sent</Th>
                <Th right>Recv</Th>
                <Th right>Last</Th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={`${r.staff}-${r.party_type}-${r.party}`} className="border-b border-hairline last:border-0">
                  <Td><span className="font-medium text-ink">{r.party}</span></Td>
                  <Td><span className="text-ink-mute">{r.party_type}</span></Td>
                  <Td>
                    {r.staff ? (
                      <span className="text-ink">
                        {r.staff_name}
                        {r.shared && <SharedTag />}
                      </span>
                    ) : (
                      <span className="text-ink-mute italic">unassigned</span>
                    )}
                  </Td>
                  <Td right mono>{r.sent}</Td>
                  <Td right mono>{r.received}</Td>
                  <Td right mono>{(r.last || '').slice(0, 10) || '—'}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-ink-mute">
          Inbound mail names the client, not our colleague, so received counts attach to
          the person already corresponding with that account. An account nobody has
          written to shows as unassigned.
          {data?.truncated && ' Showing the busiest conversations only — narrow the date range to see the rest.'}
        </p>
      </div>
    </div>
  );
}

const SectionTitle = ({ children }) => (
  <div className="mb-2.5 text-[11px] font-medium uppercase tracking-[0.18em] text-ink-mute">{children}</div>
);

const SharedTag = () => (
  <span className="ml-1.5 rounded bg-canvas px-1 py-px text-[9px] uppercase tracking-[0.1em] text-ink-mute">
    shared
  </span>
);

const Th = ({ children, right }) => (
  <th className={`px-3 py-2 text-[10px] font-normal uppercase tracking-[0.16em] ${right ? 'text-right' : 'text-left'}`}>
    {children}
  </th>
);

const Td = ({ children, right, mono }) => (
  <td className={`px-3 py-2 text-[12px] ${right ? 'text-right' : ''} ${mono ? 'font-mono tabular-nums text-ink-mute' : ''}`}>
    {children}
  </td>
);
