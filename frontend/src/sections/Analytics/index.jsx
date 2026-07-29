import { useEffect } from 'react';
import { useStore } from '../../store';
import RangePicker from './RangePicker';
import Funnel from './Funnel';
import Leads from './Leads';
import Opportunities from './Opportunities';
import Revenue from './Revenue';

// Tab router for Analytics. Each tab owns one endpoint and loads on demand rather
// than all four at once — the funnel walks every lead forward, which is not work to
// do for a tab nobody opened.
const TABS = {
  '': ['funnel', Funnel],
  leads: ['leads', Leads],
  opps: ['opps', Opportunities],
  revenue: ['revenue', Revenue],
};

export default function Analytics() {
  const table = useStore((s) => s.table);
  const loadAnalytics = useStore((s) => s.loadAnalytics);
  const dateFrom = useStore((s) => s.dateFrom);
  const dateTo = useStore((s) => s.dateTo);
  const customer = useStore((s) => s.customerFilter);

  const [key, View] = TABS[table] || TABS[''];

  // Refetch on tab change and whenever the range or customer moves — analytics is
  // the section where changing the window is the whole point.
  useEffect(() => { loadAnalytics(key); }, [key, dateFrom, dateTo, customer, loadAnalytics]);

  return (
    <>
      <RangePicker />
      <View />
    </>
  );
}
