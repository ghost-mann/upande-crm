import { lazy, Suspense, useEffect, useState } from 'react';
import TopBar from './components/TopBar';
import Sidebar from './components/Sidebar';
import SectionTabs from './components/SectionTabs';
import PageTools from './components/PageTools';
import Overview from './sections/Overview/index.jsx';
import { useStore, setupAutoRefresh, SECTION_META } from './store';
import { getBoot } from '@shared/api';

// Overview is the default view (eager). Everything else is code-split so the
// initial load only parses what the landing screen needs.
const Mail = lazy(() => import('./sections/Mail'));
const Leads = lazy(() => import('./sections/Leads'));
const Opportunities = lazy(() => import('./sections/Opportunities'));
const Prospects = lazy(() => import('./sections/Prospects'));
const Customers = lazy(() => import('./sections/Customers'));
const Events = lazy(() => import('./sections/Events/index.jsx'));
const WhatsApp = lazy(() => import('./sections/WhatsApp/index.jsx'));
const Activity = lazy(() => import('./sections/Activity'));
const Settings = lazy(() => import('./sections/Settings/index.jsx'));
const Reports = lazy(() => import('./sections/Reports/index.jsx'));
const Calls = lazy(() => import('./sections/Calls/index.jsx'));
const Analytics = lazy(() => import('./sections/Analytics/index.jsx'));
const Campaigns = lazy(() => import('./sections/Campaigns/index.jsx'));
const ThreadView = lazy(() => import('./components/ThreadView'));
const ComposeDialog = lazy(() => import('./components/ComposeDialog'));
const EventDialog = lazy(() => import('./components/EventDialog'));
const TaskDialog = lazy(() => import('./components/TaskDialog'));
const CallDialog = lazy(() => import('./components/CallDialog'));
const CampaignDialog = lazy(() => import('./components/CampaignDialog'));
const EnrolDialog = lazy(() => import('./components/EnrolDialog'));

const SECTIONS = {
  overview: Overview, mail: Mail, wa: WhatsApp, leads: Leads, opps: Opportunities,
  prosp: Prospects, cust: Customers, evt: Events, act: Activity, set: Settings,
  rep: Reports, calls: Calls, anl: Analytics, camp: Campaigns,
};

function fmtTime(d) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export default function App() {
  const { section, loadAll, lastUpdated, customerFilter } = useStore();
  const openCompose = useStore((s) => s.openCompose);
  const openMsg = useStore((s) => s.openMsg);
  const loadOrg = useStore((s) => s.loadOrg);
  const select = useStore((s) => s.select);
  const waEnabled = useStore((s) => !!s.org?.whatsapp_enabled);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    // Organisation settings first: they decide the opening date range and which
    // sections exist, so resolving them after the fetch would load twice.
    (async () => {
      await loadOrg();
      loadAll();
      setupAutoRefresh();
    })();
  }, [loadOrg, loadAll]);

  // A section that settings have just switched off must not stay on screen.
  useEffect(() => {
    if (section === 'wa' && !waEnabled) select('overview');
  }, [section, waEnabled, select]);

  const meta = SECTION_META[section] || SECTION_META.overview;
  const updated = lastUpdated ? fmtTime(lastUpdated) : '—';
  const Section = SECTIONS[section] || Overview;

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <TopBar />
      <div className={`w-full px-5 md:px-8 pt-6 pb-20 grid ${collapsed ? 'grid-cols-[72px_minmax(0,1fr)]' : 'grid-cols-[240px_minmax(0,1fr)]'} max-[900px]:grid-cols-1 gap-6 items-start`}>
        <Sidebar collapsed={collapsed} onToggleCollapse={() => setCollapsed((c) => !c)} onCompose={() => openCompose({})} onSettings={() => select('set', '')} />
        <main className="min-w-0">
          <div className="flex items-end justify-between gap-8 pb-9">
            <div className="min-w-0">
              <div className="text-[11px] text-ink-mute uppercase tracking-[0.2em] font-medium mb-2.5 flex items-center gap-2.5 before:content-[''] before:w-[18px] before:h-px before:bg-ink-3">
                {getBoot().brandName}{customerFilter ? ` · ${customerFilter}` : ''}
              </div>
              <h1 className="text-[36px] md:text-[44px] font-semibold -tracking-[0.03em] leading-[1.05] text-ink">{meta.title}</h1>
              <p className="mt-2 text-[15px] text-ink-4">{meta.sub}</p>
            </div>
            <PageTools />
          </div>
          {!openMsg && <SectionTabs />}
          <div>
            <Suspense fallback={<div className="p-12 text-center text-ink-mute text-[13px]">Loading…</div>}>
              {openMsg ? <ThreadView /> : <Section />}
            </Suspense>
          </div>
        </main>
      </div>
      <Suspense fallback={null}>
        <ComposeDialog />
        <EventDialog />
        <TaskDialog />
        <CallDialog />
        <CampaignDialog />
        <EnrolDialog />
      </Suspense>
    </div>
  );
}
