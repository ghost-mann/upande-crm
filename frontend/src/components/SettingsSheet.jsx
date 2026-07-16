import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter } from '@/components/ui/sheet';
import { Input } from '@/components/ui/input';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { useStore, setupAutoRefresh } from '../store';
import { getBoot } from '@shared/api';
import { cn } from '@/lib/utils';

function Toggle({ on, onClick }) {
  return (
    <button onClick={onClick} className={cn('w-9 h-5 rounded-full relative transition-colors shrink-0', on ? 'bg-gold' : 'bg-line-2')}>
      <span className={cn('absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all', on ? 'left-[18px]' : 'left-0.5')} />
    </button>
  );
}

function Group({ title, children }) {
  return (
    <div className="grid gap-2.5">
      <h4 className="text-xs font-semibold text-ink">{title}</h4>
      {children}
    </div>
  );
}
function Row({ label, children }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <label className="text-xs text-ink-2">{label}</label>
      {children}
    </div>
  );
}

const RANGES = [['7d', 'Last 7 days'], ['30d', 'Last 30 days'], ['90d', 'Last 90 days'], ['ytd', 'Year to date']];

export default function SettingsSheet({ open, onOpenChange }) {
  const { settings, saveSettings } = useStore();
  const boot = getBoot();
  const updRefresh = (patch) => { saveSettings(patch); setupAutoRefresh(); };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader><SheetTitle>Settings</SheetTitle></SheetHeader>
        <div className="flex-1 overflow-y-auto p-4 grid gap-6">
          <Group title="Auto-refresh">
            <Row label="Enabled"><Toggle on={settings.autoRefresh} onClick={() => updRefresh({ autoRefresh: !settings.autoRefresh })} /></Row>
            <Row label="Interval (seconds)">
              <Input type="number" min={15} max={3600} step={5} value={settings.refreshIntervalSec}
                onChange={(e) => updRefresh({ refreshIntervalSec: Number(e.target.value) })} className="w-20 h-8" />
            </Row>
          </Group>
          <Group title="Defaults">
            <Row label="Default date range">
              <Select value={settings.defaultDateRange} onValueChange={(v) => saveSettings({ defaultDateRange: v })}>
                <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
                <SelectContent>{RANGES.map(([k, l]) => <SelectItem key={k} value={k}>{l}</SelectItem>)}</SelectContent>
              </Select>
            </Row>
            <Row label="Open Frappe in new tab"><Toggle on={settings.openInNewTab} onClick={() => saveSettings({ openInNewTab: !settings.openInNewTab })} /></Row>
          </Group>
          <Group title="Account">
            <Row label="Signed in as"><span className="font-mono text-[11px] text-ink-2">{boot.user || '—'}</span></Row>
          </Group>
        </div>
        <SheetFooter>CRM · {boot.brandName} · v1.0</SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
