import { useStore } from '../store';
import Icon from './Icon';
import { avatarBg, openFrappe } from '@/lib/crm';
import { initials, fmtRelative, nameFromAddress } from '@shared/utils';

// Renders an array of Communication/email rows as Gmail-style mail-rows.
export default function MailList({ rows = [], onOpen, selected, onToggleSelect }) {
  const starred = useStore((s) => s.starred);
  const toggleStar = useStore((s) => s.toggleStar);
  const markRead = useStore((s) => s.markRead);
  const openCompose = useStore((s) => s.openCompose);
  const newTab = useStore((s) => s.settings.openInNewTab);

  if (!rows.length) return <div className="crm-empty">No emails</div>;

  return (
    <div>
      {rows.map((e) => {
        const sent = (e.direction || e.sent_or_received) === 'Sent';
        const counterparty = e.display_name
          || (sent ? (e.recipients || '—') : nameFromAddress(e.sender || ''))
          || '—';
        const isStarred = starred.includes(e.name) || String(e._user_tags || '').toLowerCase().includes('starred');
        const unread = !!e.unread || (e.sent_or_received === 'Received' && e.status === 'Open' && !e.seen);

        const reply = (ev) => {
          ev.stopPropagation();
          openCompose({
            title: 'Reply',
            to: sent ? (e.recipients || '') : (e.sender || ''),
            subject: `Re: ${String(e.subject || '').replace(/^\s*(re:\s*)+/i, '')}`,
            reference: e.reference_doctype && e.reference_name ? { doctype: e.reference_doctype, name: e.reference_name } : undefined,
            inReplyTo: e.name,
          });
        };

        const checked = selected ? selected.has(e.name) : false;
        return (
          <div key={e.name} className={`mail-row ${unread ? 'unread' : ''} ${checked ? 'selected' : ''}`} onClick={() => onOpen?.(e)}>
            <div className="m-check" onClick={(ev) => ev.stopPropagation()}>
              <input type="checkbox" aria-label={`Select email: ${e.subject || '(no subject)'}`}
                checked={checked} onChange={() => onToggleSelect?.(e.name)} />
            </div>
            <button
              type="button"
              aria-label={isStarred ? 'Unstar email' : 'Star email'}
              aria-pressed={isStarred}
              className={`m-star ${isStarred ? 'on' : ''}`}
              onClick={(ev) => { ev.stopPropagation(); toggleStar(e.name, !isStarred); }}
            >
              <Icon name={isStarred ? 'star' : 'star_border'} className="text-[16px]" />
            </button>
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
            <div className="m-actions">
              <button
                title={unread ? 'Mark as read' : 'Mark as unread'}
                aria-label={unread ? 'Mark as read' : 'Mark as unread'}
                onClick={(ev) => { ev.stopPropagation(); markRead(e.name, unread); }}
              >
                <Icon name={unread ? 'mark_email_read' : 'mark_email_unread'} className="text-[18px]" />
              </button>
              <button title="Reply" aria-label="Reply" onClick={reply}>
                <Icon name="reply" className="text-[18px]" />
              </button>
              <button
                title="Open in Frappe"
                aria-label="Open in Frappe"
                onClick={(ev) => { ev.stopPropagation(); openFrappe('Communication', e.name, newTab); }}
              >
                <Icon name="open_in_new" className="text-[17px]" />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
