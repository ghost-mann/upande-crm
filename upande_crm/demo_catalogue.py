"""Demo data for catalogues: Marginpar's real offer sheet on a test site.

    bench --site webstore.localhost execute upande_crm.demo_catalogue.seed

Creates (only if missing) an Item per variety on the sheet, except the
"N varieties" summary rows, which are left unmatched on purpose so the import's
map-by-hand step has something to do; placeholder photos on two Items; a Sales
User `crm.sales@webstore.test` (password `admin`); and a Live USD + EUR
catalogue owned by that user, built through the same import the CRM uses.
Never run it on a client's site: it creates Items.
"""

import os

import frappe

from upande_crm.api.catalogue_import import match_items, parse_offer_sheet

SHEET = "/home/austin/Downloads/Marginpar FOB Combined pricelist Oct-Dec 2026 final.xlsx"
SALES = "crm.sales@webstore.test"
TITLE = "Marginpar FOB offer Oct–Dec 2026"
PHOTO = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><rect width="120" height="120" fill="{bg}"/>
<g transform="translate(60 56)">{petals}<circle r="9" fill="#f6c26b"/></g>
<path d="M60 70 V112" stroke="#4f7a3a" stroke-width="4"/></svg>"""


def _photo(item, colour, bg):
    petals = "".join(f'<ellipse rx="9" ry="20" cy="-16" fill="{colour}" transform="rotate({a})"/>' for a in range(0, 360, 45))
    f = frappe.get_doc({"doctype": "File", "file_name": f"{frappe.scrub(item)[:40]}.svg", "is_private": 0,
                        "content": PHOTO.format(bg=bg, petals=petals), "attached_to_doctype": "Item",
                        "attached_to_name": item}).insert(ignore_permissions=True)
    frappe.db.set_value("Item", item, "image", f.file_url)


def _sales_user():
    if not frappe.db.exists("User", SALES):
        frappe.get_doc({"doctype": "User", "email": SALES, "first_name": "Sales", "last_name": "Demo",
                        "send_welcome_email": 0, "user_type": "System User",
                        "roles": [{"role": "Sales User"}, {"role": "CRM User"}]}).insert(ignore_permissions=True)
        from frappe.utils.password import update_password

        update_password(SALES, "admin")
    return SALES


def seed(path=SHEET):
    if not os.path.exists(path):
        frappe.throw(f"Offer sheet not found at {path}")
    from upande_crm.setup import ensure_crm_role_permissions

    ensure_crm_role_permissions()
    content = open(path, "rb").read()
    out = parse_offer_sheet(content, ["USD", "EUR"])
    group = "Products" if frappe.db.exists("Item Group", "Products") else \
        frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    made = []
    for product in dict.fromkeys(l["product"] for l in out["lines"]):
        if "varieties" in product.lower() or frappe.db.exists("Item", {"item_name": product}):
            continue
        frappe.get_doc({"doctype": "Item", "item_code": product, "item_name": product, "item_group": group,
                        "stock_uom": "Nos", "is_stock_item": 0, "is_sales_item": 1}).insert(ignore_permissions=True)
        made.append(product)
    for item, colour, bg in (("Agapanthus 'Gletsjer'", "#f4f4f8", "#cfdcea"),
                             ("Aster (Novi Belgii Grp) Dark Milka", "#7b4fa8", "#ece4f3")):
        name = frappe.db.get_value("Item", {"item_name": item}, "name")
        if name and not frappe.db.get_value("Item", name, "image"):
            _photo(name, colour, bg)

    user = _sales_user()
    lines = [l for l in match_items(out["lines"]) if l["item"]]
    existing = frappe.db.get_value("CRM Catalogue", {"title": TITLE}, "name")
    if existing:
        frappe.delete_doc("CRM Catalogue", existing, ignore_permissions=True, force=True)
    frappe.set_user(user)
    try:
        cat = frappe.get_doc({
            "doctype": "CRM Catalogue", "title": TITLE, "company": frappe.db.get_value("Company", {}, "name"),
            "status": "Live", "currencies": "USD, EUR", "volume_tier_qty": 4, "terms": out["terms"],
            "valid_from": "2026-10-01", "valid_to": "2026-12-31",
            "lines": [{k: l.get(k) for k in ("item", "grade", "box_type", "color", "vbn", "pack_qty", "bunch",
                                              "weight", "info_url")} | {"prices": frappe.as_json(l["prices"])}
                      for l in lines],
        }).insert(ignore_permissions=True)
    finally:
        frappe.set_user("Administrator")
    frappe.db.commit()
    print(f"items created: {len(made)}; catalogue {cat.name}: {len(cat.lines)} lines")
    print(f"public link: {frappe.utils.get_url('/catalogue/' + cat.public_token)}")
    return cat.name


# ---------------------------------------------------------------- magazine
FLOWER_NOTES = {
    "Agapanthus 'Gletsjer'": ("Bestseller", "Ice-white heads that open evenly and hold two weeks in the vase."),
    "Aster (Novi Belgii Grp) Dark Milka": ("New this season", "Deep violet sprays — a filler that photographs."),
    "Aster (Novi-belgii Grp) Double Date Pink": ("Limited", "Fully double pink buttons, cut in small volumes."),
}
FLOWER_MIXES = [
    ("Cool whites", "White"),
    ("Purple & blush", ("Purple", "Pink")),
]


def dress_flowers(name=None):
    """Give the Marginpar catalogue its magazine dressing in place — template,
    badges, notes and two mixes — without touching its lines, links or
    interests. Safe to re-run."""
    name = name or frappe.db.get_value("CRM Catalogue", {"title": TITLE}, "name")
    doc = frappe.get_doc("CRM Catalogue", name)
    doc.template = "Flowers almanac"
    doc.save(ignore_permissions=True)  # syncs one product row per item
    names = {frappe.db.get_value("Item", p.item, "item_name"): p for p in doc.products}
    for item_name, (badge, note) in FLOWER_NOTES.items():
        row = names.get(item_name)
        if row:
            row.badges, row.note = badge, note
    doc.set("mixes", [])
    for title, colours in FLOWER_MIXES:
        colours = (colours,) if isinstance(colours, str) else colours
        picks, seen = [], set()
        for line in doc.lines:
            if line.color in colours and line.box_type == "Standard" and line.item not in seen and len(picks) < 3:
                picks.append({"line": line.name, "boxes": 1})
                seen.add(line.item)
        if picks:
            doc.append("mixes", {"title": title, "items": frappe.as_json(picks)})
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"{doc.name}: {len(doc.products)} products, {len(doc.mixes)} mixes")
    return doc.name
