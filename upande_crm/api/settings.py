"""Organisation-wide CRM settings, and a health panel for what the CRM depends on.

Two halves with opposite failure behaviour, matching the split the rest of this
app already uses:

* **Reads degrade.** `get_settings()` and `crm_integration_status()` never raise
  past the role gate. A site that has this app's Python but has not migrated the
  `Upande CRM Settings` doctype must still render a working dashboard, so
  `DEFAULTS` below is the authority for reads and the doctype only overrides it.
  `DEFAULTS` mirrors the doctype JSON's field defaults — keep them in step.
* **Writes throw.** A settings change that silently did not apply is worse than
  an error, because these values drive reported numbers.

Import direction: this module imports from `api/crm.py`. `crm.py` and
`analytics.py` therefore import `get_settings` *inside* the functions that need
it — a module-level import in both directions would be a cycle.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, nowdate

from upande_crm.api.activity import _load
from upande_crm.api.crm import _company_currency, _count, _guard, _has, _hascol

SETTINGS_DOCTYPE = "Upande CRM Settings"

# Who may change settings. Broader than the doctype's DocPerms on purpose:
# `CRM Manager` does not exist on every site (it does not exist on this one), so
# it cannot appear in the doctype JSON without breaking `migrate`, but it should
# still be honoured where a site defines it.
WRITE_ROLES = {"System Manager", "Sales Manager", "CRM Manager"}

# Read-side defaults. Mirrors upande_crm_settings.json; the value's Python type
# also defines how a stored value is coerced (see `_coerce`).
DEFAULTS = {
    "revenue_target_monthly": 0.0,
    "revenue_target_annual": 0.0,
    "target_basis": "Billed",
    "default_date_range": "30d",
    "top_n": 8,
    "auto_refresh": 1,
    "refresh_interval_sec": 60,
    "lead_open_statuses": "Lead, Open, Replied, Interested",
    "opportunity_open_statuses": "Open, Quotation, Replied",
    "default_task_priority": "Medium",
    "default_task_due_days": 3,
    "default_event_category": "Meeting",
    "default_event_duration_mins": 60,
    "whatsapp_enabled": 1,
    "default_whatsapp_template": "",
    "whatsapp_fail_rate_alert": 20.0,
}

# Select vocabularies, so the UI does not have to hardcode them and still works
# when the doctype is absent.
OPTIONS = {
    "target_basis": ["Billed", "Booked"],
    "default_date_range": ["7d", "30d", "90d", "ytd"],
    "default_task_priority": ["High", "Medium", "Low"],
    "default_event_category": ["Event", "Meeting", "Call", "Sent/Received Email", "Other"],
}

# How far back the WhatsApp failure-rate health check looks.
WA_HEALTH_DAYS = 30


# ---------------------------------------------------------------- reads
def _installed():
    try:
        return bool(frappe.db.exists("DocType", SETTINGS_DOCTYPE))
    except Exception:
        return False


def _coerce(value, default):
    try:
        if isinstance(default, bool):
            return bool(cint(value))
        if isinstance(default, int):
            return cint(value)
        if isinstance(default, float):
            return flt(value)
        return str(value)
    except Exception:
        return default


def get_settings():
    """Resolved settings, always complete. Never raises."""
    out = dict(DEFAULTS)
    if not _installed():
        return out
    try:
        doc = frappe.get_cached_doc(SETTINGS_DOCTYPE)
    except Exception:
        return out
    for key, default in DEFAULTS.items():
        value = doc.get(key)
        # An unsaved Single has no values at all; "" means "never filled in".
        if value is None or value == "":
            continue
        out[key] = _coerce(value, default)
    return out


def parse_list(text):
    """Comma-separated text -> trimmed, non-empty values.

    Only commas separate: statuses on this site are multi-word ("In Process").
    """
    return [p.strip() for p in str(text or "").split(",") if p.strip()]


def open_statuses(key, settings=None):
    """The configured open-status list for `key`, falling back to the default.

    Used by the dashboard readers in place of the literal lists they used to
    carry. A blank setting must not produce an empty `in ()` filter, which would
    count zero.
    """
    s = settings if settings is not None else get_settings()
    values = parse_list(s.get(key))
    return values or parse_list(DEFAULTS[key])


def top_n(settings=None):
    s = settings if settings is not None else get_settings()
    return max(1, cint(s.get("top_n")) or DEFAULTS["top_n"])


def _can_edit(user=None):
    return bool(set(frappe.get_roles(user or frappe.session.user)) & WRITE_ROLES)


@frappe.whitelist()
def crm_settings():
    _guard()
    return {
        "settings": get_settings(),
        "can_edit": _can_edit(),
        "installed": _installed(),
        "currency": _company_currency(),
        "options": OPTIONS,
    }


# ---------------------------------------------------------------- write
@frappe.whitelist()
def crm_settings_save(settings=None):
    """Persist a partial settings patch. Throws on anything unexpected."""
    _guard()
    if not _can_edit():
        frappe.throw(
            _("Only a Sales Manager or System Manager can change CRM settings."),
            frappe.PermissionError,
        )
    if not _installed():
        frappe.throw(
            _("Upande CRM Settings is not installed on this site — run `bench migrate` first.")
        )

    payload = _load(settings)
    if not isinstance(payload, dict):
        frappe.throw(_("Malformed settings payload"))

    # Unknown keys are dropped rather than written, so a crafted request cannot
    # set fields this endpoint does not own.
    values = {k: v for k, v in payload.items() if k in DEFAULTS}
    if not values:
        frappe.throw(_("No recognised settings in this request"))

    doc = frappe.get_single(SETTINGS_DOCTYPE)
    doc.update(values)
    # ignore_permissions: the role gate above is the authority here, because
    # WRITE_ROLES intentionally includes a role the DocPerms cannot name.
    # Validation still runs — it lives in the controller, not in the DocPerm.
    doc.save(ignore_permissions=True)
    return {"settings": get_settings()}


# ---------------------------------------------------------------- health
def _check(key, label, status, detail, hint=""):
    return {"key": key, "label": label, "status": status, "detail": detail, "hint": hint}


def _sales_check():
    so, si = _has("Sales Order"), _has("Sales Invoice")
    if not so and not si:
        return _check("sales", "Sales data", "missing",
                      "Neither Sales Order nor Sales Invoice exists on this site",
                      "Install ERPNext to populate revenue analytics")
    orders = _count("Sales Order", {"docstatus": 1}) if so else 0
    invoices = _count("Sales Invoice", {"docstatus": 1}) if si else 0
    if not orders and not invoices:
        return _check("sales", "Sales data", "warn", "No submitted orders or invoices found",
                      "Revenue cards will read zero until sales are submitted")
    return _check("sales", "Sales data", "ok",
                  f"{orders:,} submitted orders · {invoices:,} submitted invoices")


def _pipeline_check():
    wanted = ("Lead", "Opportunity", "Prospect", "Customer", "Quotation")
    missing = [d for d in wanted if not _has(d)]
    if len(missing) == len(wanted):
        return _check("pipeline", "Pipeline doctypes", "missing",
                      "No CRM doctypes are available on this site")
    if missing:
        return _check("pipeline", "Pipeline doctypes", "warn",
                      "Missing: " + ", ".join(missing),
                      "Those sections will render empty")
    counts = " · ".join(
        f"{_count(d):,} {label}" for d, label in
        (("Lead", "leads"), ("Opportunity", "opportunities"), ("Customer", "customers"))
    )
    return _check("pipeline", "Pipeline doctypes", "ok", counts)


def _email_checks():
    out = []
    if not _has("Email Account"):
        out.append(_check("email_out", "Outgoing email", "missing", "Email Account is unavailable"))
        return out
    try:
        default_out = frappe.get_all("Email Account", filters={"enable_outgoing": 1, "default_outgoing": 1},
                                     fields=["name", "email_id"], limit=1)
        any_out = _count("Email Account", {"enable_outgoing": 1})
        any_in = _count("Email Account", {"enable_incoming": 1})
    except Exception:
        out.append(_check("email_out", "Outgoing email", "warn", "Could not read Email Account"))
        return out

    if default_out:
        out.append(_check("email_out", "Outgoing email", "ok",
                          f"Default sender: {default_out[0].email_id or default_out[0].name}"))
    elif any_out:
        out.append(_check("email_out", "Outgoing email", "warn",
                          f"{any_out} outgoing account(s), none marked default",
                          "Compose may fail without a default outgoing account"))
    else:
        out.append(_check("email_out", "Outgoing email", "off", "No outgoing account is enabled",
                          "Sending from the CRM will fail"))

    out.append(
        _check("email_in", "Incoming email", "ok" if any_in else "off",
               f"{any_in} account(s) pulling mail" if any_in else "No incoming account is enabled",
               "" if any_in else "The Inbox will only show mail sent from Frappe")
    )
    return out


def _whatsapp_check(settings):
    """WhatsApp health.

    Reads `WhatsApp Account`, never `WhatsApp Settings`: the latter still has a
    DocType row on this site but its table was dropped when `frappe_whatsapp`
    moved to multi-account, so `_has()` reports it as present and any query
    against it raises.
    """
    if not _has("WhatsApp Message"):
        return _check("whatsapp", "WhatsApp", "missing", "frappe_whatsapp is not installed")

    if not cint(settings.get("whatsapp_enabled")):
        return _check("whatsapp", "WhatsApp", "off", "Hidden from the CRM by settings",
                      "Turn it on under Settings · WhatsApp")

    account = None
    try:
        rows = frappe.get_all("WhatsApp Account",
                              filters={"is_default_outgoing": 1},
                              fields=["name", "account_name", "status"], limit=1)
        account = rows[0] if rows else None
    except Exception:
        account = None

    approved = 0
    try:
        if _has("WhatsApp Templates"):
            approved = _count("WhatsApp Templates", {"status": "APPROVED"})
    except Exception:
        approved = 0

    sent = failed = 0
    try:
        row = frappe.db.sql(
            """select count(*), coalesce(sum(case when status='failed' then 1 else 0 end), 0)
               from `tabWhatsApp Message`
               where type='Outgoing' and creation >= %s""",
            (add_days(nowdate(), -WA_HEALTH_DAYS),),
        )[0]
        sent, failed = cint(row[0]), cint(row[1])
    except Exception:
        sent = failed = 0
    fail_rate = round(failed / sent * 100, 1) if sent else 0.0
    threshold = flt(settings.get("whatsapp_fail_rate_alert"))

    detail = (f"{approved} approved template(s) · {sent} sent in {WA_HEALTH_DAYS}d"
              f" · {fail_rate}% failed")
    if not account:
        return _check("whatsapp", "WhatsApp", "warn", "No default outgoing WhatsApp Account",
                      "Sends will fail until one is set in desk")
    if (account.get("status") or "") != "Active":
        return _check("whatsapp", "WhatsApp", "warn",
                      f"Account {account.get('account_name') or account.get('name')} is "
                      f"{account.get('status') or 'not active'}",
                      "Sends will fail while the account is inactive")
    if not approved:
        return _check("whatsapp", "WhatsApp", "warn", detail,
                      "Without an approved template you can only reply inside the 24-hour window")
    if sent and fail_rate > threshold:
        return _check("whatsapp", "WhatsApp", "warn", detail,
                      f"Failure rate is above the {threshold:g}% alert threshold")
    return _check("whatsapp", "WhatsApp", "ok", detail)


def _activity_check():
    if not _has("Event") or not _has("ToDo"):
        return _check("activity", "Events & Tasks", "missing", "Event or ToDo is unavailable")
    events = _count("Event")
    open_tasks = _count("ToDo", {"status": "Open"})
    google = ""
    try:
        if _has("Google Calendar") and _hascol("Google Calendar", "enable"):
            n = _count("Google Calendar", {"enable": 1})
            google = f" · {n} Google calendar(s) connected" if n else ""
    except Exception:
        google = ""
    return _check("activity", "Events & Tasks", "ok",
                  f"{events:,} events · {open_tasks:,} open tasks{google}")


def _storage_check():
    if not _installed():
        return _check("storage", "Settings storage", "warn",
                      f"{SETTINGS_DOCTYPE} is not installed — built-in defaults are in use",
                      "Run `bench migrate` to make settings saveable")
    saved = False
    try:
        saved = bool(frappe.db.exists("Singles", {"doctype": SETTINGS_DOCTYPE}))
    except Exception:
        saved = False
    return _check("storage", "Settings storage", "ok",
                  "Saved on this site" if saved else "Installed · never edited, defaults in use")


@frappe.whitelist()
def crm_integration_status():
    """Everything the CRM depends on, one row per dependency. Never raises."""
    _guard()
    settings = get_settings()
    checks = [_sales_check(), _pipeline_check()]
    checks.extend(_email_checks())
    checks.append(_whatsapp_check(settings))
    checks.append(_activity_check())
    checks.append(_storage_check())

    try:
        full_name = frappe.db.get_value("User", frappe.session.user, "full_name")
    except Exception:
        full_name = None

    return {
        "company": frappe.defaults.get_global_default("company") or "",
        "currency": _company_currency(),
        "user": {
            "name": frappe.session.user,
            "full_name": full_name or frappe.session.user,
            "roles": sorted(set(frappe.get_roles(frappe.session.user)) & (WRITE_ROLES | {"Sales User", "CRM User"})),
            "can_edit": _can_edit(),
        },
        "checks": checks,
    }
