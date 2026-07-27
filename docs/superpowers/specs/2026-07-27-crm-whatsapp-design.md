# CRM WhatsApp Integration — Design

**Date:** 2026-07-27
**Status:** Approved design
**Scope:** Spec 3 of 3. Siblings: Events & Tasks (spec 1, delivered), Sales analytics (spec 2, delivered).

## Problem

`frappe_whatsapp` v1.0.12 is installed, configured, and carrying real two-way traffic — an
active default in/out WhatsApp Account (`james@upande.com`, phone_id set, webhook token),
386 messages, 97 profiles, 14 templates. But none of it is reachable from the CRM. A sales
user must leave for the desk to see or send a WhatsApp message, and nothing connects a
conversation to the Lead or Customer it concerns.

This is therefore a **surface** on an existing integration, not a Meta integration from
scratch. We do not touch webhooks, tokens, or the Cloud API — `frappe_whatsapp` owns those.

## Goals

A WhatsApp section mirroring the existing Mail section: conversation list keyed by contact,
thread view, send free text and approved templates, automatic phone→CRM matching, unread
counts, and a small analytics dashboard.

### Non-goals

Media/attachment sending (text and templates only), WhatsApp Flows, interactive button
messages, bulk campaigns, editing templates (that stays in desk), and realtime push (the
section refreshes on demand and on the existing auto-refresh interval).

## Hard constraints discovered on this site

### 1. `WhatsApp Message` is System-Manager-only

Its only DocPerm is System Manager (read/write/create/delete). Enforcing document
permissions would make the feature useless for every Sales User and Sales Manager — the
people it is for.

**Decision:** role-gate at the endpoint via `_guard()` (CRM roles), then perform the
WhatsApp Message read/write with `ignore_permissions=True`. This follows the precedent
already set by `crm_send_email` in `api/crm.py`, which does exactly this for `Communication`
with the same reasoning. Every write still validates its CRM reference against an allowlist,
so a caller cannot attach a message to an arbitrary doctype.

This is a deliberate, documented widening: a CRM-role user can send WhatsApp messages
through this endpoint that they could not send in desk. That is the point of the feature.
It is recorded here so it is a decision rather than an accident.

### 2. Phone numbers are not stored consistently

`WhatsApp Profiles` contains both `34607522650` and `254-727273549`. `frappe_whatsapp`'s own
`format_number` only strips a leading `+`, so it cannot be relied on for matching.

**Decision:** a local `_norm(number)` reduces to digits only, and matching compares the
**last 9 digits**. Nine is chosen because it is the significant subscriber length for Kenyan
numbers (`254 7XX XXX XXX` → `7XX XXX XXX` is 9) and it makes matching robust to country-code
presence, leading zeros, and punctuation without being so short that unrelated numbers
collide.

### 3. Unread has no dedicated field

Incoming messages carry `status` of either `"marked as read"` (192) or `NULL` (3). There is
no `seen` column as `Communication` has.

**Decision:** unread ≙ `type='Incoming' AND (status IS NULL OR status <> 'marked as read')`.
`crm_whatsapp_mark_read(party)` sets `"marked as read"` on that party's inbound messages,
matching what the desk chat UI does.

### 4. Meta's 24-hour customer service window

Free-form text may only be sent within 24 hours of the contact's last inbound message;
outside it, only approved templates are deliverable. 82 of 191 outgoing messages on this
site are already `failed`, so this is a live problem, not a theoretical one.

**Decision:** the API returns `window_open` and `last_inbound_at` per conversation. When the
window is closed the composer disables free text, says why, and offers the template picker
instead. Failing loudly in the UI beats letting Meta reject the message silently.

## Backend — `upande_crm/api/whatsapp.py`

Mixed read/write module. Reads degrade to empty; **sends throw** — a send that appears to
succeed but did not is the worst outcome here.

| Endpoint | Returns |
|---|---|
| `crm_whatsapp_conversations(search="", limit=60)` | `{"rows": [...], "unread_total": int}` — one row per counterparty with `party`, `display_name`, `last_message`, `last_at`, `last_direction`, `last_status`, `total`, `unread`, `window_open`, `link` |
| `crm_whatsapp_thread(party, limit=200)` | `{"party", "display_name", "window_open", "last_inbound_at", "link", "messages": [...]}` |
| `crm_whatsapp_send(to, message, reference_doctype=None, reference_name=None, reply_to=None)` | `{"name", "status"}` |
| `crm_whatsapp_send_template(to, template, reference_doctype=None, reference_name=None)` | `{"name", "status"}` |
| `crm_whatsapp_templates()` | `[{"name", "actual_name", "language_code", "preview"}]` — APPROVED only |
| `crm_whatsapp_mark_read(party)` | `{"party", "updated": int}` |
| `crm_whatsapp_analytics(date_from, date_to)` | KPIs + direction/status mix + daily trend + top conversations |

