"""Demo-data seeder for the Upande CRM dashboard.

Populates a full sales pipeline (Prospects -> Leads -> Opportunities ->
Quotations -> submitted Sales Orders) plus linked Events, ToDos and email
Communications, themed as a Kenya cut-flower export business. Every record is
tagged ``crm-demo`` so the whole set can be removed in one call.

Usage (from the bench directory):

    bench --site <site> execute upande_crm.demo_data.seed_demo
    bench --site <site> execute upande_crm.demo_data.clear_demo   # remove it all

``seed_demo`` clears any previous demo batch first, so it is safe to re-run.

Design notes
------------
* Nothing here posts to the general ledger: Sales Orders submit without GL
  impact, and no Sales Invoices are created. The CRM revenue KPI, funnel and
  trends all read Sales Order ``base_grand_total`` (company currency), so
  submitted SOs are enough to light up every widget.
* Amounts are in the demo company's own currency (KES) via a dedicated demo
  price list, so no Currency Exchange records are needed.
* ``creation`` is back-dated after insert (the dashboard buckets Leads /
  Prospects / Customers by ``creation``) so trends span recent months rather
  than spiking on today.
"""

import random

import frappe
from frappe.utils import add_days, nowdate, getdate

DEMO_TAG = "crm-demo"
ITEM_CODE = "DEMO-ROSE-EXPORT"
PRICE_LIST = "Demo KES Price List"

# Doctypes that carry the demo tag, in delete-safe order (children/links first).
_TAGGED_DOCTYPES = [
    "Communication", "ToDo", "Event", "Sales Order", "Quotation",
    "Opportunity", "Lead", "Prospect", "Customer",
]

# ------------------------------------------------------------------ demo content
# Fictional export buyers (distinct from the real customer groups on this site).
_BUYERS = [
    ("Rotterdam Bloom Traders B.V.", "Netherlands", "procurement@rotterdambloom.nl"),
    ("Dubai Petal Imports LLC", "United Arab Emirates", "orders@dubaipetal.ae"),
    ("Highland Blooms UK Ltd", "United Kingdom", "buying@highlandblooms.co.uk"),
    ("Moscow Rose Distributors OOO", "Russia", "import@moscowrose.ru"),
    ("Berlin Fresh Florals GmbH", "Germany", "einkauf@berlinfresh.de"),
    ("Sydney Stem Wholesale Pty", "Australia", "sales@sydneystem.com.au"),
    ("Oslo Nordic Flowers AS", "Norway", "post@oslonordic.no"),
    ("Tokyo Sakura Import KK", "Japan", "trade@tokyosakura.jp"),
]

