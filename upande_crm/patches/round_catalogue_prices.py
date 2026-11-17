"""Catalogue prices are kept to 2 decimal places: round (half up) the prices
already stored on catalogue lines, e.g. 0.232 -> 0.23 and 0.2204 -> 0.22."""

import json

import frappe

from upande_crm.upande_crm.doctype.crm_catalogue.crm_catalogue import round_price


def execute():
    for row in frappe.get_all("CRM Catalogue Line", filters={"prices": ["is", "set"]}, fields=["name", "prices"]):
        try:
            prices = json.loads(row.prices)
        except (TypeError, ValueError):
            continue
        if not isinstance(prices, dict):
            continue
        clean = {cur: {k: round_price(v) if v not in (None, "") else v for k, v in (p or {}).items()}
                 for cur, p in prices.items()}
        if clean != prices:
            frappe.db.set_value("CRM Catalogue Line", row.name, "prices", json.dumps(clean), update_modified=False)
