import { useEffect, useState } from 'react';
import { useStore } from '../../store';
import { waTemplatesApi } from '../../api';
import { Panel, Row, SaveBar, useOrgForm, SELECT } from './parts';

// What a personal catalogue link is sent with: the email wording, and the
// approved WhatsApp template used outside Meta's 24-hour window.
const KEYS = ['catalogue_email_subject', 'catalogue_email_body', 'catalogue_whatsapp_template'];
const INPUT = 'w-[380px] rounded-md border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring';

export default function CatalogueSettings() {
  const form = useOrgForm(KEYS);
  const waOn = useStore((s) => s.moduleOn('wa'));
  const [templates, setTemplates] = useState([]);
  useEffect(() => {
    if (!waOn) return;
    waTemplatesApi().then((t) => setTemplates(t || [])).catch(() => setTemplates([]));
  }, [waOn]);
  const f = form.draft;
  return (
    <Panel title="Sending catalogues" sub="{name}, {link} and {catalogue} are filled in for each buyer">
      <Row label="Email subject">
        <input className={INPUT} disabled={form.disabled} value={f.catalogue_email_subject || ''}
          onChange={(e) => form.set({ catalogue_email_subject: e.target.value })} />
      </Row>
      <Row label="Message" help="Used for email, and for WhatsApp inside the 24-hour window.">
        <textarea className={`${INPUT} h-32`} disabled={form.disabled} value={f.catalogue_email_body || ''}
          onChange={(e) => form.set({ catalogue_email_body: e.target.value })} />
      </Row>
      <Row label="WhatsApp template"
        help="An APPROVED template whose first body variable is the link. Used when the buyer hasn't messaged in 24 hours.">
        <select className={`${SELECT} w-[280px]`} disabled={form.disabled || !waOn}
          value={f.catalogue_whatsapp_template || ''} onChange={(e) => form.set({ catalogue_whatsapp_template: e.target.value })}>
          <option value="">— none —</option>
          {templates.map((t) => <option key={t.name} value={t.name}>{t.actual_name}{t.language_code ? ` · ${t.language_code}` : ''}</option>)}
        </select>
      </Row>
      <SaveBar form={form} />
    </Panel>
  );
}
