"""A personal catalogue link: one buyer, one token, so opens can be tracked."""

import frappe
from frappe.model.document import Document


class CRMCatalogueLink(Document):
    def before_insert(self):
        self.token = frappe.generate_hash(length=24)
        self.open_count = 0