# Leads: (contact person, company, source, status, qualification, territory)
_LEADS = [
    ("Marta Visser", "Amsterdam Petals Co-op", "Trade Show", "Open", "In Process", "Netherlands"),
    ("Omar Al-Farsi", "Gulf Bloom Trading", "Referral", "Interested", "Qualified", "United Arab Emirates"),
    ("Sophie Turner", "Covent Garden Flowers", "Website", "Replied", "In Process", "United Kingdom"),
    ("Ivan Petrov", "St. Petersburg Roses", "Cold Call", "Lead", "Unqualified", "Russia"),
    ("Lena Fischer", "Hamburg Flora Import", "Exhibition", "Open", "Qualified", "Germany"),
    ("James Whitfield", "Melbourne Blooms", "LinkedIn", "Opportunity", "Qualified", "Australia"),
    ("Astrid Berg", "Nordic Stems", "Website", "Converted", "Qualified", "Norway"),
    ("Kenji Watanabe", "Osaka Flower House", "Trade Show", "Quotation", "Qualified", "Japan"),
    ("Fatima Nour", "Doha Florals", "Referral", "Interested", "In Process", "Qatar"),
    ("Pieter de Vries", "Aalsmeer Direct", "Exhibition", "Converted", "Qualified", "Netherlands"),
    ("Grace Mwangi", "Nairobi Event Florists", "Website", "Open", "In Process", "Kenya"),
    ("Carlos Mendez", "Madrid Rosas", "Cold Call", "Lost Quotation", "Unqualified", "Spain"),
    ("Anna Kowalski", "Warsaw Bloom Market", "LinkedIn", "Lead", "Unqualified", "Poland"),
    ("Liam O'Brien", "Dublin Petals", "Referral", "Replied", "In Process", "Ireland"),
    ("Yuki Tanaka", "Tokyo Green Trade", "Trade Show", "Opportunity", "Qualified", "Japan"),
    ("Noor Hassan", "Kuwait Flower Souk", "Exhibition", "Interested", "In Process", "Kuwait"),
    ("Emma Larsson", "Stockholm Stems", "Website", "Open", "Qualified", "Sweden"),
    ("David Chen", "Singapore Petal Hub", "LinkedIn", "Converted", "Qualified", "Singapore"),
    ("Sara Bakker", "Utrecht Flowers", "Referral", "Do Not Contact", "Unqualified", "Netherlands"),
    ("Tom Becker", "Munich Rose Co", "Cold Call", "Open", "In Process", "Germany"),
    ("Zara Ahmed", "Abu Dhabi Blooms", "Trade Show", "Quotation", "Qualified", "United Arab Emirates"),
    ("Henrik Sorensen", "Copenhagen Flora", "Website", "Converted", "Qualified", "Denmark"),
    ("Isabella Rossi", "Milano Fiori", "Exhibition", "Interested", "In Process", "Italy"),
    ("Paul Adeyemi", "Lagos Luxe Flowers", "Referral", "Lead", "Unqualified", "Nigeria"),
    ("Mei Lin", "Shanghai Bloom Express", "LinkedIn", "Open", "In Process", "China"),
    ("Robert King", "Toronto Petal Trade", "Website", "Replied", "Qualified", "Canada"),
    ("Amara Okafor", "Accra Flower Market", "Trade Show", "Interested", "In Process", "Ghana"),
    ("Nina Volkov", "Kyiv Rose Import", "Cold Call", "Lead", "Unqualified", "Ukraine"),
    ("Hans Muller", "Zurich Blossom AG", "Exhibition", "Converted", "Qualified", "Switzerland"),
    ("Priya Sharma", "Mumbai Floral Traders", "LinkedIn", "Open", "In Process", "India"),
]

# Prospects: (company, industry, no_of_employees, territory)
_PROSPECTS = [
    ("EuroFlora Wholesale Group", "Agriculture", "201-500", "Netherlands"),
    ("Gulf Horticulture Holdings", "Consumer Products", "501-1000", "United Arab Emirates"),
    ("British Floral Distributors", "Grocery", "51-200", "United Kingdom"),
    ("Rossiya Flower Network", "Consumer Products", "1000+", "Russia"),
    ("Deutsche Blumen AG", "Consumer Products", "201-500", "Germany"),
    ("Pacific Bloom Importers", "Agriculture", "11-50", "Australia"),
    ("Scandinavian Petal Union", "Grocery", "51-200", "Norway"),
    ("Nippon Flower Trading", "Consumer Products", "201-500", "Japan"),
    ("Iberia Rosas Group", "Agriculture", "11-50", "Spain"),
    ("Nordic Fresh Logistics", "Grocery", "51-200", "Sweden"),
    ("Asia Pacific Florals", "Consumer Products", "501-1000", "Singapore"),
    ("Emirates Garden Supplies", "Agriculture", "11-50", "United Arab Emirates"),
]

_STAGES = ["Prospecting", "Qualification", "Needs Analysis", "Value Proposition",
           "Identifying Decision Makers", "Proposal/Price Quote", "Negotiation/Review"]


