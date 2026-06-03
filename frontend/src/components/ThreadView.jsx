import { useStore } from '../store';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import Icon from './Icon';
import { fmtDateTime } from '@shared/utils';

export default function ThreadView() {
  const m = useStore((s) => s.openMsg);
  const close = useStore((s) => s.closeMessage);
  const newTab = useStore((s) => s.settings.openInNewTab);
  if (!m) return null;

  return (
    <Card>
      <div className="flex items-center gap-2 px-3 h-12 border-b border-line">
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={close}><Icon name="arrow_back" className="text-[18px]" /></Button>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold truncate">{m.subject || '(no subject)'}</div>
          <div className="text-[11px] text-ink-3 truncate">
            {m.sender}{m.recipients ? ` → ${m.recipients}` : ''} · {fmtDateTime(m.communication_date)}
          </div>
        </div>
        {m.reference_doctype && m.reference_name && (
          <Button variant="outline" size="sm"
            onClick={() => window.open(`/app/${m.reference_doctype.toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(m.reference_name)}`, newTab ? '_blank' : '_self')}>
            <Icon name="open_in_new" className="text-[14px]" />{m.reference_doctype}
          </Button>
        )}
      </div>
      <div
        className="p-4 text-[13px] leading-relaxed [&_img]:max-w-full [&_a]:text-maroon [&_a]:underline"
        dangerouslySetInnerHTML={{ __html: m.content || '<p class="crm-empty">No content.</p>' }}
      />
    </Card>
  );
}
