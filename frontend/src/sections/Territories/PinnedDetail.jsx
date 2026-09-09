import { Bar, Empty, Note, Row, Section, compact } from './atoms';

/**
 * Everything that loads only once a territory is pinned.
 *
 * Split out of IntelPanel because the panel's job is the always-visible header
 * and the hover preview, while this is the deep read. Keeping them in one file
 * meant a component that changed for two unrelated reasons.
 */
export default function PinnedDetail({ detail, currency }) {
  if (!detail) return null;

  const flowers = detail.flowers?.rows || [];
  const flowerMax = Math.max(1, ...flowers.map((f) => f.amount || 0));
  const topMax = Math.max(1, ...(detail.top_accounts || []).map((a) => a.amount || 0));
  const claimMax = Math.max(1, ...(detail.claim_types || []).map((c) => c.count || 0));
  const stageMax = Math.max(1, ...(detail.stages || []).map((s) => s.count || 0));
  const reasons = detail.claim_reasons || {};

  return (
    <>
      <Section title="Top varieties">
        {flowers.length ? (
          <>
            {flowers.map((f) => (
              <Bar
                key={f.label}
                label={f.label}
                sub={f.grp}
                value={f.amount}
                max={flowerMax}
                currency={currency}
              />
            ))}
            {/* Not a footnote. On this site the un-coded lines outweigh every
                named variety, so a list that stayed silent about them would
                imply a completeness it does not have. */}
            {detail.flowers?.unattributed > 0 && (
              <Note>
                {compact(detail.flowers.unattributed, currency)} on invoice lines with no
                item code, excluded above.
              </Note>
            )}
          </>
        ) : (
          <Empty>No itemised sales in range.</Empty>
        )}
      </Section>

      <Section title="Claims">
        {detail.claim_types?.length ? (
          <>
            {detail.claim_types.map((c) => (
              <Bar
                key={c.label}
                label={c.label}
                sub={`${compact(c.stems)} stems · ${compact(c.amount, currency)}`}
                value={c.count}
                max={claimMax}
              />
            ))}
            {reasons.total > 0 && (
              <Note>
                {reasons.covered
                  ? `Reason recorded on ${reasons.covered} of ${reasons.total} claims.`
                  : `No itemised reason on any of these ${reasons.total} claims — the field exists but is unfilled.`}
              </Note>
            )}
          </>
        ) : (
          <Empty>No claims raised here.</Empty>
        )}
      </Section>

      {reasons.rows?.length > 0 && (
        <Section title="Claim reasons">
          {reasons.rows.map((r) => (
            <Row key={`${r.label}-${r.detail}`} label={r.detail || r.label} value={r.count} />
          ))}
        </Section>
      )}

      {detail.fulfilment?.stages?.length > 0 && (
        <Section title="Order fulfilment">
          {detail.fulfilment.stages.map((st) => (
            <Bar
              key={st.label}
              label={st.label}
              value={st.orders}
              max={Math.max(1, ...detail.fulfilment.stages.map((x) => x.orders || 0))}
            />
          ))}
          {/* The chain is drawn only where it is actually joined. Saying which
              stages are missing is the point — a funnel that quietly started at
              "Ordered" would imply harvest data had been considered. */}
          {detail.fulfilment.gaps?.map((g) => (
            <Note key={g}>{g}</Note>
          ))}
        </Section>
      )}

      <Section title="In contact">
        {detail.staff?.length ? (
          detail.staff.map((s) => (
            <div key={s.staff} className="flex items-baseline justify-between gap-3 py-[3px]">
              <span className="truncate text-[11px]" style={{ color: 'rgba(255,255,255,0.78)' }}>
                {s.staff_name}
                {s.shared && (
                  <span className="ml-1.5 text-[9px] uppercase" style={{ color: 'rgba(255,255,255,0.28)' }}>
                    shared
                  </span>
                )}
              </span>
              <span
                className="shrink-0 font-mono text-[10px] tabular-nums"
                style={{ color: 'rgba(255,255,255,0.52)' }}
              >
                {s.emails} · {s.accounts} acct
              </span>
            </div>
          ))
        ) : (
          <Empty>Nobody has emailed a customer here.</Empty>
        )}
      </Section>

      <Section title="Top accounts">
        {detail.top_accounts?.length ? (
          detail.top_accounts.map((a) => (
            <Bar key={a.label} label={a.label} value={a.amount} max={topMax} currency={currency} />
          ))
        ) : (
          <Empty>No billed revenue in range.</Empty>
        )}
      </Section>

      <Section title="Stage split">
        {detail.stages?.length ? (
          detail.stages.map((s) => (
            <Bar key={s.label} label={`${s.label} · ${s.count}`} value={s.count} max={stageMax} />
          ))
        ) : (
          <Empty>No open opportunities.</Empty>
        )}
      </Section>

      {detail.consignees?.length > 0 && (
        <Section title="Consignees">
          {detail.consignees.map((c) => (
            <div key={c.label} className="truncate py-[3px] text-[11px]" style={{ color: 'rgba(255,255,255,0.78)' }}>
              {c.label}
            </div>
          ))}
          {/* The consignee master is free text and many rows are addresses
              rather than company names. Say so rather than let it read as a
              broken list. */}
          <Note>Consignee records are free text; some are addresses.</Note>
        </Section>
      )}

      <Section title="Recent activity">
        {detail.recent?.length ? (
          detail.recent.map((x) => (
            <div key={`${x.doctype}-${x.name}`} className="flex items-baseline justify-between gap-3 py-1">
              <span className="truncate text-[11px]" style={{ color: 'rgba(255,255,255,0.78)' }}>
                {x.title || x.name}
              </span>
              <span
                className="shrink-0 font-mono text-[10px] uppercase"
                style={{ color: 'rgba(255,255,255,0.28)' }}
              >
                {x.doctype === 'Lead' ? 'LEAD' : 'OPP'}
              </span>
            </div>
          ))
        ) : (
          <Empty>Nothing logged.</Empty>
        )}
      </Section>
    </>
  );
}
