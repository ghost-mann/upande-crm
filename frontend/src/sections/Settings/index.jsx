import { useStore } from '../../store';
import General from './General';
import Targets from './Targets';
import Pipeline from './Pipeline';
import Activity from './Activity';
import WhatsAppSettings from './WhatsApp';
import Theme from './Theme';
import Integrations from './Integrations';

// Tab router for the Settings section, driven by the same `table` key the rest of
// the app uses, so the sidebar sub-nav and the tab strip stay in sync.
const TABS = {
  '': General,
  targets: Targets,
  pipeline: Pipeline,
  activity: Activity,
  wa: WhatsAppSettings,
  theme: Theme,
  health: Integrations,
};

export default function Settings() {
  const table = useStore((s) => s.table);
  const Tab = TABS[table] || General;
  return <Tab />;
}
