import { fmtRelative } from '@shared/utils';

// Did the client open it?
//
// Frappe stamps `read_by_recipient` from a tracking pixel embedded in outgoing
// mail. Two consequences shape everything below.
//
// It undercounts. A recipient whose mail client blocks images reads the message
// and never registers, so the negative case says "no open recorded" — which is
// true — and never "not opened", which would not be.
//
// There is no count. `update_communication_as_read` returns early once the flag is
// set, so only the first open is ever stored. This shows *whether* and *when*,
// because that is all there is; a "opened 3 times" badge would be invented.
//
// Only ever rendered for mail we sent: an open flag on a received message is
// meaningless.

const NOTE = 'Tracked with a pixel in the sent message, so opens are undercounted — '
  + 'a client that blocks images reads without registering. Requires “Track Email '
  + 'Status” on the outgoing email account.';

export default function OpenIndicator({ row, className = '' }) {
  const sent = (row?.direction || row?.sent_or_received) === 'Sent';
  if (!sent) return null;

  const opened = !!row.opened || !!row.read_by_recipient;
  const when = row.opened_on || row.read_by_recipient_on;

  return (
    <span
      title={`${opened ? 'The recipient opened this message.' : 'No open has been recorded.'} ${NOTE}`}
      className={`inline-flex items-center gap-1.5 text-[11px] whitespace-nowrap ${
        opened ? 'text-good' : 'text-ink-mute'} ${className}`}
    >
      <span className={`w-[7px] h-[7px] rounded-full shrink-0 ${
        opened ? 'bg-good' : 'border border-current'}`} />
      {opened ? `opened${when ? ` · ${fmtRelative(when)}` : ''}` : 'no open recorded'}
    </span>
  );
}
