import { useStore } from '../../store';
import { Button } from '@/components/ui/button';
import Icon from '../../components/Icon';
import CampaignsDashboard from './Dashboard';
import CampaignsTable from './CampaignsTable';
import Enrolments from './Enrolments';
import Audiences from './Audiences';

function Actions() {
  const openCampaignDialog = useStore((s) => s.openCampaignDialog);
  const openEnrolDialog = useStore((s) => s.openEnrolDialog);
  const campaigns = useStore((s) => s.data.campaigns?.campaigns) || [];
  const sendable = campaigns.filter((c) => c.steps).length;

  return (
    <div className="flex items-center gap-2.5 mb-5 flex-wrap">
      <Button size="sm" onClick={() => openCampaignDialog({})}
        className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-4">
        <Icon name="campaign" className="text-[16px]" />New campaign
      </Button>
      <Button size="sm" variant="outline" onClick={() => openEnrolDialog({})}
        disabled={!sendable} className="rounded-full px-4">
        <Icon name="send" className="text-[16px]" />Enrol recipients
      </Button>
      {!sendable && campaigns.length > 0 && (
        <span className="text-[12px] text-warn">
          no campaign has a schedule yet, so none can send
        </span>
      )}
    </div>
  );
}

export default function Campaigns() {
  const table = useStore((s) => s.table);
  return (
    <>
      <Actions />
      {table === 'rows' ? <CampaignsTable />
        : table === 'enrol' ? <Enrolments />
          : table === 'mine' ? <Enrolments mine />
            : table === 'audiences' ? <Audiences />
              : <CampaignsDashboard />}
    </>
  );
}
