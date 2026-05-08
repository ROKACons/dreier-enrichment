import re

KNOWN_BRANDS = {
    "migros": "Migros",
    "coop": "Coop",
    "sbb": "SBB",
    "post": "Die Post",
    "manor": "Manor",
    "globus": "Globus",
}


def parse_company_input(raw: str) -> dict:
    """
    Accepts a company name or domain (URL) and returns a normalized dict.
    Examples:
      "dreierfashion.ch"       → {companyName: "Dreierfashion", domain: "dreierfashion.ch", ...}
      "https://www.dreier.ch"  → {companyName: "Dreier", domain: "dreier.ch", ...}
      "Dreier AG"              → {companyName: "Dreier AG", domain: None, ...}
    """
    text = raw.strip()
    domain_pattern = re.compile(
        r"^(https?://)?(www\.)?([a-zA-Z0-9\-]+(\.[a-zA-Z0-9\-]+)+)(/.*)?\s*$"
    )
    match = domain_pattern.match(text)

    if match:
        domain = match.group(3).lower().rstrip("/")
        base = domain.split(".")[0]
        company_name = base.replace("-", " ").title()
        website = f"https://{domain}"
    else:
        domain = None
        website = None
        company_name = text

    lookup = company_name.lower().strip().split()[0] if company_name else ""
    if lookup in KNOWN_BRANDS:
        company_name = KNOWN_BRANDS[lookup]

    return {
        "companyName": company_name,
        "domain": domain,
        "website": website,
        "originalInput": raw.strip(),
    }
