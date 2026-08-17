import { fmt } from '@shared/utils';
import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';
import { useStore } from '../../store';
import { openFrappe } from '@/lib/crm';
import FilterPopover from '../../components/FilterPopover';

// The funnel, drawn as one.
//
// What was here before was five bars whose counts shared no records: leads,
// opportunities, quotations, orders and conversions each queried independently.
// On this site that reported 4 leads beside 1,429 orders, which is not a funnel
// narrowing — it is four unrelated numbers stacked by height. `api/funnel.py` now
// walks a single lead cohort forward, so every stage below is a subset of the one
// above it and the shape cannot widen.
//
// Three stages, not five. Quotations and Prospects are both branches off the path
// rather than steps along it, and inserting either makes the shape bulge back out.
// The prospect route is drawn *inside* the opportunity band, where it decomposes
// that stage instead of contradicting it.

// Ink → gold, descending. Read as: the further down, the more valuable.
const RAMP = [
  'linear-gradient(180deg, #3a3a34 0%, #2a2a26 100%)',
  'linear-gradient(180deg, #8a6a10 0%, #6f5510 100%)',
  'linear-gradient(180deg, #d9a514 0%, #a87d0d 100%)',
];

const BAND_H = 78;
const GAP_H = 34;
// A stage with almost nothing in it still needs to be visible and hold its label.
const MIN_WIDTH = 22;
// How far a leak wedge may reach into the right margin.
const LEAK_MAX = 30;

const half = (w) => w / 2;

function bandClip(topW, botW) {
  const t = half(topW);
  const b = half(botW);
  return `polygon(${50 - t}% 0%, ${50 + t}% 0%, ${50 + b}% 100%, ${50 - b}% 100%)`;
}

function StageRow({ stage, index, topW, botW, ofFirst }) {
  const newTab = useStore((s) => s.settings.openInNewTab);
  const samples = stage.sample || [];
  const via = stage.via_prospect || 0;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_150px] items-center gap-4"
      style={{ height: BAND_H }}>
      <FilterPopover
        align="start"
        width={300}
        trigger={
          <button type="button" className="relative block w-full text-left group"
            style={{ height: BAND_H }}
            title={samples.length ? 'Show the records behind this stage' : undefined}>
            <span className="absolute inset-0 transition-opacity group-hover:opacity-90"
              style={{ background: RAMP[index % RAMP.length], clipPath: bandClip(topW, botW) }} />
            {/* The prospect route, decomposing this band rather than preceding it.
                Absent on this site — no prospect carrying a lead link has an
                opportunity — so it simply does not render. */}
            {via > 0 && (
              <span className="absolute inset-0 bg-white/20"
                style={{ clipPath: bandClip(topW * (via / stage.count), botW * (via / stage.count)) }} />
            )}
            {/* The count only. The stage name lives in the meta column, because a
                narrow band cannot hold it — "Became an opportunity" ran straight
                out through both walls of a stage floored to its minimum width. */}
            <span className="absolute inset-0 flex items-center justify-center text-white">
              <span className="text-[20px] font-semibold tabular-nums leading-none">
                {fmt(stage.count)}
              </span>
            </span>
          </button>
        }
      >
        {() => (
          <div className="grid gap-1.5">
            <div className="text-[10px] uppercase tracking-wide text-ink-mute font-medium">
              {stage.label} · {fmt(stage.count)}
            </div>
            {samples.length ? (
              <div className="max-h-64 overflow-y-auto crm-scroll grid gap-px">
                {samples.map((r) => (
                  <button key={r.name} type="button"
                    onClick={() => openFrappe(stage.key === 'leads' ? 'Lead' : 'Opportunity', r.name, newTab)}
                    className="text-left px-2 py-1.5 rounded-lg hover:bg-hover">
                    <div className="text-[12.5px] text-ink truncate">{r.label}</div>
                    <div className="text-[10.5px] text-ink-mute truncate">{r.name}</div>
                  </button>
                ))}
              </div>
            ) : <div className="crm-empty !py-3">Nothing at this stage</div>}
            {stage.count > samples.length && (
              <div className="text-[10.5px] text-ink-mute px-2">
                showing {samples.length} of {fmt(stage.count)}
              </div>
            )}
          </div>
        )}
      </FilterPopover>

      <div>
        <div className="text-[12.5px] text-ink font-medium leading-tight">{stage.label}</div>
        <div className="text-[11.5px] text-ink-mute tabular-nums mt-0.5">
          {index === 0 ? 'entering' : `${ofFirst}% of leads`}
        </div>
        {via > 0 && (
          <div className="text-[11px] text-gold-text tabular-nums mt-0.5">
            {fmt(via)} via prospect
          </div>
        )}
      </div>
    </div>
  );
}