Sending creates a `WhatsApp Message` with `type="Outgoing"`, `content_type="text"`,
`message_type="Manual"`. `frappe_whatsapp`'s `before_insert` hook performs the actual Meta
dispatch, so a `.insert()` **is** the send. Template sends set `template` and let the
controller route to its template path. We never call the Graph API directly.

Reference linkage reuses the same allowlist idea as spec 1: `WA_REF_DOCTYPES =
{Lead, Opportunity, Prospect, Customer, Quotation, Contact, Sales Order}`.

### Phone → CRM matching

`_match_party(number)` resolves a phone to at most one CRM record, cheapest first:

1. `Lead.whatsapp_no` — a dedicated WhatsApp field exists on Lead on this site.
2. `Lead.mobile_no` / `Lead.phone`
3. `Contact Phone.phone` → parent `Contact` → `Dynamic Link` → `Customer`
4. `Contact.mobile_no` / `Contact.phone`
5. `Customer.mobile_no`

Returns `{"doctype", "name", "label"}` or `None`. Matching is done in one pass over
candidate rows keyed by normalized suffix rather than a query per conversation, so a
60-conversation list costs a bounded number of queries, not 300.

## Frontend

```
sections/WhatsApp/index.jsx        routes on `table`
  Conversations.jsx                list + search + unread badges
  Thread.jsx                       message bubbles + composer
  Dashboard.jsx                    KPIs and charts
components/WaComposer.jsx          free text vs template, 24h-window aware
```

Bubbles: outgoing right-aligned in the gold/ink tone, incoming left in surface tone, with
per-message status (`sent`/`delivered`/`read`/`failed`). **Failed messages get an explicit
red marker** — with 82 failures already on this site, silent failure is the main hazard.

The conversation list shows the matched CRM record as a chip; clicking it opens the desk
record. The thread header carries the same chip plus a "Log as activity" affordance that
opens spec 1's `TaskDialog` prefilled with the matched reference — this is where the three
specs join up.

`LinkSearch` from spec 1 is reused to attach a conversation to a CRM record when matching
finds nothing.

Nav gains a WhatsApp group under Mail with an unread count, mirroring the Inbox pattern.
No new npm dependency (the `vite.config.js` vendor-chunk hazard still applies).

## Error handling

- `crm_whatsapp_send` validates a non-empty recipient and message, checks the 24-hour window
  and refuses free text when closed (with a message naming the template alternative), and
  lets a Meta failure propagate as a thrown error rather than a silent "sent".
- The composer surfaces the thrown message inline and does not clear the input on failure,
  so the user does not lose what they typed.
- Reads degrade: no `frappe_whatsapp` installed → empty section with an explanatory empty
  state rather than a crash.

## Testing

`upande_crm/tests/test_whatsapp.py`:

- `_norm` strips `+`, spaces, dashes; `254-727273549` and `+254727273549` normalize equal.
- Suffix matching links a Lead by `whatsapp_no` and does not link an unrelated number.
- `_match_party` returns `None` for an unknown number rather than raising.
- Conversation grouping keys outgoing by `to` and incoming by `from`.
- Unread counting treats `status IS NULL` incoming as unread and `"marked as read"` as read.
- `crm_whatsapp_mark_read` clears that party's unread count.
- `window_open` is True within 24h of the last inbound and False beyond it.
- `crm_whatsapp_send` rejects an empty recipient, an empty message, and an off-allowlist
  reference doctype.
- `crm_whatsapp_send` refuses free text when the window is closed.
- `crm_whatsapp_templates` returns only APPROVED templates.
- `_guard` rejects a user without a CRM role.

Send tests must not hit Meta. They assert the validation branches that reject *before*
insert, and monkeypatch the insert path where a successful send would otherwise dispatch.

## Verification

`bench --site kaitet.local run-tests --app upande_crm`, `cd frontend && yarn build`, then the
WhatsApp section at `http://localhost:8002/customer-relationship-management` should list real
conversations with matched CRM chips and show the existing 82 failed sends as failed.
