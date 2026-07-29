import { useEffect } from 'react';
import { useStore } from '../../store';
import { Button } from '@/components/ui/button';
import Icon from '../../components/Icon';
import { Panel, Row, StatusDot } from './parts';

const TONE = {
  ok: { label: 'OK', cls: 'bdg-good' },
  warn: { label: 'Attention', cls: 'bdg-warn' },
  off: { label: 'Off', cls: 'bdg-other' },
  missing: { label: 'Missing', cls: 'bdg-bad' },
};

function Check({ c }) {
  const tone = TONE[c.status] || TONE.off;
  return (
    <div className="py-3.5 border-b border-hairline last:border-b-0 flex items-start gap-3">
      <div className="pt-1.5"><StatusDot status={c.status} /></div>
      <div className="min-w-0 flex-1">
        <div className="text-[13px] text-ink font-medium">{c.label}</div>
        <div className="text-[12px] text-ink-2 mt-0.5">{c.detail}</div>
        {c.hint && (
          <div className="text-[11.5px] text-ink-mute mt-1 flex items-start gap-1.5">
            <Icon name="info" className="text-[13px] mt-px" />{c.hint}
          </div>
        )}
      </div>
      <span className={`bdg ${tone.cls} shrink-0`}>{tone.label}</span>
    </div>
  );
}

export default function Integrations() {
  const health = useStore((s) => s.health);
  const loading = useStore((s) => s.healthLoading);
  const loadHealth = useStore((s) => s.loadHealth);

  useEffect(() => { if (!health) loadHealth(); }, [health, loadHealth]);

  const checks = health?.checks || [];
  const problems = checks.filter((c) => c.status === 'warn' || c.status === 'missing').length;

  return (
    <div>
      <Panel
        title="Integration health"
        sub="What the CRM depends on, and whether it is actually working"
        aside={
          <Button
            size="sm" variant="outline" onClick={loadHealth} disabled={loading}
            className="rounded-full h-9"
          >
            <Icon name="refresh" className="text-[16px]" />{loading ? 'Checking…' : 'Re-check'}
          </Button>
        }
      >
        {loading && !checks.length ? (
          <div className="crm-empty">Checking…</div>
        ) : health?.error ? (
          <div className="crm-empty">Could not run the health checks</div>
        ) : !checks.length ? (
          <div className="crm-empty">No checks reported</div>
        ) : (
          <>
            <div className="text-[12px] mb-1">
              {problems ? (
                <span className="text-warn font-medium">
                  {problems} of {checks.length} checks need attention
                </span>
              ) : (
                <span className="text-good font-medium">All {checks.length} checks are healthy</span>
              )}
            </div>
            {checks.map((c) => <Check key={c.key} c={c} />)}
          </>
        )}
      </Panel>

      <Panel title="This site" sub="Context every figure in the CRM is reported against">
        <Row label="Company">
          <span className="text-[12.5px] text-ink-2">{health?.company || '—'}</span>
        </Row>
        <Row label="Reporting currency" help="Money is summed from base_* columns, so it is always this currency.">
          <span className="text-[12.5px] text-ink-2">{health?.currency || '—'}</span>
        </Row>
        <Row label="Signed in as">
          <span className="font-mono text-[11.5px] text-ink-2">{health?.user?.name || '—'}</span>
        </Row>
        <Row label="CRM roles">
          <span className="flex flex-wrap gap-1.5 justify-end">
            {(health?.user?.roles || []).length
              ? health.user.roles.map((r) => <span key={r} className="bdg bdg-other">{r}</span>)
              : <span className="text-[12.5px] text-ink-mute">—</span>}
          </span>
        </Row>
      </Panel>
    </div>
  );
}
