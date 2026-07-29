import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import Icon from './Icon';
import { useStore } from '../store';
import { waTemplatesApi } from '../api';

// Composer for a WhatsApp thread.
//
// Meta only delivers free-form text within 24 hours of the contact's last inbound
// message. Outside that window this switches to template-only and says why —
// letting the user type into a dead box would just add to the 82 failed sends
// already on this site.
export default function WaComposer({ party, windowOpen, link, lastInboundAt }) {
  const sendWhatsapp = useStore((s) => s.sendWhatsapp);
  const sendWhatsappTemplate = useStore((s) => s.sendWhatsappTemplate);
  const defaultTemplate = useStore((s) => s.org?.default_whatsapp_template);

  const [text, setText] = useState('');
  const [templates, setTemplates] = useState([]);
  const [template, setTemplate] = useState('');
  const [mode, setMode] = useState(windowOpen ? 'text' : 'template');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [ok, setOk] = useState('');

  useEffect(() => {
    setMode(windowOpen ? 'text' : 'template');
    setErr(''); setOk('');
  }, [windowOpen, party]);

  useEffect(() => {
    let dead = false;
    waTemplatesApi()
      .then((t) => {
        if (dead) return;
        const rows = t || [];
        setTemplates(rows);
        // Preselect the configured default, but only if it is still approved —
        // a stale name in settings must not silently arm an undeliverable send.
        if (defaultTemplate && rows.some((r) => r.name === defaultTemplate)) {
          setTemplate((cur) => cur || defaultTemplate);
        }
      })
      .catch(() => { if (!dead) setTemplates([]); });
    return () => { dead = true; };
  }, [defaultTemplate]);

  const ref = {
    reference_doctype: link?.doctype || undefined,
    reference_name: link?.name || undefined,
  };

  async function send() {
    setBusy(true); setErr(''); setOk('');
    try {
      if (mode === 'template') {
        if (!template) { setErr('Pick a template.'); setBusy(false); return; }
        await sendWhatsappTemplate({ to: party, template, ...ref });
        setOk('Template sent');
        setTemplate('');
      } else {
        if (!text.trim()) { setErr('Type a message.'); setBusy(false); return; }
        await sendWhatsapp({ to: party, message: text, ...ref });
        // Only clear on success — a failed send must not lose what was typed.
        setText('');
        setOk('Sent');
      }
    } catch (e) {
      setErr(e.message || 'Could not send the message.');
    } finally {
      setBusy(false);
    }
  }

  const picked = templates.find((t) => t.name === template);

  return (
    <div className="border-t border-hairline px-4 py-3">
      <div className="flex items-center gap-2 mb-2.5">
        <button
          onClick={() => windowOpen && setMode('text')}
          disabled={!windowOpen}
          title={windowOpen ? 'Send free text' : 'Free text is not deliverable outside the 24-hour window'}
          className={`text-[12px] px-3 py-1.5 rounded-full font-medium transition-colors ${
            mode === 'text' ? 'bg-grad-ink text-white' : 'text-ink-4 hover:text-ink'
          } ${!windowOpen ? 'opacity-40 cursor-not-allowed' : ''}`}
        >
          Message
        </button>
        <button
          onClick={() => setMode('template')}
          className={`text-[12px] px-3 py-1.5 rounded-full font-medium transition-colors ${
            mode === 'template' ? 'bg-grad-ink text-white' : 'text-ink-4 hover:text-ink'
          }`}
        >
          Template
        </button>
        {!windowOpen && (
          <span className="text-[11.5px] text-warn flex items-center gap-1.5">
            <Icon name="schedule" className="text-[14px]" />
            {lastInboundAt
              ? 'No reply in 24h — WhatsApp only delivers approved templates now'
              : 'This contact has never messaged in — templates only'}
          </span>
        )}
      </div>

      {mode === 'template' ? (
        <div className="grid gap-2">
          <select
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">Select an approved template…</option>
            {templates.map((t) => (
              <option key={t.name} value={t.name}>
                {t.actual_name}{t.language_code ? ` · ${t.language_code}` : ''}
              </option>
            ))}
          </select>
          {picked && (
            <div className="rounded-xl bg-surface-2 border border-hairline px-3 py-2.5 text-[12.5px] text-ink-2">
              {picked.header && <div className="font-semibold text-ink mb-1">{picked.header}</div>}
              {picked.preview}
            </div>
          )}
          {!templates.length && (
            <div className="text-[12px] text-ink-mute">
              No APPROVED templates available. Create and submit one in desk first.
            </div>
          )}
        </div>
      ) : (
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Write a WhatsApp message…"
          className="min-h-[64px]"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); send(); }
          }}
        />
      )}

      <div className="flex items-center gap-3 mt-2.5">
        <Button size="sm" onClick={send} disabled={busy}
          className="rounded-full bg-gold text-ink hover:bg-gold-2 hover:text-white shadow-none px-5">
          <Icon name="send" className="text-[15px]" />
          {busy ? 'Sending…' : (mode === 'template' ? 'Send template' : 'Send')}
        </Button>
        {link && (
          <span className="text-[11px] text-ink-mute">
            Linked to {link.doctype} · {link.name}
          </span>
        )}
        {err && <span className="ml-auto text-[12px] text-bad text-right max-w-[60%]">{err}</span>}
        {!err && ok && <span className="ml-auto text-[12px] text-good">{ok}</span>}
      </div>
    </div>
  );
}
