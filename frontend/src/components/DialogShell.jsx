import { Button } from '@/components/ui/button';
import Icon from './Icon';

// The CRM's dialog frame: ink title bar, scrolling body, save bar. Matches the
// call/event/task dialogs so a new form looks like it belongs.
export const LABEL = 'text-[10px] uppercase tracking-[0.14em] text-ink-mute font-medium mb-1.5 block';
export const SELECT = 'h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm outline-none focus:ring-1 focus:ring-ring';

export default function DialogShell({ title, onClose, onSave, saving, err, saveLabel = 'Save', width = 640, children }) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4" role="dialog" aria-modal="true">
      <div className="flex flex-col max-w-[96vw] max-h-[92vh] rounded-dialog shadow-2xl border border-hairline bg-surface overflow-hidden"
        style={{ width }}>
        <div className="h-11 shrink-0 bg-grad-ink text-white flex items-center gap-1 pl-4 pr-1.5">
          <span className="text-[14px] font-semibold truncate flex-1">{title}</span>
          <button className="w-7 h-7 rounded flex items-center justify-center hover:bg-white/15" onClick={onClose} title="Close">
            <Icon name="close" className="text-[18px]" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto crm-scroll p-5 grid gap-4">{children}</div>
        <div className="shrink-0 border-t border-hairline px-5 py-3 flex items-center gap-3">
          <Button size="sm" onClick={onSave} disabled={saving}
            className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-5">
            <Icon name="check" className="text-[16px]" />{saving ? 'Saving…' : saveLabel}
          </Button>
          <button type="button" onClick={onClose} className="text-[13px] text-ink-3 hover:text-ink">Cancel</button>
          {err && <span className="text-[12px] text-bad ml-auto text-right">{err}</span>}
        </div>
      </div>
    </div>
  );
}