# ------------------------------------------------------------------ helpers
def _cfg():
    """Resolve the site-specific bits the seeder needs (company, users, currency)."""
    company = "Karen Roses" if frappe.db.exists("Company", "Karen Roses") else \
        frappe.db.get_value("Company", {"is_group": 0}, "name")
    currency = frappe.db.get_value("Company", company, "default_currency") or "KES"
    users = [u.parent for u in frappe.get_all(
        "Has Role",
        filters={"role": ["in", ["Sales User", "Sales Manager", "CRM User", "System Manager"]],
                 "parenttype": "User"},
        fields=["parent"], distinct=True, limit=20)
        if u.parent not in ("Administrator", "Guest") and "@" in (u.parent or "")]
    users = users[:5] or [frappe.session.user]

    # Site customizations make several custom fields mandatory on Lead / Sales
    # Order. Resolve real link targets so the demo docs validate.
    def first(dt, prefer=None):
        if prefer and frappe.db.exists(dt, prefer):
            return prefer
        return frappe.db.get_value(dt, {}, "name") if frappe.db.exists("DocType", dt) else None

    return {
        "company": company, "currency": currency, "users": users,
        "business_unit": first("Business Unit", "Roses"),
        "farm": first("Farm", "Kapkolia"),
        "consignee": first("Consignee"),
    }


def _tag(dt, name):
    from frappe.desk.doctype.tag.tag import add_tag
    try:
        add_tag(DEMO_TAG, dt, name)
    except Exception:
        # Fall back to writing the tag column directly if the helper is unavailable.
        existing = frappe.db.get_value(dt, name, "_user_tags") or ""
        if DEMO_TAG not in existing:
            frappe.db.set_value(dt, name, "_user_tags", (existing + "," + DEMO_TAG).strip(","),
                                update_modified=False)


def _set_cols(dt, name, **cols):
    """db_set only the columns that actually exist on the table (no modified bump)."""
    have = set(frappe.db.get_table_columns(dt))
    for k, v in cols.items():
        if k in have:
            frappe.db.set_value(dt, name, k, v, update_modified=False)


def _backdate(dt, name, days_ago):
    frappe.db.set_value(dt, name, "creation", f"{add_days(nowdate(), -days_ago)} 09:00:00",
                        update_modified=False)


def _ensure_item(cfg):
    if not frappe.db.exists("Item", ITEM_CODE):
        group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
        uom = "Nos" if frappe.db.exists("UOM", "Nos") else frappe.db.get_value("UOM", {}, "name")
        item = frappe.get_doc({
            "doctype": "Item", "item_code": ITEM_CODE,
            "item_name": "Demo Rose Stems (Export Grade)",
            "item_group": group, "stock_uom": uom,
            "is_stock_item": 0, "is_sales_item": 1, "is_purchase_item": 0,
            "include_item_in_manufacturing": 0,
            "description": "Demo export-grade rose stems for CRM dashboard sample data.",
        })
        item.insert(ignore_permissions=True)
        _tag("Item", ITEM_CODE)
    # A site hook may default new items to disabled; force-enable so it is sellable.
    _set_cols("Item", ITEM_CODE, disabled=0, end_of_life=None)
    if not frappe.db.exists("Price List", PRICE_LIST):
        pl = frappe.get_doc({
            "doctype": "Price List", "price_list_name": PRICE_LIST,
            "selling": 1, "buying": 0, "currency": cfg["currency"],
        })
        pl.insert(ignore_permissions=True)


