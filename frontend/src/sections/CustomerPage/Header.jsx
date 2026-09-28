import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { fmt, fmtDate, fmtMoney, fmtMoneyCompact } from '@shared/utils';
import { useStore } from '../../store';
import { KpiRow } from '../../components/Kpi';
import Icon from '../../components/Icon';
import { openFrappe, shortUser } from '@/lib/crm';

// Who the customer is, what they are worth, and the moves you make next.
// Every quick action respects its own module switch.
export default function Header({ header, onAddNote }) {
  const { customer: c, figures: f, currency } = header;
  const on = useStore((s) => s.moduleOn);
  useStore((s) => s.orgMeta.modules);
  const openCall = useStore((s) => s.openCallDialog);
  const openCompose = useStore((s) => s.openCompose);
  const openEvent = useStore((s) => s.openEventDialog);
  const newTab = useStore((s) => s.settings.openInNewTab);
  const ref = { doctype: 'Customer', name: c.name };

  const facts = [
    c.customer_group, c.territory,
    c.default_price_list && `Price list: ${c.default_price_list}`,
    c.account_manager && `Account: ${shortUser(c.account_manager)}`,
  ].filter(Boolean);


  return (
    <>
      <Card className="mb-5">
        <CardContent className="pt-5">
          <div className="flex items-start justify-between gap-6 flex-wrap">
            <div className="min-w-0">
              <div className="flex items-center gap-2.5 flex-wrap">
                <span className="text-[18px] font-semibold text-ink">{c.customer_name || c.name}</span>
                {c.disabled ? <span className="bdg bdg-bad">Disabled</span> : <span className="bdg bdg-good">Active</span>}
              </div>
              <div className="text-[12.5px] text-ink-3 mt-1">{facts.join(' · ') || '—'}</div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {on('calls') && (
                <Button size="sm" variant="outline" className="rounded-full"
                  onClick={() => openCall({ reference_doctype: 'Customer', reference_name: c.name })}>
                  <Icon name="call" className="text-[16px]" />Log call
                </Button>
              )}
              {on('mail') && (
                <Button size="sm" variant="outline" className="rounded-full" onClick={() => openCompose({ reference: ref })}>
                  <Icon name="mail" className="text-[16px]" />Email
                </Button>
              )}
              {on('evt') && (
                <Button size="sm" variant="outline" className="rounded-full"
                  onClick={() => openEvent({ participants: [{ reference_doctype: 'Customer', reference_docname: c.name }] })}>
                  <Icon name="event" className="text-[16px]" />New event
                </Button>
              )}
              {onAddNote && (
                <Button size="sm" variant="outline" className="rounded-full" onClick={onAddNote}>
                  <Icon name="edit_note" className="text-[16px]" />Add note
                </Button>
              )}
              <Button size="sm" variant="ghost" className="rounded-full" onClick={() => openFrappe('Customer', c.name, newTab)}>
                <Icon name="open_in_new" className="text-[16px]" />Open in desk
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
      <KpiRow items={[
        { lbl: 'Lifetime revenue', val: fmtMoneyCompact(f.lifetime_revenue, currency), sub: fmtMoney(f.lifetime_revenue, currency), compact: true },
        { lbl: 'In selected range', val: f.range_revenue == null ? '—' : fmtMoneyCompact(f.range_revenue, currency), sub: 'Invoiced in the date range', compact: true },
        { lbl: 'Orders', val: fmt(f.order_count), sub: 'Submitted sales orders', compact: true },
        { lbl: 'Average order', val: f.order_count ? fmtMoneyCompact(f.avg_order_value, currency) : '—', compact: true },
        { lbl: 'Last order', val: f.last_order_date ? fmtDate(f.last_order_date) : 'Never',
          sub: f.days_since_last_order != null ? `${fmt(f.days_since_last_order)} days ago` : null, compact: true },
        { lbl: 'Open quotations', val: fmt(f.open_quotations), compact: true },
        ...(f.open_claims != null ? [{ lbl: 'Open claims', val: fmt(f.open_claims), compact: true,
          chip: f.open_claims ? 'see Claims tab' : null, chipTone: f.open_claims ? 'down' : '' }] : []),
      ]} />
    </>
  );
}
