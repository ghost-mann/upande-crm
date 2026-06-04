import { useEffect, useState } from 'react';
import TopBar from './components/TopBar';
import Sidebar from './components/Sidebar';
import SettingsSheet from './components/SettingsSheet';
import ComposeDialog from './components/ComposeDialog';
import Overview from './sections/Overview';
import Mail from './sections/Mail';
import Leads from './sections/Leads';
import Opportunities from './sections/Opportunities';
import Prospects from './sections/Prospects';
import Customers from './sections/Customers';
import Events from './sections/Events';
import Activity from './sections/Activity';
import { useStore, setupAutoRefresh, SECTION_META } from './store';

const SECTIONS = {
  overview: Overview, mail: Mail, leads: Leads, opps: Opportunities,
  prosp: Prospects, cust: Customers, evt: Events, act: Activity,
};

function fmtTime(d) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export default function App() {
  const { section, loadAll, lastUpdated, customerFilter } = useStore();
  const openCompose = useStore((s) => s.openCompose);
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    loadAll();
    setupAutoRefresh();
  }, [loadAll]);

  const meta = SECTION_META[section] || SECTION_META.overview;
  const updated = lastUpdated ? fmtTime(lastUpdated) : '—';
  const Section = SECTIONS[section] || Overview;

  return (
    <div className="flex flex-col h-screen text-ink">
      <TopBar onSettings={() => setSettingsOpen(true)} />
      <div className="grid grid-cols-[230px_1fr] h-[calc(100vh-48px)]">
        <Sidebar onCompose={() => openCompose({})} onSettings={() => setSettingsOpen(true)} />
        <main className="bg-surface overflow-hidden flex flex-col">
          <div className="flex items-end justify-between gap-3 px-5 pt-3.5 pb-2.5 border-b border-line">
            <div>
              <div className="text-[18px] font-semibold -tracking-[0.01em]">{meta.title}</div>
              <div className="font-mono text-[10px] text-ink-3 uppercase tracking-[0.1em] mt-0.5">
                {meta.sub}{customerFilter ? ` · ${customerFilter}` : ''}
              </div>
            </div>
            <div className="font-mono text-[10.5px] text-ink-3">Updated {updated}</div>
          </div>
          <div className="flex-1 overflow-y-auto px-5 pt-3.5 pb-8">
            <Section />
          </div>
        </main>
      </div>
      <SettingsSheet open={settingsOpen} onOpenChange={setSettingsOpen} />
      <ComposeDialog />
    </div>
  );
}
