"""Country strings that are not Territory names, and what they mean.

Two doctypes here carry a free `country` string rather than a Territory link —
`Consignee` most importantly — and those strings come from a different
vocabulary. Measured on kaitet.local: 13 of 85 distinct consignee countries do
not match any Territory name, because the list they were typed against uses
ISO-3166 official forms ("Russian Federation") where Territory uses common ones
("Russia").

Only unambiguous renames are listed. Places with no Territory at all are named
in UNMAPPABLE rather than being quietly bent onto a neighbour: Réunion is not
France for sales purposes, and a consignee in Taiwan should show up as
un-attributable rather than silently vanish or land somewhere wrong.
"""

# Country string -> Territory name. Renames only.
COUNTRY_ALIASES = {
	"Congo": "Republic of the Congo",
	"Congo, The Democratic Republic of the": "Democratic Republic of the Congo",
	"Cote d'Ivoire": "Côte d'Ivoire",
	"Czech Republic": "Czechia (Czech Republic)",
	"Korea": "South Korea",
	"Libyan Arab Jamahiriya": "Libya",
	"Northern Ireland": "United Kingdom",
	"Russian Federation": "Russia",
	"United States": "United States of America (USA)",
}

# Real places with no Territory record. Kept explicit so they are reported as
# un-attributable instead of being dropped or forced onto a nearby country.
UNMAPPABLE = {
	"Montserrat",       # UK overseas territory
	"Netherlands Antilles",  # dissolved 2010
	"Réunion",          # French overseas department
	"Taiwan",           # no Territory record on this site
}


def to_territory(country: str | None) -> str | None:
	"""The Territory a country string denotes, or None if it denotes none."""
	if not country:
		return None
	country = country.strip()
	if country in UNMAPPABLE:
		return None
	return COUNTRY_ALIASES.get(country, country)
