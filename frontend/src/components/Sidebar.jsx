import { NAV } from '../nav';
import Icon from './Icon';
import { useStore } from '../store';
import { fmt, initials } from '@shared/utils';
import { getBoot } from '@shared/api';
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar';
import { cn } from '@/lib/utils';

function groupCount(section, data, mailCounts) {
  switch (section) {
    case 'leads': return data.leads?.kpis?.total;
    case 'opps': return data.opps?.kpis?.total;
    case 'prosp': return data.prosp?.kpis?.total;
    case 'cust': return data.cust?.kpis?.active;
    case 'evt': return (data.evt?.kpis?.events_open || 0) + (data.evt?.kpis?.tasks_open || 0);
    case 'act': return data.act?.kpis?.total;
    case 'mail': return mailCounts?.inbox_unread;
    default: return undefined;
  }
}

const ITEM_ON = 'bg-grad-ink text-white font-medium shadow-[0_4px_14px_rgba(10,10,10,0.18)]';
const ITEM_OFF = 'text-ink-4 hover:bg-hover hover:text-ink';

export default function Sidebar({ onCompose, onSettings, collapsed, onToggleCollapse }) {
  const section = useStore((s) => s.section);
  const select = useStore((s) => s.select);
  const data = useStore((s) => s.data);
  const mailCounts = useStore((s) => s.mailFolder?.counts);

  return (
    <aside className="sticky top-[84px] max-[900px]:static max-h-[calc(100vh-104px)] max-[900px]:max-h-none bg-surface border border-hairline rounded-[24px] shadow-card flex flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto crm-scroll pt-4 pb-2">
        <div className={cn('pb-2', collapsed ? 'px-2' : 'px-3.5')}>
          <button
            onClick={onCompose}
            title="Compose"
            className={cn(
              'bg-gold text-ink rounded-2xl text-[13px] font-semibold flex items-center justify-center gap-2 hover:bg-gold-2 hover:text-white transition-colors shadow-[0_4px_14px_rgba(217,165,20,0.28)] h-11',
              collapsed ? 'w-11 mx-auto' : 'w-full',
            )}
          >
            <Icon name="edit_square" className="text-[18px]" />{!collapsed && 'Compose'}
          </button>
        </div>
        {NAV.map((grp) => (
          <div key={grp.label} className="px-2">
            {!collapsed && <div className="text-[9.5px] font-semibold text-ink-mute uppercase tracking-[0.16em] px-2 pt-4 pb-2">{grp.label}</div>}
            {collapsed && <div className="h-px bg-hairline mx-2 my-2 first:hidden" />}
            {grp.items.map((it) => {
              const active = section === it.section;
              const cnt = groupCount(it.section, data, mailCounts);
              return (
                <button
                  key={it.section}
                  title={collapsed ? it.label : undefined}
                  onClick={() => select(it.section, it.subs ? it.subs[0].table : '')}
                  className={cn(
                    'flex items-center gap-2.5 h-10 rounded-2xl text-[13px] cursor-pointer select-none w-full text-left transition-colors',
                    collapsed ? 'justify-center px-0' : 'px-3.5',
                    active ? ITEM_ON : ITEM_OFF,
                  )}
                >
                  <Icon name={it.icon} className="text-[18px] shrink-0" />
                  {!collapsed && <span className="flex-1 truncate">{it.label}</span>}
                  {!collapsed && cnt != null && (
                    <span className={cn('text-[10.5px] font-semibold tabular-nums rounded-full px-2 py-0.5', active ? 'bg-white/16 text-white' : 'bg-[rgba(10,10,10,0.06)] text-ink-4')}>
                      {fmt(cnt)}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* Actions: back to desk + collapse toggle */}
      <div className={cn('border-t border-hairline py-1.5', collapsed ? 'px-2' : 'px-2')}>
        <SideAction icon="grid_view" label="Back to Desk" collapsed={collapsed} onClick={() => { window.location.href = '/app'; }} />
        <SideAction icon={collapsed ? 'chevron_right' : 'chevron_left'} label="Collapse" collapsed={collapsed} onClick={onToggleCollapse} />
      </div>

      <UserFooter onSettings={onSettings} collapsed={collapsed} />
    </aside>
  );
}

function SideAction({ icon, label, collapsed, onClick }) {
  return (
    <button
      onClick={onClick}
      title={label}
      className={cn(
        'flex items-center gap-2.5 h-9 rounded-2xl text-[12.5px] text-ink-4 hover:bg-hover hover:text-ink w-full transition-colors',
        collapsed ? 'justify-center px-0' : 'px-3.5',
      )}
    >
      <Icon name={icon} className="text-[18px] shrink-0" />
      {!collapsed && <span className="truncate">{label}</span>}
    </button>
  );
}

function UserFooter({ onSettings, collapsed }) {
  const boot = getBoot();
  const name = boot.fullName || boot.user || 'User';
  const email = boot.user || '';
  const img = typeof window !== 'undefined' ? window.frappe_user_image : '';
  return (
    <button
      onClick={onSettings}
      title="Settings"
      className={cn('flex items-center gap-2.5 border-t border-hairline hover:bg-hover text-left w-full shrink-0', collapsed ? 'justify-center px-2 py-3' : 'px-4 py-3.5')}
    >
      <Avatar className="h-9 w-9 shrink-0">
        {img ? <AvatarImage src={img} alt={name} /> : null}
        <AvatarFallback>{initials(name)}</AvatarFallback>
      </Avatar>
      {!collapsed && (
        <>
          <div className="min-w-0 flex-1">
            <div className="text-[13px] font-medium text-ink truncate">{name}</div>
            <div className="text-[10.5px] text-ink-mute truncate">{email}</div>
          </div>
          <Icon name="settings" className="text-[17px] text-ink-mute" />
        </>
      )}
    </button>
  );
}