function LeakRow({ dropped, label, edgeW, share }) {
  // The wedge starts where the funnel wall is and peels outward, so the leak reads
  // as coming off the shape rather than floating beside it.
  const left = 50 + half(edgeW);
  // Floored at 8% so a small leak is still a visible wedge rather than a sliver,
  // and capped at the right margin so it never runs under the meta column.
  const width = Math.min(Math.max(share * LEAK_MAX, 8), Math.max(100 - left - 1, 8));
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_150px] items-center gap-4" style={{ height: GAP_H }}>
      <div className="relative h-full">
        {/* Opacity comes from the style attribute, not from a `bg-bad/55` utility.
            The theme's semantic colours are bare `var(--bad)` rather than channel
            triples, and Tailwind's slash modifier compiles those into an invalid
            colour — the wedge silently rendered as nothing. */}
        <span
          className="absolute top-1/2 -translate-y-1/2 h-[18px]"
          style={{
            left: `${left}%`,
            width: `${width}%`,
            background: 'var(--bad)',
            opacity: 0.55,
            clipPath: 'polygon(0% 0%, 100% 34%, 100% 66%, 0% 100%)',
          }}
        />
      </div>
      <div className="text-[11.5px] text-ink-mute leading-tight">
        <span className="text-bad font-semibold tabular-nums">−{fmt(dropped)}</span> {label}
      </div>
    </div>
  );
}

export default function Funnel() {
  const stages = useStore((s) => s.data.command?.funnel) || [];
  if (!stages.length) {
    return (
      <Card>
        <CardHeader><div><CardTitle>Sales funnel</CardTitle></div></CardHeader>
        <CardContent><div className="crm-empty">No funnel data</div></CardContent>
      </Card>
    );
  }

  const first = stages[0]?.count || 0;

  // No cohort, no funnel. Three bands all floored to the same minimum width is a
  // rectangle claiming to be a shape, and every percentage on it reads 0% — the
  // date range simply has no leads in it, which is worth saying rather than
  // drawing.
  if (!first) {
    return (
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Sales funnel</CardTitle>
            <CardSub>Leads created in this range, followed forward</CardSub>
          </div>
        </CardHeader>
        <CardContent>
          <div className="crm-empty">No leads were created in this range</div>
        </CardContent>
      </Card>
    );
  }

  // Width is proportional to the cohort it came from, floored so a near-empty
  // stage stays readable. The floor only affects the drawing — every number shown
  // is the real one.
  const widthOf = (c) => Math.max((c / first) * 100, MIN_WIDTH);

  const rows = [];
  stages.forEach((s, i) => {
    const next = stages[i + 1];
    const topW = widthOf(s.count);
    const botW = next ? widthOf(next.count) : topW * 0.92;
    rows.push(
      <StageRow key={s.key} stage={s} index={i} topW={topW} botW={botW} ofFirst={s.of_first} />,
    );
    if (next && s.dropped > 0) {
      rows.push(
        <LeakRow key={`${s.key}-leak`} dropped={s.dropped} label={s.dropped_label}
          edgeW={botW} share={first ? s.dropped / first : 0} />,
      );
    }
  });

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Sales funnel</CardTitle>
          <CardSub>
            The same {fmt(first)} leads followed forward — not each stage counted on its own
          </CardSub>
        </div>
      </CardHeader>
      <CardContent>
        <div className="pt-1 pb-2">{rows}</div>
        <div className="text-[11px] text-ink-mute leading-relaxed border-t border-hairline pt-3 mt-1">
          Every stage is a subset of the one above it, so the shape can only narrow.
          Quotations and prospects are branches off this path rather than steps along
          it — a prospect-routed opportunity is counted inside “became an opportunity”.
          Click a stage for the records behind it.
        </div>
      </CardContent>
    </Card>
  );
}
