import { useEffect, useState } from 'react';
import { apiGet } from '@shared/api';

// Client address -> the colleague who has written to it most. Cached across
// renders and across sections, because the mail list re-renders constantly
// (starring, marking read, paging) and the answer changes only when somebody
// sends a new email.
const cache = new Map();

/** The client-side address of a mail row: the other party, whichever way it went. */
export function counterpartyAddress(row) {
  const sent = (row.direction || row.sent_or_received) === 'Sent';
  const raw = sent ? row.recipients : row.sender;
  // `recipients` is a comma-joined list; the first address is the addressee.
  const first = String(raw || '').split(',')[0].trim();
  const angled = first.match(/<([^>]+)>/);
  return (angled ? angled[1] : first).toLowerCase();
}

/**
 * Who handles each of these conversations.
 *
 * Batched deliberately: the inbox renders 50 rows at a time and each wants a
 * badge, so a per-row request would be 50 round trips per page. Only addresses
 * not already cached are asked for.
 */
export function useCorrespondents(rows) {
  const [map, setMap] = useState(() => new Map(cache));

  useEffect(() => {
    const wanted = [...new Set((rows || []).map(counterpartyAddress).filter(Boolean))];
    const missing = wanted.filter((a) => !cache.has(a));
    if (!missing.length) return undefined;

    let cancelled = false;
    apiGet('upande_crm.api.correspondence.crm_correspondent_for_emails', {
      addresses: missing.join(','),
    })
      .then((res) => {
        if (cancelled) return;
        // Cache misses too, as null — otherwise every render re-asks about the
        // addresses that have no correspondent, which is most of them.
        missing.forEach((a) => cache.set(a, (res && res[a]) || null));
        setMap(new Map(cache));
      })
      .catch(() => {
        if (!cancelled) missing.forEach((a) => cache.set(a, null));
      });
    return () => {
      cancelled = true;
    };
  }, [rows]);

  return map;
}
