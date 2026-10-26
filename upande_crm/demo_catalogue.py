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


def _item_group(name):
    if not frappe.db.exists("Item Group", name):
        frappe.get_doc({"doctype": "Item Group", "item_group_name": name,
                        "parent_item_group": frappe.db.get_value("Item Group", {"is_group": 1}, "name")}
                       ).insert(ignore_permissions=True)
    return name


def _demo_item(code, group, description=None):
    if not frappe.db.exists("Item", code):
        frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": code, "item_group": _item_group(group),
                        "stock_uom": "Nos", "is_stock_item": 0, "is_sales_item": 1,
                        "description": description or code}).insert(ignore_permissions=True)
    return code


def _demo_catalogue(title, template, lines, products, terms, currencies="USD", tier=None):
    existing = frappe.db.get_value("CRM Catalogue", {"title": title}, "name")
    if existing and not frappe.db.exists("CRM Catalogue Interest", {"catalogue": existing}):
        frappe.delete_doc("CRM Catalogue", existing, ignore_permissions=True, force=True)
    elif existing:
        return existing
    frappe.set_user(_sales_user())
    try:
        doc = frappe.get_doc({"doctype": "CRM Catalogue", "title": title, "template": template,
                              "company": frappe.db.get_value("Company", {}, "name"), "status": "Live",
                              "currencies": currencies, "volume_tier_qty": tier, "terms": terms,
                              "valid_from": "2026-10-01", "valid_to": "2027-03-31", "lines": lines})
        doc.insert(ignore_permissions=True)
        for p in doc.products:
            extra = products.get(p.item) or {}
            p.badges, p.note = extra.get("badges"), extra.get("note")
            p.specs = frappe.as_json(extra["specs"]) if extra.get("specs") else None
        doc.save(ignore_permissions=True)
    finally:
        frappe.set_user("Administrator")
    frappe.db.commit()
    print(f"{doc.name} {title}: {len(doc.lines)} lines, link {frappe.utils.get_url('/catalogue/' + doc.public_token)}")
    return doc.name


def seed_avocado():
    hass = _demo_item("Hass, class 1", "Hass", "Dry matter above 24%, ripens evenly after arrival.")
    fuerte = _demo_item("Fuerte, class 1", "Fuerte", "Smooth green skin, creamy and mild.")
    price = {12: 13.9, 14: 13.4, 16: 12.4, 18: 12.1, 20: 11.8, 22: 11.2, 24: 10.6}
    lines = [{"item": hass, "grade": str(c), "box_type": "4 kg carton", "pack_qty": 1, "bunch": str(c), "weight": 4,
              "prices": frappe.as_json({"USD": {"price": p}})} for c, p in price.items()]
    lines += [{"item": fuerte, "grade": str(c), "box_type": "4 kg carton", "pack_qty": 1, "bunch": str(c), "weight": 4,
               "prices": frappe.as_json({"USD": {"price": round(p - 1.3, 2)}})} for c, p in list(price.items())[1:6]]
    products = {hass: {"badges": "GlobalG.A.P.", "specs": {"dry_matter": "24–26%"}},
                fuerte: {"specs": {"dry_matter": "22–24%"}}}
    return _demo_catalogue("Avocado export season 2027", "Avocado export", lines, products,
                           "<p>Sea-freight, 40 ft reefer from Mombasa, about 21 days to Rotterdam.</p>"
                           "<p>Orders close ten days before each sailing.</p>")


def seed_coffee():
    sl28 = _demo_item("Lot 14 · SL28", "Washed Arabica", "Blackcurrant, bright acidity, syrupy body.")
    ruiru = _demo_item("Lot 9 · Ruiru 11", "Washed Arabica", "Red apple and cane sugar, round and sweet.")
    rows = [(sl28, "AA", 9.6, "Washed"), (sl28, "AB", 8.4, "Washed"), (sl28, "PB", 8.9, "Washed"),
            (ruiru, "AA", 8.2, "Natural"), (ruiru, "AB", 7.4, "Natural")]
    lines = [{"item": i, "grade": g, "box_type": "60 kg jute", "pack_qty": 60, "weight": 60,
              "specs": frappe.as_json({"process": proc}), "prices": frappe.as_json({"USD": {"price": p}})}
             for i, g, p, proc in rows]
    products = {sl28: {"badges": "Microlot", "specs": {"cup_score": "86", "variety": "SL28"}},
                ruiru: {"badges": "Top lot", "specs": {"cup_score": "84", "variety": "Ruiru 11"}}}
    return _demo_catalogue("Estate lots 2026/27", "Coffee lots", lines, products,
                           "<p>Samples on request. Shipped from Mombasa in GrainPro-lined jute.</p>")
