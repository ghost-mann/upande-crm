import { fmtMoney, fmtMoneyCompact } from '@shared/utils';
import { useStore } from '../../store';
import { Input } from '@/components/ui/input';
import { Panel, Row, SelectBox, SaveBar, Meter, useOrgForm } from './parts';

const KEYS = ['revenue_target_monthly', 'revenue_target_annual', 'target_basis'];
const BASIS_LABELS = { Billed: 'Billed — submitted Sales Invoices', Booked: 'Booked — submitted Sales Orders' };

// Ahead/behind is the whole point of a target: 39% of a monthly target is good on
// the 10th and bad on the 28th, so attainment is always shown against elapsed time.
function Attainment({ label, actual, target, pct, elapsed, ccy, period }) {
  if (!target) {
    return (
      <div className="py-3 border-b border-hairline last:border-b-0">
        <div className="text-[13px] text-ink font-medium">{label}</div>
        <div className="text-[12px] text-ink-mute mt-1">
          No target set · {fmtMoney(actual, ccy)} so far this {period}
        </div>
      </div>
    );
  }
  const behind = pct < elapsed - 5;
  const ahead = pct > elapsed + 5;
  return (
    <div className="py-3.5 border-b border-hairline last:border-b-0">
      <div className="flex items-baseline justify-between gap-4 mb-2">
        <div className="text-[13px] text-ink font-medium">{label}</div>
        <div className="text-[12px] text-ink-mute tabular-nums">
          {fmtMoneyCompact(actual, ccy)} of {fmtMoneyCompact(target, ccy)}
        </div>
      </div>
      <Meter pct={pct} marker={elapsed} tone={behind ? 'bad' : ahead ? 'good' : 'gold'} />
      <div className="flex items-center justify-between gap-4 mt-1.5">
        <div className="text-[11.5px] text-ink-mute">
          {elapsed}% of the {period} elapsed
        </div>
        <div className={`text-[11.5px] font-medium ${behind ? 'text-bad' : ahead ? 'text-good' : 'text-ink-2'}`}>
          {pct}% attained · {behind ? 'behind pace' : ahead ? 'ahead of pace' : 'on pace'}
        </div>
      </div>
    </div>
  );
}

export default function Targets() {
  const form = useOrgForm(KEYS);
  const ccy = useStore((s) => s.orgMeta.currency);
  const t = useStore((s) => s.data.sales?.targets);
  const basisOptions = useStore((s) => s.orgMeta.options?.target_basis) || ['Billed', 'Booked'];

  return (
    <div>
      <Panel
        title="Revenue targets"
        sub={`In ${ccy} — the company's default currency, the same basis every figure in the CRM uses`}
      >
        <Row label="Monthly target" help="Attainment is measured over the current calendar month.">
          <Input
            type="number" min={0} step={1000} disabled={form.disabled}
            value={form.draft.revenue_target_monthly ?? 0}
            onChange={(e) => form.set({ revenue_target_monthly: e.target.value === '' ? 0 : Number(e.target.value) })}
            className="w-[190px] h-9 text-right tabular-nums"
          />
        </Row>
        <Row label="Annual target" help="Measured over the calendar year to date.">
          <Input
            type="number" min={0} step={10000} disabled={form.disabled}
            value={form.draft.revenue_target_annual ?? 0}
            onChange={(e) => form.set({ revenue_target_annual: e.target.value === '' ? 0 : Number(e.target.value) })}
            className="w-[190px] h-9 text-right tabular-nums"
          />
        </Row>
        <Row
          label="Measure attainment on"
          help="Billed counts what has been invoiced; Booked counts order value the moment it is won."
        >
          <SelectBox
            value={form.draft.target_basis} options={basisOptions} labels={BASIS_LABELS}
            disabled={form.disabled} className="w-[280px]"
            onChange={(v) => form.set({ target_basis: v })}
          />
        </Row>
        <SaveBar form={form} />
      </Panel>

      <Panel
        title="Current attainment"
        sub="Against the saved targets · not affected by the header date range"
      >
        {t ? (
          <>
            <Attainment
              label={`This month · ${t.basis.toLowerCase()}`} period="month"
              actual={t.mtd} target={t.monthly} pct={t.mtd_pct} elapsed={t.month_elapsed_pct} ccy={ccy}
            />
            <Attainment
              label={`${t.year} to date · ${t.basis.toLowerCase()}`} period="year"
              actual={t.ytd} target={t.annual} pct={t.ytd_pct} elapsed={t.year_elapsed_pct} ccy={ccy}
            />
            <div className="mt-3 text-[11.5px] text-ink-mute">
              Measured from {t.source}. A target belongs to its calendar period, so these two
              figures ignore the date range in the page header.
            </div>
          </>
        ) : (
          <div className="crm-empty">Sales analytics unavailable</div>
        )}
      </Panel>
    </div>
  );
}
