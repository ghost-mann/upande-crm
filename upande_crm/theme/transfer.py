"""Shipped theme presets.

A preset is a JSON file of seed colours next to this module. Applying one writes
those seeds onto `Upande CRM Settings` and records which preset was applied, so
the UI can show it as selected.

Unlike the webstore's equivalent, there is no export/import: the CRM's theme is
eight colours, small enough that a preset is worth reviewing in git rather than
passing around as a payload.
"""

import json
import os
import re

import frappe
from frappe import _

from upande_crm.theme.tokens import SEED_FIELDS

PRESET_DIR = os.path.join(os.path.dirname(__file__), "presets")
# Rejects '/', '.' and '%' outright, so no name can escape PRESET_DIR.
PRESET_NAME_RE = re.compile(r"^[a-z0-9_]+$")

DEFAULT_PRESET = "upande"


def _read(name):
    path = os.path.join(PRESET_DIR, f"{name}.json")
    if not os.path.isfile(path):
        frappe.throw(_("No shipped preset named {0}.").format(name))
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _validate_name(name):
    if not isinstance(name, str) or not PRESET_NAME_RE.match(name):
        frappe.throw(_("Invalid preset name."))
    return name


def list_presets():
    """[{name, label, seeds}] for every shipped preset. Never raises."""
    if not os.path.isdir(PRESET_DIR):
        return []
    out = []
    for filename in sorted(os.listdir(PRESET_DIR)):
        if not filename.endswith(".json"):
            continue
        name = filename[: -len(".json")]
        try:
            payload = _read(name)
        except Exception:
            continue
        seeds = payload.get("seeds") or {}
        out.append({
            "name": name,
            "label": payload.get("label") or name.replace("_", " ").title(),
            "seeds": {k: v for k, v in seeds.items() if k in SEED_FIELDS},
        })
    return out


def preset_seeds(name):
    """The seed dict for one preset, filtered to known fields."""
    payload = _read(_validate_name(name))
    seeds = payload.get("seeds") or {}
    if not isinstance(seeds, dict):
        frappe.throw(_("Preset {0} has no seeds.").format(name))
    return {k: v for k, v in seeds.items() if k in SEED_FIELDS}
