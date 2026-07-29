import { useEffect, useState } from 'react';
import { fmt } from '@shared/utils';
import { useStore } from '../../store';
import { waTemplatesApi } from '../../api';
import Icon from '../../components/Icon';
import { Panel, Row, Toggle, NumberBox, SaveBar, useOrgForm, SELECT } from './parts';

const KEYS = ['whatsapp_enabled', 'default_whatsapp_template', 'whatsapp_fail_rate_alert'];

export default function WhatsAppSettings() {
  const form = useOrgForm(KEYS);
  const wa = useStore((s) => s.data.wa);
  const [templates, setTemplates] = useState(null);

  useEffect(() => {
    let dead = false;
    waTemplatesApi()
      .then((t) => { if (!dead) setTemplates(t || []); })
      .catch(() => { if (!dead) setTemplates([]); });
    return () => { dead = true; };
  }, []);

  const enabled = !!form.draft.whatsapp_enabled;
  const failRate = wa?.kpis?.fail_rate;
  const threshold = Number(form.draft.whatsapp_fail_rate_alert);
  const over = failRate != null && Number.isFinite(threshold) && failRate > threshold;
  const picked = (templates || []).find((t) => t.name === form.draft.default_whatsapp_template);

  return (
    <div>
      <Panel
        title="WhatsApp in the CRM"
        sub="A surface over frappe_whatsapp — credentials, webhooks and templates stay in desk"
      >
        <Row
          label="Show the WhatsApp section"
          help="Off removes it from the sidebar and stops the CRM querying WhatsApp on refresh."
        >
          <Toggle
            on={enabled} disabled={form.disabled}
            onClick={() => form.set({ whatsapp_enabled: enabled ? 0 : 1 })}
          />
        </Row>
        <Row
          label="Default template"
          help="Preselected in the composer — useful outside Meta's 24-hour reply window, where only approved templates deliver."
        >
          <select
            className={`${SELECT} w-[280px]`}
            disabled={form.disabled || !enabled}
            value={form.draft.default_whatsapp_template || ''}
            onChange={(e) => form.set({ default_whatsapp_template: e.target.value })}
          >
            <option value="">— none —</option>
            {(templates || []).map((t) => (
              <option key={t.name} value={t.name}>
                {t.actual_name}{t.language_code ? ` · ${t.language_code}` : ''}
              </option>
            ))}
          </select>
        </Row>
        {picked && (
          <div className="mt-3 rounded-xl bg-surface-2 border border-hairline px-3.5 py-3 text-[12.5px] text-ink-2">
            {picked.header && <div className="font-semibold text-ink mb-1">{picked.header}</div>}
            {picked.preview}
          </div>
        )}
        {templates && !templates.length && (
          <div className="mt-3 text-[12px] text-ink-mute">
            No APPROVED templates on this site — create and submit one in desk first.
          </div>
        )}
        <Row
          label="Failure rate alert"
          help="Above this, the Integrations tab flags WhatsApp as a warning."
        >
          <NumberBox
            value={form.draft.whatsapp_fail_rate_alert} min={0} max={100} suffix="%"
            disabled={form.disabled || !enabled}
            onChange={(v) => form.set({ whatsapp_fail_rate_alert: v })}
          />
        </Row>
        <SaveBar form={form} />
      </Panel>

      <Panel title="Delivery in the selected range" sub="From the WhatsApp dashboard's own figures">
        {wa?.kpis ? (
          <>
            <Row label="Sent"><span className="text-[13px] tabular-nums text-ink">{fmt(wa.kpis.sent)}</span></Row>
            <Row label="Received"><span className="text-[13px] tabular-nums text-ink">{fmt(wa.kpis.received)}</span></Row>
            <Row label="Failed">
              <span className={`text-[13px] tabular-nums ${wa.kpis.failed ? 'text-bad' : 'text-ink'}`}>
                {fmt(wa.kpis.failed)}
              </span>
            </Row>
            <Row label="Failure rate">
              <span className={`bdg ${over ? 'bdg-bad' : 'bdg-good'}`}>{wa.kpis.fail_rate}%</span>
            </Row>
            {over && (
              <div className="mt-3 flex items-start gap-2 text-[12px] text-bad">
                <Icon name="error" className="text-[15px] mt-px" />
                <span>
                  Above the {threshold}% alert threshold. Free text outside Meta's 24-hour window is
                  the usual cause — send an approved template instead.
                </span>
              </div>
            )}
          </>
        ) : (
          <div className="crm-empty">
            {enabled ? 'No WhatsApp data' : 'WhatsApp is switched off, so nothing is being read'}
          </div>
        )}
      </Panel>
    </div>
  );
}
