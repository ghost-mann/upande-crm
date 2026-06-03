import { useStore } from '../store';
import Icon from './Icon';
import { avatarBg } from '@/lib/crm';
import { initials, fmtRelative, nameFromAddress } from '@shared/utils';

// Renders an array of Communication/email rows as mail-rows (source .mail-row).
export default function MailList({ rows = [], onOpen }) {
  const starred = useStore((s) => s.starred);
  const toggleStar = useStore((s) => s.toggleStar);

  if (!rows.length) return <div className="crm-empty">No emails</div>;

  return (
    <div>
      {rows.map((e) => {
        const sent = (e.direction || e.sent_or_received) === 'Sent';
        const counterparty = e.display_name
          || (sent ? (e.recipients || '—') : nameFromAddress(e.sender || ''))
          || '—';
        const isStarred = starred.includes(e.name) || String(e._user_tags || '').toLowerCase().includes('starred');
        const unread = !!e.unread || (e.sent_or_received === 'Received' && e.status === 'Open');
        return (
          <div key={e.name} className={`mail-row ${unread ? 'unread' : ''}`} onClick={() => onOpen?.(e)}>
            <div className="m-check" onClick={(ev) => ev.stopPropagation()}>
              <input type="checkbox" />
            </div>
            <div
              className={`m-star ${isStarred ? 'on' : ''}`}
              onClick={(ev) => { ev.stopPropagation(); toggleStar(e.name, !isStarred); }}
            >
              <Icon name={isStarred ? 'star' : 'star_border'} className="text-[16px]" />
            </div>
            <div className="m-from">
              <div className="m-avatar" style={{ background: avatarBg(counterparty) }}>{initials(counterparty)}</div>
              {sent && <span className="m-dir">to</span>}
              <div className="m-name">{counterparty}</div>
            </div>
            <div className="m-subj-cell">
              {e.reference_doctype && <span className="m-chip">{e.reference_doctype}</span>}
              <span className="m-subj">{e.subject || '(no subject)'}</span>
              {e.reference_name && <span className="m-snip">— {e.reference_name}</span>}
            </div>
            <div className="m-time">{fmtRelative(e.communication_date)}</div>
          </div>
        );
      })}
    </div>
  );
}
