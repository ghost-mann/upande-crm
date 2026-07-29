# CRM Campaigns — Design

**Date:** 2026-07-29
**Status:** Built. Scope confirmed in conversation; research done before designing.
**Scope:** Spec 9.

## What was asked

"A place for campaigns" — and, explicitly, *"I don't know how that works, so do your
research"*. So this spec leads with the research, because the answer changed the design twice.

## Research: ERPNext has two unrelated things called "campaign"

### 1. `Campaign` + `Email Campaign` — a drip-email engine (CRM module)

**`Campaign`** is the *definition*: a title, a description, and a child table
`Campaign Email Schedule` of `(email_template, send_after_days)` rows. A campaign **is** a drip
sequence — "send Weekly Promo 7 days in".

Already in use on this site: **32 campaigns, 27 with a schedule**, created by real staff
(*Seasons greetings*, *Flowers Expo Moscow*, *Endebess taste of harvest*, *farm to cup*,
*WAITROSE PROMO*). 5 have no schedule and therefore cannot send at all.

**`Email Campaign`** is an *enrolment*: one Campaign pointed at one recipient — a **Lead**, a
**Contact** or an **Email Group** — with a sender and a start date. `end_date` is derived as
`start_date + max(send_after_days)`. 16 exist, all Completed.

**`Email Group`** holds the audiences: **30 groups, 10,307 members**, 47 unsubscribed. Largest
are *cu* (1,043), *testy* (1,034), *ENDEBESS COFFEE FEST* (940 active / 2 unsubscribed).

**Sending is the scheduler's job.** `daily_maintenance` runs
`erpnext...email_campaign.send_email_to_leads_or_contacts` and `set_email_campaign_status` once
a day. **Nothing sends on save.** The UI states this on the dashboard and in the enrol dialog,
because a user expecting an instant blast would otherwise think it had failed.

### 2. `UTM Campaign` — attribution (Website module), and it is dead

A **separate** doctype, 32 rows with overlapping names. `Lead.utm_campaign` links to it and is
populated on **0 of 112 leads**. So nothing connected a lead to the campaign that produced it —
campaigns could be sent but never evaluated.

Two details that shaped the implementation:

- `UTM Campaign.autoname` is `prompt`, so the row name *is* the title — matching the 32 rows
  already there.
- It carries a **`crm_campaign` Link field pointing back at `Campaign`**. That is ERPNext's own
  bridge between the two concepts, so attribution uses it rather than inventing a local
  convention.

### A stale column, deliberately untouched

`Lead.campaign_name` exists in the database but **not in the schema** — a leftover from
ERPNext renaming it to `utm_campaign`. It holds 3 values, one of which is "Cold Calling", a
*source* rather than a campaign. Stale and dirty; attribution ignores it.

## Decisions

**Attribution is written on enrolment** (confirmed with James). Enrolling a Lead sets its
`utm_campaign` and ensures the UTM row bridges back via `crm_campaign`. Without this no campaign
can be evaluated. It applies to Leads only — an Email Group has no such field — and can be
declined per enrolment.

**Drip enrolment only, no immediate blast** (confirmed). The engine that exists is used as-is.
This is also the safer choice: there is no button that instantly emails a 1,043-member list.

**Permissions.** `Email Campaign` is System-Manager-only and `UTM Campaign` is granted to
System/Newsletter/Marketing Manager — neither includes the Sales roles this CRM serves. So, as
with Communication, WhatsApp Message and Call Log, endpoints role-gate through `_guard()` then
write with `ignore_permissions=True`. `Campaign` itself is writable by Sales Manager, so that
gate is real rather than nominal. Editing a campaign is restricted to its owner or a manager:
campaigns are shared assets others have enrolled recipients into, so changing someone else's
schedule silently changes what those recipients receive next.

## Validations inherited from the core controller

Read from `erpnext/crm/doctype/email_campaign/email_campaign.py`: a past `start_date` throws;
the Campaign must have a schedule; a Lead recipient must have an `email_id`; and the same
campaign cannot be enrolled twice for one recipient while Scheduled or In Progress.

**Enrolment is bulk**, so one rejected recipient must not lose the batch. `crm_campaign_enrol`
returns a per-recipient result with the reason, keeps the ones that worked, and the dialog stays
open showing the failures. The recipient picker greys out leads with no email address up front,
which is better than a failed row afterwards.

One more thing the tests exposed: `Campaign` is named by its title here, so a repeated name is a
primary-key collision. It is now caught with "A campaign called X already exists" instead of a
raw `DuplicateEntryError` traceback.

## Surface

Backend `upande_crm/api/campaigns.py`: `crm_dashboard_campaigns`, `crm_campaign_detail`,
`crm_campaign_save`, `crm_campaign_enrol`, `crm_campaign_cancel`, `crm_campaign_recipients`,
`crm_email_templates`, `crm_email_groups`.

Frontend `sections/Campaigns/` with tabs Dashboard / Campaigns / Enrolments / My enrolments /
Audiences, plus `CampaignDialog` (name, description, drip schedule builder) and `EnrolDialog`
(campaign, target, multi-select recipients, start date, attribution toggle, per-recipient
results). Nav gains a **Marketing** group, icon `campaign`.

Campaigns with no schedule are flagged **NO SCHEDULE** in the list and disabled in the enrol
picker, because they are the one thing in this feature that silently cannot work.

## Testing

`tests/test_campaigns.py` (33 tests): schedule round-trip and sorting, wholesale replacement,
duplicate-name message, unknown/negative/duplicate-offset steps refused; enrolment creating one
Email Campaign per recipient with the derived `end_date`; a campaign without a schedule refused;
**one bad recipient not losing the batch**; a lead without an email failing with a reason; past
start date and off-list target refused; attribution writing `utm_campaign` and the
`crm_campaign` bridge, and being declinable; group enrolment tagging nothing; dashboard shape and
with/without-schedule accounting; recipient eligibility flags; owner-only editing; Guest refused
everywhere.

## Verification

Full suite green, and the section driven in a headless browser: dashboard reports 32 campaigns
with 5 unsendable, the list shows real sequences (*Valentines Season (d0)*, *Weekly Promo (d1)*),
enrolments and audiences render, and the schedule builder adds a step with real templates. No
console errors.
