import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { fmt, fmtDate, fmtDateTime, shortUser } from '@shared/utils';
import { useStore } from '../../store';
import Icon from '../../components/Icon';
import DataTable from '../../components/DataTable';
import { SELECT } from '../../components/DialogShell';
import CatalogueEditor from './CatalogueEditor';
import InterestDetail from './InterestDetail';
import {
  cataloguesApi, interestsApi, copyText, CATALOGUE_TONE, INTEREST_TONE,
} from '@/lib/catalogues';

// Catalogues: price lists shared with buyers by link, and the interest that
// comes back (docs/superpowers/specs/2026-10-25-crm-catalogues-design.md).
// `#cat` lists catalogues; `#cat/interests` lists submissions; the owner's
// notification email links to `#cat/interest:<name>`, which opens one.

export function interestColumns(withParty = true) {
  return [
    { key: 'name', label: 'Interest', cls: 'cell-id' },
    { key: 'creation', label: 'Received', cls: 'cell-id', render: (r) => fmtDateTime(r.creation) },
    { key: 'contact_name', label: 'From', render: (r) => (
      <span>{r.contact_name || r.email}{r.company_name ? <span className="text-ink-mute"> · {r.company_name}</span> : null}</span>
    ) },
    ...(withParty ? [{ key: 'party', label: 'Lead / customer', render: (r) => (
      r.party ? <span><span className="text-ink-mute">{r.party_type}</span> {r.party_name || r.party}</span> : '—'
    ) }] : []),
    { key: 'catalogue_title', label: 'Catalogue' },
    { key: 'boxes', label: 'Boxes', cls: 'cell-num', render: (r) => (
      <span>{fmt(r.boxes)}{r.weekly ? <span className="bdg bdg-info ml-1.5">weekly</span> : null}</span>
    ) },
    { key: 'status', label: 'Status', render: (r) => <span className={`bdg ${INTEREST_TONE[r.status] || 'bdg-other'}`}>{r.status}</span> },
  ];
}

function CatalogueList({ onOpen }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const [copied, setCopied] = useState('');

  useEffect(() => {
    cataloguesApi().then(setData).catch((e) => setErr(e.message || 'Could not load catalogues'));
  }, []);

  if (err) return <div className="crm-empty">{err}</div>;
  if (!data) return <div className="p-12 text-center text-ink-mute text-[13px]">Loading…</div>;
  if (!data.available) return <div className="crm-empty">Catalogues are not available — run bench migrate, or ask for access to CRM Catalogue.</div>;

  const columns = [
    { key: 'title', label: 'Catalogue', render: (r) => <span className="font-medium text-ink">{r.title}</span> },
    { key: 'status', label: 'Status', render: (r) => <span className={`bdg ${CATALOGUE_TONE[r.status]}`}>{r.status}</span> },
    { key: 'valid_to', label: 'Valid', cls: 'cell-id', render: (r) => (
      r.valid_from || r.valid_to ? `${r.valid_from ? fmtDate(r.valid_from) : '…'} – ${r.valid_to ? fmtDate(r.valid_to) : '…'}` : '—') },
    { key: 'currencies', label: 'Currencies' },
    { key: 'lines', label: 'Lines', cls: 'cell-num', render: (r) => fmt(r.lines) },
    { key: 'views', label: 'Public views', cls: 'cell-num', render: (r) => fmt(r.views || 0) },
    { key: 'links', label: 'Links opened', cls: 'cell-num', render: (r) => (r.links ? `${fmt(r.opened)} / ${fmt(r.links)}` : '—') },
    { key: 'interests', label: 'Interests', cls: 'cell-num', render: (r) => fmt(r.interests) },
    { key: 'owner', label: 'Owner', render: (r) => shortUser(r.owner) },
    { key: 'copy', label: '', render: (r) => (r.status === 'Live' ? (
      <button type="button" title="Copy the public link" className="text-gold-text hover:underline text-[12px] inline-flex items-center gap-1"
        onClick={(e) => { e.stopPropagation(); copyText(r.public_url); setCopied(r.name); setTimeout(() => setCopied(''), 1800); }}>
        <Icon name="content_copy" className="text-[14px]" />{copied === r.name ? 'Copied' : 'Link'}
      </button>) : null) },
  ];

  return (
    <>
      <div className="flex items-center gap-2.5 mb-5 flex-wrap">
        <Button size="sm" onClick={() => onOpen('new')}
          className="rounded-full bg-gold text-[var(--on-accent)] hover:bg-gold-2 hover:text-white shadow-none px-4">
          <Icon name="add" className="text-[16px]" />New catalogue
        </Button>
        <span className="text-[12px] text-ink-mute">Build an offer from your items, put it live, and share it as a link. Whoever fills it in arrives here as an interest.</span>
      </div>
      <DataTable title="Catalogues" columns={columns} rows={data.rows} onRowClick={(r) => onOpen(r.name)}
        searchFields={['title', 'status', 'currencies', 'owner']}
        emptyText="No catalogues yet — make one from this season's offer sheet" />
    </>
  );
}

function Interests({ openName }) {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState('');
  const [status, setStatus] = useState('');
  const [detail, setDetail] = useState(openName || null);

  const load = useCallback(() => {
    setErr('');
    interestsApi(status ? { status } : {}).then((d) => setRows(d.rows)).catch((e) => setErr(e.message || 'Could not load interests'));
  }, [status]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (openName) setDetail(openName); }, [openName]);

  if (err) return <div className="crm-empty">{err}</div>;
  if (!rows) return <div className="p-12 text-center text-ink-mute text-[13px]">Loading…</div>;
  return (
    <>
      <div className="flex items-center gap-2.5 mb-4">
        <div className="w-[180px] shrink-0">
          <select className={SELECT} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {Object.keys(INTEREST_TONE).map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
        <span className="text-[12px] text-ink-mute">Each row is one submission from a catalogue link. New ones also reach the catalogue's owner by email.</span>
      </div>
      <DataTable title="Interests" columns={interestColumns()} rows={rows} onRowClick={(r) => setDetail(r.name)}
        searchFields={['name', 'contact_name', 'company_name', 'email', 'party', 'catalogue_title']}
        emptyText="No interest yet — share a live catalogue to collect some" />
      {detail && <InterestDetail name={detail} onClose={() => setDetail(null)} onChanged={load} />}
    </>
  );
}

export default function Catalogues() {
  const table = useStore((s) => s.table);
  const select = useStore((s) => s.select);
  // The open catalogue rides in the hash (`#cat/edit:<name>`, `#cat/new`), so the
  // sidebar, Back and a pasted link all land where they should.
  const open = (name) => select('cat', name === 'new' ? 'new' : `edit:${name}`);

  if (table === 'interests' || table.startsWith('interest:')) {
    return <Interests openName={table.startsWith('interest:') ? table.slice(9) : null} />;
  }
  if (table === 'new' || table.startsWith('edit:')) {
    const name = table === 'new' ? null : table.slice(5);
    return <CatalogueEditor key={table} name={name} onBack={() => select('cat', '')} onOpen={open} />;
  }
  return <CatalogueList onOpen={open} />;
}
