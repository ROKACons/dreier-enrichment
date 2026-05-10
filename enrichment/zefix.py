"""
ZEFIX Lookup via offizielle ZefixPublicREST API (mit Basic Auth).
Doku: https://www.zefix.admin.ch/ZefixPublicREST/swagger-ui/index.html
"""
import base64
from enrichment import ssl_session as requests
from config import ZEFIX_USER, ZEFIX_PASS

_BASE = "https://www.zefix.admin.ch/ZefixPublicREST/api/v1"


def _auth_header() -> dict:
    if not ZEFIX_USER or not ZEFIX_PASS:
        return {}
    token = base64.b64encode(f"{ZEFIX_USER}:{ZEFIX_PASS}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def lookup(company_name: str) -> dict:
    """Suche Firma in ZEFIX und liefere Stammdaten."""
    headers = {
        **_auth_header(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    if not _auth_header():
        return {**_not_found(), "fehler": "ZEFIX-Credentials fehlen"}

    try:
        # ── 1. Suche ──────────────────────────────────────────────────────
        search_resp = requests.post(
            f"{_BASE}/company/search",
            json={
                "name": company_name,
                "maxEntries": 5,
                "offset": 0,
                "activeOnly": True,
            },
            headers=headers,
            timeout=15,
        )
        search_resp.raise_for_status()
        results = search_resp.json()

        if not results:
            return _not_found()

        hit = results[0]
        ehraid = hit.get("ehraid")
        uid = hit.get("uid", "")

        # UID-Format CHE-XXX.XXX.XXX herstellen (API liefert ohne Punkte)
        uid_formatted = ""
        if uid and len(uid) == 12 and uid.startswith("CHE"):
            uid_formatted = f"CHE-{uid[3:6]}.{uid[6:9]}.{uid[9:12]}"
        else:
            uid_formatted = uid

        # ── 2. Detail abrufen für Adresse + Zweck ─────────────────────────
        detail = {}
        if ehraid:
            try:
                d_resp = requests.get(
                    f"{_BASE}/company/ehraid/{ehraid}",
                    headers=headers,
                    timeout=15,
                )
                if d_resp.status_code == 200:
                    detail = d_resp.json()
            except Exception:
                pass

        # Adresse
        addr = detail.get("address", {}) if detail else {}
        strasse = addr.get("street", "")
        hausnr  = addr.get("houseNumber", "") or addr.get("addressLine1", "")
        plz     = addr.get("swissZipCode", "") or addr.get("zipCode", "")
        ort     = addr.get("town", "") or hit.get("legalSeat", "")

        # Zweck / Branche (aus SOGC-Publikationen)
        branche = ""
        pubs = detail.get("sogcPub", []) if detail else []
        if pubs:
            first_pub = pubs[0].get("message", "")
            # Zweck-Block extrahieren
            import re
            zweck_m = re.search(r'Zweck[:\s]+([^.]{20,500})', first_pub, re.IGNORECASE)
            if zweck_m:
                branche = re.sub(r'<[^>]+>', '', zweck_m.group(1)).strip()[:300]

        # Entscheider aus letzter Mutation
        entscheider = ""
        if pubs:
            msg = pubs[0].get("message", "")
            if "mutierend" in msg.lower():
                import re
                m = re.search(r'mutierend[^:]*:\s*(.{20,300})', msg, re.IGNORECASE)
                if m:
                    entscheider = re.sub(r'<[^>]+>', '', m.group(1)).strip()[:300]

        # Kanton aus Publikation
        kanton = ""
        if pubs:
            kanton = pubs[0].get("registryOfCommerceCanton", "") or "CH"

        # Rechtsform
        legal_form = hit.get("legalForm", {}) or {}
        rechtsform = legal_form.get("shortName", {}).get("de", "") or \
                     legal_form.get("name", {}).get("de", "")

        return {
            "zefix_gefunden": True,
            "zefix_url": f"https://www.zefix.ch/de/search/entity/list/firm/{ehraid}",
            "ehraid": ehraid,
            "uid": uid_formatted,
            "name_offiziell": hit.get("name", company_name),
            "rechtsform": rechtsform,
            "strasse": strasse,
            "hausnummer": hausnr,
            "plz": plz,
            "ort": ort,
            "kanton": kanton or "CH",
            "branche": branche or "Keine Angabe (siehe Handelsregister)",
            "entscheider": entscheider,
            "status": hit.get("status", ""),
            "letzte_publikation": hit.get("sogcDate", ""),
        }

    except Exception as exc:
        return {**_not_found(), "fehler": str(exc)}


def _not_found() -> dict:
    return {
        "zefix_gefunden": False,
        "zefix_url": "",
        "ehraid": "", "uid": "", "name_offiziell": "", "rechtsform": "",
        "strasse": "", "hausnummer": "", "plz": "", "ort": "", "kanton": "",
        "branche": "", "entscheider": "", "status": "", "letzte_publikation": "",
    }
