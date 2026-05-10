"""
Konfiguration: liest zuerst aus Streamlit Secrets (Cloud),
dann aus .env (lokal). So funktioniert die App in beiden Umgebungen.
"""
import os
from dotenv import load_dotenv

load_dotenv()

def _get(key: str, default: str = "") -> str:
    """Liest Wert aus st.secrets (Cloud) oder os.environ (lokal)."""
    try:
        import streamlit as st
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)

SERPAPI_KEY      = _get("SERPAPI_KEY")
FIRECRAWL_KEY    = _get("FIRECRAWL_KEY")
PERPLEXITY_KEY   = _get("PERPLEXITY_KEY")
ANTHROPIC_KEY    = _get("ANTHROPIC_KEY")
GOOGLE_SHEETS_ID = _get("GOOGLE_SHEETS_ID")

# ZEFIX (offizielle API – Basic Auth)
ZEFIX_USER = _get("ZEFIX_USER")
ZEFIX_PASS = _get("ZEFIX_PASS")

SMTP_SERVER = _get("SMTP_SERVER", "smtp.office365.com")
SMTP_PORT   = int(_get("SMTP_PORT", "587"))
SMTP_USER   = _get("SMTP_USER")
SMTP_PASS   = _get("SMTP_PASS")
EMAIL_FROM  = _get("EMAIL_FROM")

CLAUDE_MODEL = "claude-sonnet-4-6"

SERPAPI_BASE    = "https://serpapi.com/search"
ZEFIX_BASE      = "https://www.zefix.admin.ch/ZefixPublicREST/api/v1"
PERPLEXITY_BASE = "https://api.perplexity.ai"
FIRECRAWL_BASE  = "https://api.firecrawl.dev/v1"
