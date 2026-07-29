import { useStore, setupAutoRefresh } from '../../store';
import { getBoot } from '@shared/api';
import Icon from '../../components/Icon';
import { Panel, Row, Toggle, NumberBox, SelectBox, SaveBar, useOrgForm } from './parts';

const RANGE_LABELS = { '7d': 'Last 7 days', '30d': 'Last 30 days', '90d': 'Last 90 days', ytd: 'Year to date' };
const ORG_KEYS = ['default_date_range', 'auto_refresh', 'refresh_interval_sec'];

// Shows when a device preference has been pinned away from the org default, with
// a one-click way back — otherwise an org-wide change looks broken to whoever
// once toggled the setting locally.
function Override({ shown, onReset }) {
  if (!shown) return null;
  return (
    <button onClick={onReset} className="text-[11px] text-gold-text hover:underline flex items-center gap-1">
      <Icon name="undo" className="text-[13px]" />use the organisation default
    </button>
  );
}

function stored() {
  try { return JSON.parse(localStorage.getItem('crm_settings')) || {}; } catch { return {}; }
}

export default function General() {
  const settings = useStore((s) => s.settings);
  const saveSettings = useStore((s) => s.saveSettings);
  const resetSetting = useStore((s) => s.resetSetting);
  const meta = useStore((s) => s.orgMeta);
  const setDateRange = useStore((s) => s.setDateRange);
  const form = useOrgForm(ORG_KEYS);
  const boot = getBoot();
  const pinned = stored();

  const updRefresh = (patch) => { saveSettings(patch); setupAutoRefresh(); };
  const ranges = meta.options?.default_date_range || ['7d', '30d', '90d', 'ytd'];

  return (
    <div>
      <Panel
        title="This device"
        sub="Preferences stored in this browser only · they override the organisation defaults below"
      >
        <Row
          label="Auto-refresh"
          help="Re-reads every section in the background on the interval below."
          footer={<div className="mt-1.5"><Override shown={'autoRefresh' in pinned} onReset={() => { resetSetting('autoRefresh'); setupAutoRefresh(); }} /></div>}
        >
          <Toggle on={settings.autoRefresh} onClick={() => updRefresh({ autoRefresh: !settings.autoRefresh })} />
        </Row>
        <Row
          label="Refresh interval"
          help="Between 15 and 3600 seconds."
          footer={<div className="mt-1.5"><Override shown={'refreshIntervalSec' in pinned} onReset={() => { resetSetting('refreshIntervalSec'); setupAutoRefresh(); }} /></div>}
        >
          <NumberBox
            value={settings.refreshIntervalSec} min={15} max={3600} step={5} suffix="seconds"
            onChange={(v) => updRefresh({ refreshIntervalSec: v || 15 })}
          />
        </Row>
        <Row
          label="Date range on open"
          help="The header range this browser starts on."
          footer={<div className="mt-1.5"><Override shown={'defaultDateRange' in pinned} onReset={() => resetSetting('defaultDateRange')} /></div>}
        >
          <SelectBox
            value={settings.defaultDateRange} options={ranges} labels={RANGE_LABELS}
            onChange={(v) => { saveSettings({ defaultDateRange: v }); setDateRange(v); }}
          />
        </Row>
        <Row label="Open Frappe records in a new tab">
          <Toggle on={settings.openInNewTab} onClick={() => saveSettings({ openInNewTab: !settings.openInNewTab })} />
        </Row>
      </Panel>

      <Panel
        title="Organisation defaults"
        sub="Applied to every CRM user who has not pinned their own preference"
      >
        <Row label="Date range on open" help="What a new user's dashboard opens on.">
          <SelectBox
            value={form.draft.default_date_range} options={ranges}
            labels={RANGE_LABELS} disabled={form.disabled}
            onChange={(v) => form.set({ default_date_range: v })}
          />
        </Row>
        <Row label="Auto-refresh by default">
          <Toggle
            on={!!form.draft.auto_refresh} disabled={form.disabled}
            onClick={() => form.set({ auto_refresh: form.draft.auto_refresh ? 0 : 1 })}
          />
        </Row>
        <Row label="Default refresh interval">
          <NumberBox
            value={form.draft.refresh_interval_sec} min={15} max={3600} step={5} suffix="seconds"
            disabled={form.disabled}
            onChange={(v) => form.set({ refresh_interval_sec: v })}
          />
        </Row>
        <SaveBar form={form} />
      </Panel>

      <Panel title="Account" sub="Who this session belongs to">
        <Row label="Signed in as">
          <span className="font-mono text-[11.5px] text-ink-2">{boot.user || '—'}</span>
        </Row>
        <Row label="Company">
          <span className="text-[12.5px] text-ink-2">{boot.brandName}</span>
        </Row>
        <Row label="Reporting currency" help="Every money figure in the CRM is the company's default currency.">
          <span className="text-[12.5px] text-ink-2">{meta.currency}</span>
        </Row>
        <Row label="Can change organisation settings">
          <span className={`bdg ${meta.can_edit ? 'bdg-good' : 'bdg-other'}`}>{meta.can_edit ? 'Yes' : 'No'}</span>
        </Row>
      </Panel>
    </div>
  );
}
