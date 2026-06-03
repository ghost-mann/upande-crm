import { useState } from 'react';
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

const MAIL_SUB_COUNT = {
  unread: 'inbox_unread', inbox: 'inbox', sent: 'sent_ok',
  crm_leads: 'crm_leads', crm_opps: 'crm_opps', crm_customers: 'crm_customers', crm_quotations: 'crm_quotations',
};

export default function Sidebar({ onCompose, onSettings }) {
  const section = useStore((s) => s.section);
  const table = useStore((s) => s.table);
  const select = useStore((s) => s.select);
  const [open, setOpen] = useState(() => ({ mail: true, [section]: true }));

  const handleSelect = (sec, tbl = '') => {
    select(sec, tbl);
    setOpen((o) => ({ ...o, [sec]: true }));
  };
  const toggle = (sec) => setOpen((o) => ({ ...o, [sec]: !o[sec] }));

  return (
    <aside className="bg-surface-2 border-r border-line flex flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto crm-scroll pt-2.5 pb-2">
        <div className="px-2.5 pb-2">
          <button onClick={onCompose} className="w-full h-9 bg-maroon text-white rounded-[5px] text-[13px] font-semibold flex items-center justify-center gap-2 hover:bg-maroon-2 transition-colors">
            <Icon name="edit_square" className="text-[18px]" />Compose
          </button>
        </div>
        {NAV.map((grp) => (
          <div key={grp.label}>
            <div className="font-mono text-[9px] font-semibold text-ink-3 uppercase tracking-[0.14em] px-3.5 pt-3 pb-1.5">{grp.label}</div>
            {grp.items.map((it) =>
              it.type === 'item' ? (
                <NavItem key={it.section} it={it} active={section === it.section && !table} onClick={() => handleSelect(it.section)} />
              ) : (
                <NavGroup key={it.section} it={it} section={section} table={table} open={!!open[it.section]} onToggle={() => toggle(it.section)} onSelect={handleSelect} />
              ),
            )}
          </div>
        ))}
      </div>
      <UserFooter onSettings={onSettings} />
    </aside>
  );
}

function UserFooter({ onSettings }) {
  const boot = getBoot();
  const name = boot.fullName || boot.user || 'User';
  const email = boot.user || '';
  const img = typeof window !== 'undefined' ? window.frappe_user_image : '';
  return (
    <button
      onClick={onSettings}
      title="Settings"
      className="flex items-center gap-2.5 px-3 py-2.5 border-t border-line hover:bg-hover text-left w-full shrink-0"
    >
      <Avatar className="h-8 w-8">
        {img ? <AvatarImage src={img} alt={name} /> : null}
        <AvatarFallback>{initials(name)}</AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1">
        <div className="text-xs font-medium text-ink truncate">{name}</div>
        <div className="text-[10px] text-ink-3 font-mono truncate">{email}</div>
      </div>
      <Icon name="settings" className="text-[16px] text-ink-3" />
    </button>
  );
}

function NavItem({ it, active, onClick }) {
  return (
    <div
      onClick={onClick}
      className={cn(
        'flex items-center gap-2.5 h-[30px] px-3 mx-1.5 rounded text-[12.5px] cursor-pointer select-none',
        active ? 'bg-maroon text-white font-medium' : 'text-ink-2 hover:bg-hover hover:text-ink',
      )}
    >
      <Icon name={it.icon} className="text-[17px] shrink-0" />
      <span>{it.label}</span>
    </div>
  );
}

function NavGroup({ it, section, table, open, onToggle, onSelect }) {
  const data = useStore((s) => s.data);
  const mailCounts = useStore((s) => s.mailFolder?.counts);
  const headActive = section === it.section && !table;
  const cnt = groupCount(it.section, data, mailCounts);

  return (
    <div className="mx-1.5">
      <div
        onClick={() => onSelect(it.section, '')}
        className={cn(
          'flex items-center gap-2.5 h-[30px] px-3 rounded text-[12.5px] cursor-pointer select-none',
          headActive ? 'bg-maroon text-white font-medium' : 'text-ink-2 hover:bg-hover hover:text-ink',
        )}
      >
        <Icon name={it.icon} className="text-[17px] shrink-0" />
        <span>{it.label}</span>
        <span className={cn('ml-auto font-mono text-[10px] font-medium', headActive ? 'text-white/80' : 'text-ink-3')}>
          {cnt != null ? fmt(cnt) : ''}
        </span>
        <Icon
          name="chevron_right"
          className={cn('text-[15px] transition-transform', headActive ? 'text-white/80' : 'text-ink-3', open && 'rotate-90')}
          onClick={(e) => { e.stopPropagation(); onToggle(); }}
        />
      </div>
      {open && (
        <div className="pt-0.5 pb-1">
          {it.subs.map((sub) => {
            const subCnt = it.section === 'mail' ? mailCounts?.[MAIL_SUB_COUNT[sub.table]] : undefined;
            const active = section === it.section && table === sub.table;
            return (
              <div
                key={sub.table || 'dash'}
                onClick={() => onSelect(it.section, sub.table)}
                className={cn(
                  'flex items-center gap-2 h-[26px] px-3 pl-8 mx-1 rounded text-xs cursor-pointer',
                  active ? 'bg-maroon-soft text-maroon-text font-medium' : 'text-ink-2 hover:bg-hover hover:text-ink',
                )}
              >
                <span>{sub.label}</span>
                {subCnt != null && <span className="ml-auto font-mono text-[10px] text-ink-3">{fmt(subCnt)}</span>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
