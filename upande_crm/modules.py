"""Switchable CRM modules — the one list the settings, the API and the SPA share.

Each module is a Check field on `Upande CRM Settings`. Switching one off does
three things, and this file is the authority for all of them:

* the SPA drops its nav entries (`sections` are the keys `nav.js` uses);
* its endpoints refuse to answer (`requires_module`), so an old tab or a hand
  typed URL cannot read what the organisation has turned off;
* cards and actions that belong to it elsewhere hide themselves, via the
  `modules` map `crm_settings` returns.

WhatsApp keeps its original `whatsapp_enabled` field, so sites that had already
switched it off stay switched off.

Modules marked `available=False` are placeholders for features not built yet.
They show on the Modules tab as "coming soon" and report disabled whatever their
field says, so a stray tick cannot expose a half-finished surface.
"""

import functools
from collections import namedtuple

import frappe
from frappe import _
from frappe.utils import cint

Module = namedtuple("Module", "key field label sections group help available")

MODULES = (
    Module("customer_page", "module_customer_page", "Customer page", ("custpage",), "Customers",
           "One page per customer: their orders, prices, contracts and every conversation, in one place.", True),
    Module("leads", "module_leads", "Leads", ("leads",), "Pipeline",
           "Capture new enquiries and follow them until they become opportunities or customers.", True),
    Module("opps", "module_opps", "Opportunities", ("opps",), "Pipeline",
           "Track deals being worked on, and what stage each one has reached.", True),
    Module("prosp", "module_prosp", "Prospects", ("prosp",), "Pipeline",
           "Group the leads and opportunities that belong to one potential customer company.", True),
    Module("mail", "module_mail", "Mail", ("mail",), "Communication",
           "Read and send email from inside the CRM, filed against leads and customers.", True),
    Module("wa", "whatsapp_enabled", "WhatsApp", ("wa",), "Communication",
           "Chat with customers on WhatsApp and send approved message templates.", True),
    Module("calls", "module_calls", "Calls", ("calls",), "Communication",
           "Log phone calls against leads and customers, and see who called whom.", True),
    Module("evt", "module_events", "Events & Tasks", ("evt",), "Communication",
           "Meetings, visits, calendars and follow-up tasks.", True),
    Module("act", "module_activity_log", "Activity log", ("act",), "Communication",
           "A running list of everything that changed across the CRM.", True),
    Module("camp", "module_campaigns", "Campaigns", ("camp",), "Marketing",
           "Email campaigns: who is enrolled, what was sent, and how it went.", True),
    Module("anl", "module_analytics", "Sales analytics", ("anl",), "Insight",
           "Funnel, conversion and revenue charts for sales management.", True),
    Module("rep", "module_reports", "Reports", ("rep",), "Insight",
           "Ready-made reports you can run, filter and export.", True),
    Module("terr", "module_territories", "Territories", ("terr",), "Insight",
           "A world map of where customers, claims and sales are.", True),
    Module("corr", "module_correspondence", "Correspondence", ("corr",), "Insight",
           "Which staff member is in touch with which customer, from real email traffic.", True),
    Module("quotations", "module_quotations", "Quotations", ("quotes",), "Pipeline",
           "Quotations sent to customers and prospects, which ones turned into orders, and the prices quoted over time.", True),
    Module("claims", "module_claims", "Claims", ("claims",), "Service",
           "Log complaints and quality claims against customers and orders, and track them to resolution.", True),
    Module("visits", "module_visits", "Visits", ("visits",), "Communication",
           "Farm visits by customers and customer visits by sales staff, with outcomes and follow-ups.", True),
)

_BY_KEY = {m.key: m for m in MODULES}

# Tabs the customer page can show, in display order.
CUSTPAGE_TABS = ("overview", "timeline", "orders", "quotations", "pricing", "claims", "visits", "contracts")

# Customer page tabs that belong to a switchable module; hidden while it is off.
CUSTPAGE_TAB_MODULE = {"quotations": "quotations", "claims": "claims", "visits": "visits"}


def _settings(settings):
    if settings is not None:
        return settings
    # Imported here: api.settings imports this module for its defaults.
    from upande_crm.api.settings import get_settings

    return get_settings()


def is_enabled(key, settings=None):
    """True when module `key` exists, is built, and is switched on."""
    m = _BY_KEY.get(key)
    if not m or not m.available:
        return False
    return bool(cint(_settings(settings).get(m.field)))


def enabled_map(settings=None):
    s = _settings(settings)
    return {m.key: is_enabled(m.key, s) for m in MODULES}


def module_meta():
    return [
        {"key": m.key, "field": m.field, "label": m.label, "group": m.group,
         "help": m.help, "available": m.available, "sections": list(m.sections)}
        for m in MODULES
    ]


def requires_module(key):
    """Refuse the wrapped endpoint while module `key` is off.

    Goes beneath `@frappe.whitelist()`. The check runs before the endpoint sees
    its arguments, so a switched-off module answers with PermissionError rather
    than with whatever its argument handling would have raised.
    """

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not is_enabled(key):
                frappe.throw(_("This module is switched off in CRM Settings."), frappe.PermissionError)
            return fn(*args, **kwargs)

        return wrapper

    return deco
