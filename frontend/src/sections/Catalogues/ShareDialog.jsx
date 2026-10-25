import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { fmtDateTime, shortUser } from '@shared/utils';
import Icon from '../../components/Icon';
import LinkSearch from '../../components/LinkSearch';
import DialogShell, { LABEL, SELECT } from '../../components/DialogShell';
import { useStore } from '../../store';
import { shareOptionsApi, shareApi, catalogueLinksApi, copyText } from '@/lib/catalogues';

// Send one buyer their own link — by email, WhatsApp, or copied — so the CRM
// knows who opened it. The channel is chosen per send; a channel that cannot
// reach this buyer says why instead of failing after the click.
const INPUT = 'w-full rounded-md border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring';

export default function ShareDialog({ catalogue, onClose }) {
  const [partyType, setPartyType] = useState('Lead');
  const [party, setParty] = useState('');
  const [opts, setOpts] = useState(null);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState('');
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [links, setLinks] = useState([]);

  const loadLinks = useCallback(() => {
    catalogueLinksApi(catalogue.name).then((d) => setLinks(d.rows)).catch(() => setLinks([]));
  }, [catalogue.name]);
  useEffect(() => { loadLinks(); }, [loadLinks]);

  const org = useStore((s) => s.org);
  useEffect(() => {
    setSubject(org?.catalogue_email_subject || '{catalogue}: our current offer');
    setBody(org?.catalogue_email_body || 'Hello {name},\n\nOur current offer is here: {link}');
  }, [org]);

  useEffect(() => {
    setOpts(null); setErr(''); setMsg('');
    if (!party) return;
    shareOptionsApi(catalogue.name, partyType, party).then(setOpts).catch((e) => setErr(e.message));
  }, [catalogue.name, partyType, party]);

  async function send(channel) {
    setBusy(channel); setErr(''); setMsg('');
    try {
      const out = await shareApi({ name: catalogue.name, party_type: partyType, party, channel, subject, body });
      if (channel === 'Copied') { await copyText(out.url); setMsg('Personal link copied — paste it anywhere. Opens are tracked.'); }
      else setMsg(channel === 'Email' ? `Emailed to ${opts.email}.` : `Sent on WhatsApp to ${opts.phone}.`);
      loadLinks();
    } catch (e) { setErr(e.message); } finally { setBusy(''); }
  }

  const ch = opts?.channels || {};
  const why = opts?.reason || {};
  const pill = 'rounded-full shadow-none px-4';
  return (
    <DialogShell title={`Send “${catalogue.title}”`} onClose={onClose} onSave={onClose} saveLabel="Done" err={err} width={720}>
      <div className="grid grid-cols-[140px_1fr] gap-3 items-end">
        <label><span className={LABEL}>Send to</span>
          <select className={SELECT} value={partyType} onChange={(e) => { setPartyType(e.target.value); setParty(''); }}>
            <option>Lead</option><option>Customer</option>
          </select>
        </label>
        <label><span className={LABEL}>{partyType}</span>
          <LinkSearch doctype={partyType} value={party} onChange={(v) => setParty(v || '')} placeholder={`Find a ${partyType.toLowerCase()}…`} />
        </label>
      </div>

      {opts && (
        <>
          <div className="text-[12.5px] text-ink-mute">
            {opts.email || 'no email'} · {opts.phone || 'no phone'}
          </div>
          <div className="grid gap-2">
            <label><span className={LABEL}>Subject (email)</span>
              <input className={INPUT} value={subject} onChange={(e) => setSubject(e.target.value)} /></label>
            <label><span className={LABEL}>Message — {'{name}'}, {'{link}'} and {'{catalogue}'} are filled in</span>
              <textarea className={`${INPUT} h-28`} value={body} onChange={(e) => setBody(e.target.value)} /></label>
            {ch.whatsapp_mode === 'template' && (
              <div className="text-[12px] text-ink-mute">WhatsApp will use the approved catalogue template (they haven't messaged in 24 hours); the message above is used for email only.</div>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" className={`${pill} bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white`}
              disabled={!ch.email || !!busy} title={why.email || ''} onClick={() => send('Email')}>
              <Icon name="mail" className="text-[16px]" />{busy === 'Email' ? 'Sending…' : 'Email'}
            </Button>
            <Button size="sm" variant="outline" className={pill} disabled={!ch.whatsapp || !!busy} title={why.whatsapp || ''} onClick={() => send('WhatsApp')}>
              <Icon name="chat" className="text-[16px]" />{busy === 'WhatsApp' ? 'Sending…' : 'WhatsApp'}
            </Button>
            <Button size="sm" variant="outline" className={pill} disabled={!!busy} onClick={() => send('Copied')}>
              <Icon name="content_copy" className="text-[16px]" />Copy link
            </Button>
          </div>
          {(why.email || why.whatsapp) && (
            <ul className="text-[12px] text-ink-mute list-disc pl-5">
              {why.email && <li>Email: {why.email}</li>}
              {why.whatsapp && <li>WhatsApp: {why.whatsapp}</li>}
            </ul>
          )}
        </>
      )}
      {msg && <div className="text-[12.5px] text-good">{msg}</div>}

      <div>
        <span className={LABEL}>Sent so far</span>
        {links.length ? (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead><tr><th>To</th><th>Via</th><th>Sent</th><th>By</th><th className="cell-num">Opens</th><th>Last opened</th></tr></thead>
              <tbody>
                {links.map((l) => (
                  <tr key={l.name}>
                    <td><span className="text-ink-mute">{l.party_type}</span> {l.party_name}</td>
                    <td>{l.sent_via}</td><td>{fmtDateTime(l.sent_on)}</td><td>{shortUser(l.sent_by)}</td>
                    <td className="cell-num">{l.open_count || 0}</td>
                    <td>{l.last_opened_on ? fmtDateTime(l.last_opened_on) : <span className="text-ink-mute">not yet</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="text-[12.5px] text-ink-mute">No personal links yet.</div>}
      </div>
    </DialogShell>
  );
}