# ------------------------------------------------------------------ seed
def seed_demo():
    """Create the full tagged demo pipeline. Clears any prior demo batch first."""
    random.seed(42)
    clear_demo()
    cfg = _cfg()
    _ensure_item(cfg)

    made = {k: 0 for k in ["Customer", "Prospect", "Lead", "Opportunity",
                           "Quotation", "Sales Order", "Event", "ToDo", "Communication"]}

    def terr(t):
        return t if frappe.db.exists("Territory", t) else "All Territories"

    def country(t):
        return t if frappe.db.exists("Country", t) else "Kenya"

    seg_choices = [s for s in ["Wholesale", "Auctions", "Florists", "Supermarkets",
                               "Direct Sales", "Garden Centers"]
                   if frappe.db.exists("Market Segment", s)] or ["All Market Segments"]

    # --- Customers (export buyers) --------------------------------------
    customers = []
    for i, (nm, territory, email) in enumerate(_BUYERS):
        cust = frappe.get_doc({
            "doctype": "Customer", "customer_name": nm,
            "customer_type": "Company", "customer_group": "Commercial"
            if frappe.db.exists("Customer Group", "Commercial") else
            frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
            "territory": terr(territory),
            "default_currency": cfg["currency"],
        })
        cust.insert(ignore_permissions=True)
        _set_cols("Customer", cust.name, account_manager=cfg["users"][i % len(cfg["users"])])
        _backdate("Customer", cust.name, random.randint(20, 160))
        _tag("Customer", cust.name)
        customers.append((cust.name, nm, email, territory))
        made["Customer"] += 1

    # --- Prospects ------------------------------------------------------
    for (company, industry, size, territory) in _PROSPECTS:
        p = frappe.get_doc({
            "doctype": "Prospect", "company_name": company,
            "industry": industry if frappe.db.exists("Industry Type", industry) else None,
            "no_of_employees": size, "territory": terr(territory),
        })
        p.insert(ignore_permissions=True)
        _backdate("Prospect", p.name, random.randint(10, 150))
        _tag("Prospect", p.name)
        made["Prospect"] += 1

    # --- Leads ----------------------------------------------------------
    leads = []
    for i, (person, company, source, status, qual, territory) in enumerate(_LEADS):
        ld = frappe.get_doc({
            "doctype": "Lead", "lead_name": person, "company_name": company,
            "status": status, "qualification_status": qual,
            "territory": terr(territory),
            "lead_owner": cfg["users"][i % len(cfg["users"])],
            "email_id": "%s@%s.com" % (
                "".join(c for c in person.split()[0] if c.isalnum()).lower() or "contact",
                "".join(c for c in company if c.isalnum()).lower()[:20] or "demo"),
            # Site-mandatory custom fields:
            "custom_business_unit": cfg["business_unit"],
            "custom_business_registration_number": f"DEMO-REG-{1000 + i}",
            "market_segment": seg_choices[i % len(seg_choices)],
            "country": country(territory),
            "city": ["Amsterdam", "Dubai", "London", "Moscow", "Berlin",
                     "Sydney", "Oslo", "Tokyo"][i % 8],
            "mobile_no": f"+2547{random.randint(10, 99)}{random.randint(100000, 999999)}",
            "whatsapp_no": f"+2547{random.randint(10, 99)}{random.randint(100000, 999999)}",
        })
        ld.insert(ignore_permissions=True)
        _set_cols("Lead", ld.name, source=source)
        _backdate("Lead", ld.name, random.randint(3, 150))
        _tag("Lead", ld.name)
        leads.append((ld.name, person, company, territory))
        made["Lead"] += 1

    # --- Opportunities (from Leads, Prospects and Customers) ------------
    opp_statuses = ["Open", "Open", "Quotation", "Replied", "Converted", "Converted", "Lost"]
    for i in range(20):
        kind = ["Lead", "Prospect", "Customer"][i % 3]
        if kind == "Customer":
            party, cname = customers[i % len(customers)][0], customers[i % len(customers)][1]
            terr_v = customers[i % len(customers)][3]
        elif kind == "Prospect":
            row = _PROSPECTS[i % len(_PROSPECTS)]
            party, cname, terr_v = row[0], row[0], row[3]
        else:
            row = leads[i % len(leads)]
            party, cname, terr_v = row[0], row[2], row[3]
        status = opp_statuses[i % len(opp_statuses)]
        opp = frappe.get_doc({
            "doctype": "Opportunity",
            "opportunity_from": kind, "party_name": party,
            "customer_name": cname,
            "opportunity_type": "Sales",
            "status": status,
            "sales_stage": _STAGES[i % len(_STAGES)] if frappe.db.exists(
                "Sales Stage", _STAGES[i % len(_STAGES)]) else None,
            "probability": random.choice([10, 25, 40, 55, 70, 85, 100]),
            "territory": terr(terr_v),
            "opportunity_owner": cfg["users"][i % len(cfg["users"])],
            "currency": cfg["currency"],
            "transaction_date": add_days(nowdate(), -random.randint(2, 140)),
        })
        opp.insert(ignore_permissions=True)
        _set_cols("Opportunity", opp.name, source=random.choice(
            ["Trade Show", "Website", "Referral", "Exhibition", "LinkedIn"]))
        _tag("Opportunity", opp.name)
        made["Opportunity"] += 1

    # --- Quotations (draft; the funnel counts all doc-statuses) ---------
    for i in range(12):
        cust = customers[i % len(customers)]
        q = frappe.get_doc({
            "doctype": "Quotation",
            "quotation_to": "Customer", "party_name": cust[0],
            "order_type": "Sales", "company": cfg["company"],
            "currency": cfg["currency"], "conversion_rate": 1,
            "selling_price_list": PRICE_LIST, "price_list_currency": cfg["currency"],
            "plc_conversion_rate": 1, "ignore_pricing_rule": 1,
            "transaction_date": add_days(nowdate(), -random.randint(2, 120)),
            "items": [{"item_code": ITEM_CODE, "qty": random.randint(2000, 40000),
                       "rate": random.choice([28, 32, 38, 45, 52]), "uom": "Nos"}],
        })
        q.insert(ignore_permissions=True)
        _tag("Quotation", q.name)
        made["Quotation"] += 1

    # --- Sales Orders (submitted; drive revenue KPI / funnel / trends) --
    for i in range(18):
        cust = customers[i % len(customers)]
        txn = add_days(nowdate(), -random.randint(1, 150))
        boxes = random.randint(20, 200)
        stems_per_box = 300
        stems = boxes * stems_per_box
        so = frappe.get_doc({
            "doctype": "Sales Order",
            "customer": cust[0], "company": cfg["company"],
            "currency": cfg["currency"], "conversion_rate": 1,
            "selling_price_list": PRICE_LIST, "price_list_currency": cfg["currency"],
            "plc_conversion_rate": 1, "ignore_pricing_rule": 1,
            "transaction_date": txn, "delivery_date": add_days(txn, 14),
            # Site-mandatory custom fields:
            "custom_sales_order_type": "Roses",
            "custom_business_unit": cfg["business_unit"],
            "custom_order_name": f"DEMO-{cust[1].split()[0].upper()}-{1000 + i}",
            "custom_farm": cfg["farm"],
            "custom_consignee": cfg["consignee"],
            "items": [{"item_code": ITEM_CODE, "qty": boxes,
                       "rate": random.choice([1200, 1800, 2400, 3000]), "uom": "Nos",
                       "delivery_date": add_days(txn, 14),
                       # Roses stem/box custom fields (site validation requires them):
                       "custom_ordered_quantity": stems,
                       "custom_total_stems": stems,
                       "custom_available_quantity": stems,
                       "custom_allocated_qty": stems,
                       "custom_number_of_boxes": boxes}],
        })
        so.insert(ignore_permissions=True)
        so.submit()
        _tag("Sales Order", so.name)
        made["Sales Order"] += 1

    # --- Events ---------------------------------------------------------
    cats = ["Meeting", "Call", "Visit", "Meeting", "Call"]
    for i in range(16):
        cust = customers[i % len(customers)]
        starts = add_days(nowdate(), random.randint(-45, 20))
        ev = frappe.get_doc({
            "doctype": "Event",
            "subject": f"{cats[i % len(cats)]} — {cust[1]}",
            "event_category": cats[i % len(cats)],
            "event_type": "Private",
            "starts_on": f"{starts} 10:00:00",
            "status": "Open" if i % 3 else "Completed",
        })
        ev.insert(ignore_permissions=True)
        _tag("Event", ev.name)
        made["Event"] += 1

    # --- ToDos (linked to CRM records) ----------------------------------
    todo_targets = [("Lead", leads[i][0]) for i in range(len(leads))] + \
                   [("Customer", c[0]) for c in customers]
    for i in range(22):
        ref = todo_targets[i % len(todo_targets)]
        td = frappe.get_doc({
            "doctype": "ToDo",
            "description": f"Follow up on {ref[0]} — send updated export price sheet",
            "priority": random.choice(["Low", "Medium", "High", "High"]),
            "status": "Open",
            "allocated_to": cfg["users"][i % len(cfg["users"])],
            "reference_type": ref[0], "reference_name": ref[1],
            "date": add_days(nowdate(), random.randint(0, 21)),
        })
        td.insert(ignore_permissions=True)
        _tag("ToDo", td.name)
        made["ToDo"] += 1

    # --- Communications (emails, linked, Sent + Received) ---------------
    subjects = [
        "Quotation for Grade-A rose stems",
        "Re: Weekly availability list",
        "Order confirmation — shipment schedule",
        "New season Intermediate roses",
        "Price update — premium 50cm stems",
        "Cool-chain logistics query",
        "Re: Sample dispatch tracking",
        "Standing order for Valentine's peak",
    ]
    for i in range(40):
        cust = customers[i % len(customers)]
        sent = i % 2 == 0
        me = cfg["users"][i % len(cfg["users"])]
        ref_dt, ref_nm = random.choice(
            [("Customer", cust[0])] +
            ([("Lead", leads[i % len(leads)][0])] if leads else []) +
            ([("Opportunity", None)] if False else []))
        cm = frappe.get_doc({
            "doctype": "Communication",
            "communication_type": "Communication",
            "communication_medium": "Email",
            "sent_or_received": "Sent" if sent else "Received",
            "subject": subjects[i % len(subjects)],
            "content": f"<p>Regarding {cust[1]} — {subjects[i % len(subjects)]}.</p>",
            "sender": me if sent else cust[2],
            "recipients": cust[2] if sent else me,
            "communication_date": f"{add_days(nowdate(), -random.randint(0, 60))} 11:30:00",
            "reference_doctype": ref_dt, "reference_name": ref_nm,
            "status": "Open" if not sent else "Linked",
            "seen": 1 if sent else random.choice([0, 0, 1]),
        })
        cm.insert(ignore_permissions=True)
        _tag("Communication", cm.name)
        made["Communication"] += 1

    frappe.db.commit()
    print("Seeded demo data (all tagged '%s'):" % DEMO_TAG)
    for k, v in made.items():
        print("  %-14s %d" % (k, v))
    return made


# ------------------------------------------------------------------ teardown
def clear_demo():
    """Delete every record carrying the demo tag (cancels submitted docs first)."""
    removed = {}
    for dt in _TAGGED_DOCTYPES:
        names = [r.name for r in frappe.get_all(
            dt, filters={"_user_tags": ["like", f"%{DEMO_TAG}%"]}, fields=["name"])]
        n = 0
        for nm in names:
            try:
                doc = frappe.get_doc(dt, nm)
                if getattr(doc, "docstatus", 0) == 1:
                    doc.cancel()
                frappe.delete_doc(dt, nm, force=True, ignore_permissions=True)
                n += 1
            except Exception as e:
                frappe.log_error(f"clear_demo {dt} {nm}: {e}", "crm demo teardown")
        removed[dt] = n
    # Demo item + price list
    for dt, nm in [("Item", ITEM_CODE), ("Price List", PRICE_LIST)]:
        if frappe.db.exists(dt, nm):
            try:
                frappe.delete_doc(dt, nm, force=True, ignore_permissions=True)
                removed[nm] = 1
            except Exception:
                pass
    frappe.db.commit()
    if any(removed.values()):
        print("Removed demo data:", {k: v for k, v in removed.items() if v})
    return removed
