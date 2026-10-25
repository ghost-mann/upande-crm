import { useEffect, useState } from 'react';
import { fmt, fmtDateTime } from '@shared/utils';
import DialogShell, { LABEL, SELECT } from '../../components/DialogShell';
import { openFrappe } from '@/lib/crm';
import {
  interestGetApi, interestStatusApi, makeOpportunityApi, INTEREST_TONE,
} from '@/lib/catalogues';

// One submission: who sent it, what they ticked, and the step to an Opportunity.
export default function InterestDetail({ name, onClose, onChanged }) {
  const [doc, setDoc] = useState(null);
  const [err, setErr] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    interestGetApi(name).then((d) => setDoc(d.interest)).catch((e) => setErr(e.message || 'Could not load'));
  }, [name]);

  async function setStatus(status) {
    setErr('');
    try {
      await interestStatusApi(name, status);
      setDoc((d) => ({ ...d, status }));
      onChanged?.();
    } catch (e) { setErr(e.message); }
  }

  async function makeOpp() {
    if (doc.opportunity) { openFrappe('Opportunity', doc.opportunity); return; }
    setSaving(true); setErr('');
    try {
      const { opportunity } = await makeOpportunityApi(name);
      setDoc((d) => ({ ...d, opportunity, status: 'Converted' }));
      onChanged?.();
    } catch (e) { setErr(e.message); } finally { setSaving(false); }
  }

  const money = (v) => (v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 4 }));
  return (
    <DialogShell title={doc ? `${doc.contact_name || doc.email} · ${doc.catalogue_title}` : 'Interest'}
      onClose={onClose} onSave={makeOpp} saving={saving} err={err} width={760}
      saveLabel={doc?.opportunity ? `Open ${doc.opportunity}` : 'Make opportunity'}>
      {!doc ? <div className="crm-empty">{err || 'Loading…'}</div> : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-[13px]">
            <div><span className={LABEL}>From</span>{doc.contact_name || '—'}<div className="text-ink-mute">{doc.company_name}</div></div>
            <div><span className={LABEL}>Contact</span>{doc.email || '—'}<div className="text-ink-mute">{doc.phone}</div></div>
            <div><span className={LABEL}>Country</span>{doc.country || '—'}</div>
            <div><span className={LABEL}>Filed under</span>
              {doc.party ? (
                <button type="button" className="text-gold-text hover:underline" onClick={() => openFrappe(doc.party_type, doc.party)}>
                  {doc.party_type} · {doc.party_name || doc.party}
                </button>) : '—'}
            </div>
            <div><span className={LABEL}>Received</span>{fmtDateTime(doc.creation)}{doc.via_link ? <div className="text-ink-mute">from a personal link</div> : <div className="text-ink-mute">from the public link</div>}</div>
            <div><span className={LABEL}>Status</span>
              <select className={`${SELECT} ${INTEREST_TONE[doc.status] ? '' : ''}`} value={doc.status} onChange={(e) => setStatus(e.target.value)}>
                {Object.keys(INTEREST_TONE).map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
          </div>
          {doc.message && <div className="rounded-xl bg-surface-2 border border-hairline px-3.5 py-3 text-[13px] whitespace-pre-wrap">{doc.message}</div>}
          <div className="tbl-wrap">
            <table className="tbl">
              <thead><tr><th>Item</th><th>Grade</th><th>Box</th><th className="cell-num">Boxes</th><th>How often</th><th className="cell-num">Price ({doc.currency})</th><th className="cell-num">Tier</th></tr></thead>
              <tbody>
                {doc.items.map((i, n) => (
                  <tr key={n}>
                    <td>{i.item_name || i.item}</td><td>{i.grade || '—'}</td><td>{i.box_type || '—'}</td>
                    <td className="cell-num">{fmt(i.qty)}</td>
                    <td>{i.frequency === 'Weekly' ? <span className="bdg bdg-info">Weekly</span> : 'One-off'}</td>
                    <td className="cell-num">{i.priced ? money(i.price) : '—'}</td>
                    <td className="cell-num">{i.priced && i.tier_price ? money(i.tier_price) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="text-[12px] text-ink-mute">
            Make opportunity copies these lines in units (boxes × pack). Weekly lines go across as one week's quantity, marked Weekly — adjust them on the opportunity.
          </div>
        </>
      )}
    </DialogShell>
  );
}
