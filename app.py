"""
DreierFashion4You – Firmen News & Daten Enrichment
Streamlit Web-App
"""
from datetime import datetime
import os
import pandas as pd
import streamlit as st

from enrichment import output, pipeline, storage
from enrichment.parser import parse_company_input

st.set_page_config(
    page_title="Firmen Enrichment – DreierFashion4You",
    page_icon="🏢",
    layout="wide",
)

# ─── Login (Username + Passwort) ──────────────────────────────────────────────
# Credentials aus st.secrets["auth"] (Streamlit Cloud) oder Umgebungsvariablen (lokal).
def _check_login() -> bool:
    try:
        cfg = st.secrets["auth"]
        correct_user = cfg.get("username", "")
        correct_pw   = cfg.get("password", "")
        display_name = cfg.get("name", correct_user)
    except Exception:
        correct_user = os.getenv("APP_USERNAME", "")
        correct_pw   = os.getenv("APP_PASSWORD", "")
        display_name = os.getenv("APP_DISPLAY_NAME", correct_user)

    if not (correct_user and correct_pw):
        return True

    if st.session_state.get("authenticated"):
        return True

    # ── Brute-Force-Schutz ───────────────────────────────────────────────
    import time
    attempts = st.session_state.get("login_attempts", 0)
    lockout_until = st.session_state.get("login_lockout_until", 0)
    now = time.time()

    if lockout_until > now:
        wait = int(lockout_until - now)
        st.error(f"🔒 Zu viele Fehlversuche. Bitte {wait} Sekunden warten.")
        return False

    st.markdown("## 🔐 Anmeldung erforderlich")
    st.caption("DreierFashion4You – Firmen Enrichment | powered by ROKA Consulting")
    user = st.text_input("Benutzername", key="login_user")
    pw   = st.text_input("Passwort", type="password", key="login_pw")
    if st.button("Anmelden", type="primary"):
        if user.strip() == correct_user and pw == correct_pw:
            st.session_state.authenticated = True
            st.session_state.display_name = display_name
            st.session_state.login_attempts = 0
            st.rerun()
        else:
            attempts += 1
            st.session_state.login_attempts = attempts
            if attempts >= 5:
                # 60 Sekunden Sperre nach 5 Fehlversuchen
                st.session_state.login_lockout_until = now + 60
                st.session_state.login_attempts = 0
                st.error("🔒 Zu viele Fehlversuche – 60 Sekunden gesperrt.")
            else:
                st.error(f"❌ Benutzername oder Passwort falsch ({attempts}/5).")
    return False

if not _check_login():
    st.stop()

# ─── Theme-State (Hell/Dunkel) ────────────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state.theme = "dark"
_THEME = st.session_state.theme  # "dark" | "light"

_PALETTES = {
    "dark": {
        "bg":          "radial-gradient(ellipse at top left, #102036 0%, #0B1220 60%, #060B17 100%)",
        "card":        "#0F1A2E",
        "sidebar":     "linear-gradient(180deg, #0F1A2E 0%, #0B1220 100%)",
        "text":        "#FFFFFF",
        "muted":       "#8FA3BF",
        "border":      "rgba(79, 179, 255, 0.18)",
        "accent":      "#4FB3FF",
        "primary":     "#1279BE",
        "tab_bg":      "rgba(255,255,255,0.04)",
        "tab_active":  "rgba(18, 121, 190, 0.25)",
        "banner":      "linear-gradient(135deg, #102036 0%, #0B1A2E 60%, #060B17 100%)",
        "banner_grid": "rgba(79, 179, 255, 0.06)",
        "pain_bg":     "rgba(18, 121, 190, 0.18)",
        "pain_border": "rgba(79, 179, 255, 0.5)",
        "input_bg":    "#0F1A2E",
        "input_text":  "#E6EDF7",
        "input_border":"rgba(79, 179, 255, 0.25)",
        "btn2_bg":     "#0F1A2E",
        "btn2_text":   "#E6EDF7",
        "btn2_border": "rgba(79, 179, 255, 0.3)",
        "expander_bg": "#0F1A2E",
    },
    "light": {
        "bg":          "linear-gradient(180deg, #F4F8FD 0%, #FFFFFF 100%)",
        "card":        "#FFFFFF",
        "sidebar":     "linear-gradient(180deg, #F0F6FC 0%, #FFFFFF 100%)",
        "text":        "#0B1220",
        "muted":       "#4A5A73",
        "border":      "rgba(18, 121, 190, 0.25)",
        "accent":      "#1279BE",
        "primary":     "#1279BE",
        "tab_bg":      "rgba(18, 121, 190, 0.06)",
        "tab_active":  "rgba(18, 121, 190, 0.15)",
        "banner":      "linear-gradient(135deg, #DCEBFA 0%, #F4F8FD 60%, #FFFFFF 100%)",
        "banner_grid": "rgba(18, 121, 190, 0.08)",
        "pain_bg":     "rgba(18, 121, 190, 0.10)",
        "pain_border": "rgba(18, 121, 190, 0.45)",
        "input_bg":    "#FFFFFF",
        "input_text":  "#0B1220",
        "input_border":"rgba(18, 121, 190, 0.30)",
        "btn2_bg":     "#FFFFFF",
        "btn2_text":   "#0B1220",
        "btn2_border": "rgba(18, 121, 190, 0.40)",
        "expander_bg": "#FFFFFF",
    },
}
P = _PALETTES[_THEME]

# ─── Brand-CSS (Theme-aware) ──────────────────────────────────────────────────
st.markdown(f"""
<style>
  /* Streamlit-Header/Toolbar komplett ausblenden */
  header[data-testid="stHeader"] {{ display: none !important; }}
  div[data-testid="stToolbar"]    {{ display: none !important; }}
  #MainMenu                       {{ visibility: hidden !important; }}
  footer                          {{ visibility: hidden !important; }}
  .stDeployButton                 {{ display: none !important; }}

  .stApp {{ background: {P['bg']} !important; }}
  .main .block-container {{ padding-top: 1.2rem !important; max-width: 1200px; }}

  /* Result-Cards */
  .result-card {{
    border-left: 5px solid {P['primary']};
    padding: 0.8rem 1.2rem;
    margin-bottom: 0.8rem;
    background-color: {P['card']};
    border-radius: 4px;
  }}

  /* Pain-Tags */
  .pain-tag {{
    display: inline-block;
    border-radius: 6px;
    padding: 4px 12px;
    margin: 3px 4px 3px 0;
    font-size: 0.85rem;
    background-color: {P['pain_bg']};
    border: 1px solid {P['pain_border']};
    color: {P['accent']};
    font-weight: 500;
  }}

  h1, h2, h3 {{ color: {P['text']} !important; font-weight: 600 !important; }}
  h1 .accent, h2 .accent, .accent {{ color: {P['accent']} !important; }}

  .stMarkdown, .stMarkdown p, label, .stCaption,
  div[data-testid="stMarkdownContainer"] p {{ color: {P['text']}; }}

  /* Buttons - Primary */
  .stButton > button[kind="primary"] {{
    background-color: {P['primary']} !important;
    border-color: {P['primary']} !important;
    color: #FFFFFF !important;
  }}
  .stButton > button[kind="primary"]:hover {{
    background-color: {P['accent']} !important;
    border-color: {P['accent']} !important;
  }}
  /* Buttons - Secondary (Default) */
  .stButton > button:not([kind="primary"]),
  .stDownloadButton > button {{
    background-color: {P['btn2_bg']} !important;
    color: {P['btn2_text']} !important;
    border: 1px solid {P['btn2_border']} !important;
  }}
  .stButton > button:not([kind="primary"]):hover,
  .stDownloadButton > button:hover {{
    border-color: {P['accent']} !important;
    color: {P['accent']} !important;
  }}

  /* Inputs (Text/Number/TextArea/Selectbox) */
  .stTextInput input, .stNumberInput input, .stTextArea textarea,
  .stTextInput > div > div > input,
  .stNumberInput > div > div > input,
  div[data-baseweb="input"] input,
  div[data-baseweb="textarea"] textarea,
  div[data-baseweb="select"] > div {{
    background-color: {P['input_bg']} !important;
    color: {P['input_text']} !important;
    border-color: {P['input_border']} !important;
  }}
  .stTextInput label, .stNumberInput label, .stTextArea label,
  .stSelectbox label, .stMultiSelect label, .stCheckbox label,
  .stRadio label, .stFileUploader label {{
    color: {P['text']} !important;
  }}

  /* Expander */
  div[data-testid="stExpander"] {{
    background-color: {P['expander_bg']} !important;
    border: 1px solid {P['border']} !important;
    border-radius: 6px;
  }}
  div[data-testid="stExpander"] summary,
  div[data-testid="stExpander"] details > summary p {{
    color: {P['text']} !important;
  }}

  /* Metric */
  div[data-testid="stMetricValue"] {{ color: {P['text']} !important; }}
  div[data-testid="stMetricLabel"] {{ color: {P['muted']} !important; }}

  /* DataFrame / DataEditor */
  div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {{
    background-color: {P['card']} !important;
    border-radius: 6px;
  }}

  /* Alerts (info/success/warning/error) — Texte dunkler halten in Light */
  div[data-testid="stAlert"] {{ color: {P['text']} !important; }}

  /* File-Uploader */
  div[data-testid="stFileUploader"] section {{
    background-color: {P['input_bg']} !important;
    border: 1px dashed {P['input_border']} !important;
    color: {P['text']} !important;
  }}

  /* Tabs */
  .stTabs [data-baseweb="tab-list"] {{ gap: 4px; }}
  .stTabs [data-baseweb="tab"] {{
    background-color: {P['tab_bg']} !important;
    color: {P['text']} !important;
    border-radius: 6px 6px 0 0;
  }}
  .stTabs [aria-selected="true"] {{
    background-color: {P['tab_active']} !important; color: {P['accent']} !important;
  }}

  /* Sidebar */
  section[data-testid="stSidebar"] {{
    background: {P['sidebar']} !important;
    border-right: 1px solid {P['border']};
  }}

  /* ─── Brand-Banner im Eventkalender-Stil ─── */
  .roka-brandbar {{
    display: flex; align-items: center; gap: 18px;
    padding: 18px 22px;
    background: {P['banner']};
    background-image:
      linear-gradient(0deg, transparent 24%, {P['banner_grid']} 25%, {P['banner_grid']} 26%, transparent 27%, transparent 74%, {P['banner_grid']} 75%, {P['banner_grid']} 76%, transparent 77%),
      linear-gradient(90deg, transparent 24%, {P['banner_grid']} 25%, {P['banner_grid']} 26%, transparent 27%, transparent 74%, {P['banner_grid']} 75%, {P['banner_grid']} 76%, transparent 77%),
      {P['banner']};
    background-size: 40px 40px, 40px 40px, 100% 100%;
    border: 1px solid {P['border']};
    border-radius: 6px;
    margin-bottom: 22px;
  }}
  .roka-brandbar .roka-logo,
  .roka-brandbar .brand-logo {{ height: 56px; width: auto; object-fit: contain; flex-shrink: 0; }}
  .roka-brandbar .roka-brand-text {{ display: flex; flex-direction: column; gap: 4px; }}
  .roka-brandbar .roka-brand-title {{
    font-size: 1.45rem; font-weight: 700; color: {P['text']};
    letter-spacing: 0.2px; line-height: 1.15;
  }}
  .roka-brandbar .roka-brand-title .accent {{ color: {P['accent']}; }}
  .roka-brandbar .roka-brand-sub {{
    font-size: 0.78rem; color: {P['accent']};
    letter-spacing: 2.5px; text-transform: uppercase; font-weight: 600;
  }}

  /* Footer */
  .roka-footer {{
    text-align: center; color: {P['muted']}; font-size: 0.8rem;
    padding: 1.5rem 1rem; border-top: 1px solid {P['border']}; margin-top: 3rem;
  }}
  .roka-footer a {{ color: {P['accent']} !important; }}
</style>
""", unsafe_allow_html=True)

# ─── Session state ────────────────────────────────────────────────────────────
if "results"             not in st.session_state: st.session_state.results = []
if "running"             not in st.session_state: st.session_state.running = False
if "log"                 not in st.session_state: st.session_state.log = []
if "excel_cache"         not in st.session_state: st.session_state.excel_cache = None
if "show_inline_results" not in st.session_state: st.session_state.show_inline_results = False

# ─── Header mit Kunden-Logo ───────────────────────────────────────────────────
import base64
from pathlib import Path

_assets = Path(__file__).parent / "assets"
# Logo: jedes File in assets/ das mit "dreier" beginnt (case-insensitive),
# Reihenfolge nach Endung: png > svg > jpg/jpeg > webp.
_MIME = {".png": "image/png", ".svg": "image/svg+xml",
         ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
_logo_html: str = ""
if _assets.exists():
    _candidates = sorted(
        (f for f in _assets.iterdir()
         if f.is_file()
         and f.name.lower().startswith("dreier")
         and f.suffix.lower() in _MIME),
        key=lambda f: list(_MIME).index(f.suffix.lower()),
    )
    if _candidates:
        fp = _candidates[0]
        b64 = base64.b64encode(fp.read_bytes()).decode()
        _logo_html = f"<img src='data:{_MIME[fp.suffix.lower()]};base64,{b64}' alt='Dreier' class='brand-logo'/>"

if not _logo_html:
    # Inline-SVG-Fallback: "dreier" Wortmarke in Teal (Dreier-Brand-Farbe)
    _logo_html = """
    <svg viewBox='0 0 200 70' class='brand-logo' xmlns='http://www.w3.org/2000/svg' aria-label='Dreier'>
      <g fill='none' stroke='#D9434E' stroke-width='2'>
        <circle cx='42'  cy='38' r='17'/>
        <circle cx='72'  cy='38' r='17'/>
        <circle cx='102' cy='38' r='17'/>
      </g>
      <text x='100' y='52' text-anchor='middle'
            font-family='Helvetica, Arial, sans-serif' font-weight='800'
            font-size='42' fill='#2DAEA8' letter-spacing='-1'>dreier</text>
    </svg>
    """

_brandbar_html = (
    f"<div class='roka-brandbar'>{_logo_html}"
    f"<div class='roka-brand-text'>"
    f"<div class='roka-brand-title'>DreierFashion4You &middot; <span class='accent'>Firmen Enrichment</span></div>"
    f"<div class='roka-brand-sub'>Textillogistik &middot; Vertriebsvorbereitung &middot; powered by ROKA Consulting</div>"
    f"</div></div>"
)
st.markdown(_brandbar_html, unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    if st.session_state.get("authenticated"):
        st.caption(f"👤 {st.session_state.get('display_name', '')}")
        if st.button("Abmelden", key="logout_btn"):
            for k in ("authenticated", "display_name", "login_user", "login_pw"):
                st.session_state.pop(k, None)
            st.rerun()

    # ── Hell/Dunkel-Toggle ───────────────────────────────────────────────
    _theme_label = "☀️ Hell" if _THEME == "dark" else "🌙 Dunkel"
    if st.button(f"{_theme_label}-Modus", key="theme_toggle", use_container_width=True):
        st.session_state.theme = "light" if _THEME == "dark" else "dark"
        st.rerun()
    st.divider()

    # ── Recherche-Einstellungen ──────────────────────────────────────────
    st.markdown("### 🔎 Recherche")
    max_age_months = st.number_input(
        "Max. Alter Informationen (Monate)",
        min_value=1, max_value=24, value=st.session_state.get("max_age_months", 6),
        step=1, key="max_age_months",
        help="News, Bau- und Verbandstreffer älter als dieser Wert werden ignoriert.",
    )

    with st.expander("💼 Jobsuche-Einstellungen", expanded=False):
        job_enabled = st.checkbox(
            "Jobsuche aktiv",
            value=st.session_state.get("job_enabled", True),
            key="job_enabled",
            help="Wenn deaktiviert, werden keine Stellenanzeigen gesucht.",
        )
        job_max_age = st.number_input(
            "Max. Alter Stellenanzeigen (Monate)",
            min_value=1, max_value=12,
            value=st.session_state.get("job_max_age", 3),
            step=1, key="job_max_age",
            disabled=not job_enabled,
        )
        job_keywords_str = st.text_input(
            "Suchbegriffe (kommagetrennt)",
            value=st.session_state.get(
                "job_keywords_str",
                "Logistik, Supply Chain, Operations, CEO, CFO, COO, CIO",
            ),
            key="job_keywords_str",
            disabled=not job_enabled,
            help="Treffer müssen mind. einen dieser Begriffe enthalten.",
        )
        st.caption("🛡 Quellen-Filter: nur Treffer, deren Firmenname im Title/Link/Snippet vorkommt, werden übernommen.")

    job_settings = {
        "enabled": st.session_state.get("job_enabled", True),
        "keywords": [k.strip() for k in st.session_state.get(
            "job_keywords_str",
            "Logistik, Supply Chain, Operations, CEO, CFO, COO, CIO",
        ).split(",") if k.strip()],
        "max_age_months": int(st.session_state.get("job_max_age", 3)),
    }

    st.divider()

    # API-Keys nur sichtbar wenn ?admin=1 in URL (für Admin/Support)
    import config
    _is_admin = st.query_params.get("admin") == "1"
    if _is_admin:
        st.markdown("### ⚙️ Admin")
        with st.expander("🔧 API-Status", expanded=False):
            for label, val in [
                ("SerpAPI",    config.SERPAPI_KEY),
                ("Firecrawl",  config.FIRECRAWL_KEY),
                ("Perplexity", config.PERPLEXITY_KEY),
                ("Anthropic",  config.ANTHROPIC_KEY),
                ("ZEFIX",      config.ZEFIX_USER),
            ]:
                status = "✅" if val else "❌ fehlt"
                st.write(f"{status} {label}")

    # ── Notfall-Download immer verfügbar ─────────────────────────────────
    _state_partial = storage.load_batch()
    if _state_partial and _state_partial.get("results"):
        st.markdown("**🆘 Notfall-Download**")
        st.caption(f"{len(_state_partial['results'])} Firmen zwischengespeichert")
        try:
            _partial_xlsx = output.results_to_excel(
                [r for r in _state_partial["results"] if "_error" not in r] or _state_partial["results"],
                None,
            )
            st.download_button(
                "📥 Zwischenstand als Excel",
                data=_partial_xlsx,
                file_name=f"Enrichment_Zwischenstand_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="emergency_dl",
            )
        except Exception:
            pass

# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Firmen eingeben",
    "📊 Ergebnisse",
    "📤 Export",
    "⚙️ Bedarfsfelder",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 – EINGABE
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Firmen auswählen")

    mode = st.radio(
        "Eingabemodus",
        options=["✍️ Namen eingeben", "📂 Excel hochladen"],
        horizontal=True,
    )

    company_list: list[str] = []

    # ── Manuelle Eingabe ──────────────────────────────────────────────────────
    if mode == "✍️ Namen eingeben":
        raw_text = st.text_area(
            "Firmen (eine pro Zeile oder kommagetrennt)",
            placeholder="Dreier AG\nMigros\nmanor.ch\nKyburz Bettenware AG",
            height=160,
        )
        if raw_text.strip():
            company_list = [
                c.strip()
                for line in raw_text.splitlines()
                for c in line.split(",")
                if c.strip()
            ]

    # ── Excel-Upload ──────────────────────────────────────────────────────────
    else:
        uploaded = st.file_uploader("Excel-Datei hochladen", type=["xlsx"], key="input_xlsx")
        if uploaded:
            df_input = pd.read_excel(uploaded)
            st.dataframe(df_input.head(10), use_container_width=True)

            col_candidates = [
                c for c in df_input.columns
                if any(k in c.lower() for k in ["firma", "company", "unternehmen", "name"])
            ]
            col_name = st.selectbox(
                "Spalte mit Firmennamen",
                col_candidates if col_candidates else df_input.columns.tolist(),
            )
            company_list = df_input[col_name].dropna().astype(str).tolist()
            st.success(f"{len(company_list)} Firmen geladen.")

    # ── Auswahl & Start ───────────────────────────────────────────────────────
    if company_list:
        st.divider()

        selected = st.multiselect(
            "Auswahl einschränken (leer = alle verarbeiten)",
            options=company_list,
        )
        final_list = selected if selected else company_list

        st.info(
            f"**{len(final_list)} Firma(en) werden verarbeitet.**  \n"
            f"Geschätzte Dauer: ca. {len(final_list) * 45}–{len(final_list) * 90} Sek."
        )

        _n = len(final_list)
        _label = "Firma" if _n == 1 else "Firmen"
        start_btn = st.button(
            f"🚀 Enrichment starten ({_n} {_label})",
            type="primary",
            disabled=st.session_state.running,
        )

        # ── Resume-Banner falls unvollendeter Batch existiert ────────────────
        if storage.has_unfinished_batch() and not start_btn:
            summary = storage.batch_summary(storage.load_batch())
            with st.container(border=True):
                st.warning(
                    f"⏸️ **Unvollendeter Lauf gefunden** – "
                    f"{summary['done']}/{summary['total']} Firmen verarbeitet "
                    f"({summary['pending']} ausstehend), gestartet {summary['started_at'][:16]}."
                )
                cc1, cc2, cc3 = st.columns(3)
                if cc1.button("▶️ Fortsetzen", type="primary", key="resume_btn"):
                    state = storage.load_batch()
                    st.session_state.results = state.get("results", [])
                    st.session_state.log = state.get("log", [])
                    st.session_state.resume = True
                    st.session_state.resume_pending = state.get("pending", [])
                    st.rerun()
                if cc2.button("📥 Bisherige Ergebnisse downloaden", key="dl_partial"):
                    state = storage.load_batch()
                    partial_xlsx = output.results_to_excel(
                        [r for r in state.get("results", []) if "_error" not in r] or state.get("results", []),
                        None,
                    )
                    st.download_button(
                        "Excel speichern",
                        data=partial_xlsx,
                        file_name=f"Enrichment_partial_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_partial_btn",
                    )
                if cc3.button("🗑️ Verwerfen & neu starten", key="discard_btn"):
                    storage.clear_batch()
                    st.session_state.results = []
                    st.session_state.log = []
                    st.rerun()

        # ── Eigentlicher Enrichment-Lauf ─────────────────────────────────────
        resume_mode = st.session_state.pop("resume", False)

        if start_btn or resume_mode:
            import traceback
            st.session_state.running = True
            st.session_state.show_inline_results = False

            if resume_mode:
                state = storage.load_batch()
                to_process = list(state.get("pending", []))
                st.session_state.results = state.get("results", [])
                st.session_state.log = state.get("log", [])
                st.info(f"▶️ Fortsetzung – {len(to_process)} Firmen verbleibend")
            else:
                state = storage.init_batch(final_list)
                to_process = list(final_list)
                st.session_state.results = []
                st.session_state.log = []
                st.session_state.excel_cache = None

            progress_bar = st.progress(0, text="Initialisiere …")
            status_text = st.empty()
            live_results = st.empty()
            total_initial = state["total"]
            already_done = total_initial - len(to_process)

            for offset, raw in enumerate(to_process):
                idx = already_done + offset
                parsed_name = parse_company_input(raw)["companyName"]
                status_text.markdown(
                    f"**[{idx+1}/{total_initial}]** Verarbeite: **{parsed_name}** … "
                    f"_(automatisch gespeichert nach jeder Firma)_"
                )

                def _cb(step, pct, _idx=idx, _total=total_initial):
                    overall = min(_idx / _total + pct / 100 / _total, 0.99)
                    progress_bar.progress(overall, text=f"[{_idx+1}/{_total}] {step}")

                try:
                    result = pipeline.run(
                        raw, progress_callback=_cb,
                        max_age_months=int(max_age_months),
                        job_settings=job_settings,
                    )
                    log_line = f"✅ {parsed_name} – {result.get('totalCount', 0)} Treffer"
                except Exception as exc:
                    tb = traceback.format_exc()
                    log_line = f"❌ {parsed_name} – Fehler: {exc}"
                    result = {
                        "company": parsed_name,
                        "summary": f"Fehler bei Verarbeitung: {exc}",
                        "pain_point_1": "–", "pain_point_2": "–", "pain_point_3": "–",
                        "investitionssignale": [], "verband": "–", "sitz": "–",
                        "branche": "–", "mitarbeiter": "–", "totalCount": 0,
                        "news": [], "construction": [], "jobs": [],
                        "_error": str(exc),
                        "_error_traceback": tb,
                        "_meta": {"input": raw, "companyName": parsed_name},
                    }

                # SOFORT speichern - bei Crash gehen vorige Ergebnisse nicht verloren
                state = storage.save_result(state, raw, result, log_line)
                st.session_state.results.append(result)
                st.session_state.log.append(log_line)

                # Excel inkrementell aktualisieren - jederzeit downloadbar
                try:
                    st.session_state.excel_cache = output.results_to_excel(
                        [r for r in st.session_state.results if "_error" not in r] or st.session_state.results,
                        None,
                    )
                except Exception:
                    pass

                # Live-Anzeige der bisherigen Treffer
                with live_results.container():
                    ok = sum(1 for r in st.session_state.results if "_error" not in r)
                    err = len(st.session_state.results) - ok
                    st.caption(f"✅ {ok} fertig · ❌ {err} Fehler · ⏳ {len(to_process)-offset-1} ausstehend")

            storage.mark_finished(state)
            progress_bar.progress(1.0, text="Fertig.")
            ok_count = sum(1 for r in st.session_state.results if "_error" not in r)
            err_count = total_initial - ok_count
            if err_count == 0:
                status_text.success(f"✅ {ok_count}/{total_initial} Firmen erfolgreich angereichert.")
            else:
                status_text.warning(f"⚠️ {ok_count}/{total_initial} erfolgreich – {err_count} Fehler (siehe Protokoll unten)")

            st.session_state.running = False
            st.session_state.show_inline_results = True

            # Finale Excel (Merge mit bestehender Datei passiert nur via Tab 3 Upload)
            st.session_state.excel_cache = output.results_to_excel(
                [r for r in st.session_state.results if "_error" not in r] or st.session_state.results,
                None,
            )

        # ── Inline-Ergebnisse direkt in Tab 1 ────────────────────────────────
        if st.session_state.get("show_inline_results") and st.session_state.results:
            st.divider()
            st.markdown("### 📊 Ergebnisse")
            for r in st.session_state.results:
                name_r = r.get("company", "")
                is_err = "_error" in r
                icon = "❌" if is_err else "✅"
                with st.expander(f"{icon} {name_r}", expanded=not is_err):
                    if is_err:
                        st.error(r.get("summary", ""))
                    else:
                        col1, col2 = st.columns(2)
                        col1.markdown(f"**Branche:** {r.get('branche','–')}")
                        col1.markdown(f"**Sitz:** {r.get('sitz','–')}")
                        col2.markdown(f"**Mitarbeiter:** {r.get('mitarbeiter','–')}")
                        col2.markdown(f"**Verband:** {r.get('verband','–')}")
                        st.markdown(f"**Summary:** {r.get('summary','')}")
                        pp = [r.get(k,'') for k in ['pain_point_1','pain_point_2','pain_point_3'] if r.get(k) and r.get(k) != '–']
                        if pp:
                            st.markdown("**⚡ Pain Points:**")
                            for p in pp:
                                st.markdown(f'<span class="pain-tag">⚡ {p}</span>', unsafe_allow_html=True)
                        sigs = r.get("investitionssignale", [])
                        if sigs:
                            st.markdown("**📈 Signale:** " + " · ".join(sigs))

            # Protokoll
            if st.session_state.log:
                with st.expander("📋 Protokoll (Details & Fehler)"):
                    for line in st.session_state.log:
                        st.text(line)

            # Download-Button direkt hier
            if st.session_state.excel_cache:
                st.download_button(
                    label="📥 Excel herunterladen",
                    data=st.session_state.excel_cache,
                    file_name=f"Enrichment_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                )

    else:
        st.markdown("")
        with st.expander("💡 So funktioniert es", expanded=True):
            st.markdown("""
**Schritt 1** – Firmennamen eingeben oder Excel hochladen
**Schritt 2** – Enrichment starten (dauert ca. 1 Min. pro Firma)
**Schritt 3** – Ergebnisse ansehen und als Excel herunterladen (Tab **📤 Export**)

**Was die App recherchiert:**
- 📰 Aktuelle News & Pressemitteilungen (SerpAPI)
- 🏗️ Bau- und Expansionspläne
- 💼 Offene Stellen (Logistik / Supply Chain) – optional, eigene Stichwörter & Zeitrahmen
- 🏛️ Verbandsmitgliedschaften
- 🏢 Stammdaten (ZEFIX Handelsregister via Firecrawl)
- 🤖 KI-Analyse: 3 belegte Pain Points + Miller-Heiman Vertriebsbriefing (Claude)

**🎯 Bedarfsfelder-Matrix (Tab ⚙️ Bedarfsfelder):**
Du definierst dort selbst, welche **Branchen** und **Detail-Dienstleistungen** Dreier anbietet.
Die KI erkennt pro Firma 1–5 priorisierte Bedarfsfelder daraus –
**immer bezogen auf das Kerngeschäft der Firma** (was sie produziert/verkauft/transportiert),
**niemals auf Personalbedarf, Recruiting oder offene Stellen**.
Fehlt ein passendes Detail in der Matrix, beschreibt die KI das Feld in eigenen Worten (mit `*` markiert).

**🛡 Zeitfilter & Quellen-Sicherheit:**
- In der Sidebar legst du fest, wie alt Informationen maximal sein dürfen (Default 6 Monate).
- Jobsuche kann separat ein-/ausgeschaltet und zeitlich begrenzt werden.
- Quellen-Validierung: nur Treffer, deren Firmenname tatsächlich in Title/Link/Snippet vorkommt, werden übernommen
  (verhindert Falschzuordnungen wie "Planzer-Stelle bei Bächli Bergsport").
""")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 – ERGEBNISSE
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    if not st.session_state.results:
        st.info("Noch keine Ergebnisse. Bitte zuerst Firmen anreichern (Tab **📋 Firmen eingeben**).")
    else:
        st.subheader(f"{len(st.session_state.results)} Firma(en) angereichert")

        search_q = st.text_input("🔍 Filtern", placeholder="Firmenname, Pain Point …")

        for r in st.session_state.results:
            name    = r.get("company", "")
            summary = r.get("summary", "")
            sitz    = r.get("sitz", "")
            meta    = r.get("_meta", {})

            searchable = (name + summary + r.get("pain_point_1","") +
                          r.get("pain_point_2","") + r.get("pain_point_3","")).lower()
            if search_q and search_q.lower() not in searchable:
                continue

            with st.expander(f"🏢 {name}  —  {sitz}", expanded=False):
                # ── Stammdaten ────────────────────────────────────────────
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Branche",     r.get("branche", "–"))
                c2.metric("Mitarbeiter", r.get("mitarbeiter", "–"))
                c3.metric("Umsatz",      r.get("umsatz", "–"))
                c4.metric("ZEFIX",       "✅" if r.get("zefix_gefunden") or (r.get("_meta") or {}).get("zefix_gefunden") else "❌")

                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown(f"**UID:** {r.get('uid','–')}")
                    st.markdown(f"**Rechtsform:** {r.get('rechtsform','–')}")
                with col_r:
                    st.markdown(f"**Verband:** {r.get('verband','–')}")
                    zurl = r.get("zefix_url","") or (r.get("_meta") or {}).get("zefix_url","")
                    if zurl:
                        st.markdown(f"**ZEFIX:** [Eintrag öffnen]({zurl})")

                st.markdown(f"**Summary:** {summary}")
                st.divider()

                # ── Pain Points ───────────────────────────────────────────
                st.markdown("**⚡ Pain Points (belegte Fakten):**")
                for key in ["pain_point_1", "pain_point_2", "pain_point_3"]:
                    val = r.get(key, "")
                    if val and val not in ("–", "Nicht bekannt", "Keine weiteren Infos verfügbar"):
                        st.markdown(
                            f'<span class="pain-tag">⚡ {val}</span>',
                            unsafe_allow_html=True,
                        )

                signals = r.get("investitionssignale", [])
                if signals:
                    st.markdown("**📈 Investitionssignale:**")
                    for s in signals:
                        st.markdown(f"- {s}")

                # ── Bedarfsfelder (priorisiert) ──────────────────────────
                bedarfe = sorted(r.get("bedarfsfelder", []), key=lambda x: x.get("prio", 99))
                if bedarfe:
                    st.markdown("**🎯 Erkannte Bedarfsfelder:**")
                    for bf in bedarfe:
                        marker = " *(Freitext)*" if bf.get("quelle") == "freitext" else ""
                        st.markdown(
                            f"- **{bf.get('prio', '?')}.** "
                            f"`{bf.get('branche', '')}` / `{bf.get('detail', '')}`{marker}  \n"
                            f"  └ _{bf.get('begruendung', '')}_"
                        )

                # ── Miller-Heiman Briefing ────────────────────────────────
                mh = r.get("miller_heiman", {})
                if mh:
                    st.divider()
                    st.markdown("### 🎯 Miller-Heiman Vertriebsbriefing")

                    bi = mh.get("buying_influences", {})
                    if bi:
                        st.markdown("**👥 Buying Influences:**")
                        roles = [
                            ("💰 Economic Buyer", bi.get("economic_buyer","–")),
                            ("🔧 User Buyer",     bi.get("user_buyer","–")),
                            ("🖥️ Technical Buyer",bi.get("technical_buyer","–")),
                            ("🤝 Coach",          bi.get("coach","–")),
                        ]
                        bc1, bc2 = st.columns(2)
                        for i, (label, val) in enumerate(roles):
                            (bc1 if i % 2 == 0 else bc2).markdown(f"**{label}:** {val}")

                    st.markdown(f"**📍 IST-Situation:** {mh.get('current_situation','–')}")
                    st.markdown(f"**🎯 Gewünschtes Ergebnis:** {mh.get('desired_outcome','–')}")
                    st.markdown(f"**✅ Solution Fit:** {mh.get('solution_fit','–')}")

                    entry = mh.get("recommended_entry","")
                    if entry:
                        st.info(f"**💬 Empfohlener Gesprächseinstieg:** {entry}")

                    tps = mh.get("talking_points", [])
                    if tps:
                        st.markdown("**🗣️ Talking Points:**")
                        for tp in tps:
                            st.markdown(f"- {tp}")

                    flags = mh.get("red_flags", [])
                    if flags:
                        st.markdown("**🚩 Red Flags / Einwände:**")
                        for f in flags:
                            st.markdown(f"- ⚠️ {f}")

                # ── News & Jobs ───────────────────────────────────────────
                news = r.get("news", [])[:5]
                if news:
                    st.divider()
                    st.markdown("**📰 Top News:**")
                    for n in news:
                        title   = n.get("title", "")
                        link    = n.get("link", "")
                        snippet = n.get("snippet", "")[:120]
                        if link:
                            st.markdown(f"- [{title}]({link})  \n  *{snippet}*")
                        else:
                            st.markdown(f"- {title}")

                jobs = r.get("jobs", [])[:5]
                if jobs:
                    st.markdown("**💼 Offene Stellen (SC/Logistik/Führung):**")
                    for j in jobs:
                        title = j.get("title", "")
                        link  = j.get("link", "")
                        if link:
                            st.markdown(f"- [{title}]({link})")
                        else:
                            st.markdown(f"- {title}")

        if st.session_state.log:
            with st.expander("📋 Protokoll"):
                for line in st.session_state.log:
                    st.text(line)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 – EXPORT
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    if not st.session_state.results:
        st.info("Noch keine Ergebnisse zum Exportieren.")
    else:
        st.subheader("Export")

        # Optional: bestehende Excel ergänzen
        with st.expander("📎 Bestehende Excel ergänzen (optional)", expanded=False):
            existing_file_export = st.file_uploader(
                "Bestehende Excel-Datei hochladen",
                type=["xlsx"],
                key="existing_xlsx_export",
                help="Falls Sie bereits eine Excel haben, die ergänzt werden soll – hier hochladen."
            )
        existing_bytes = existing_file_export.getvalue() if existing_file_export else None

        # Excel mit/ohne bestehende Datei neu berechnen
        st.session_state.excel_cache = output.results_to_excel(
            st.session_state.results, existing_bytes
        )

        st.markdown("**📥 Excel herunterladen**")
        st.download_button(
            label="Excel herunterladen",
            data=st.session_state.excel_cache,
            file_name=f"Enrichment_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
        st.caption("Excel-Datei kann direkt in Teams/SharePoint hochgeladen oder weitergeleitet werden. "
                   "E-Mail-Versand ist aktuell deaktiviert.")

        st.divider()
        st.markdown("**Vorschau**")
        preview = []
        for r in st.session_state.results:
            preview.append({
                "Firma":        r.get("company", ""),
                "Sitz":         r.get("sitz", ""),
                "Branche":      r.get("branche", ""),
                "Pain Point 1": r.get("pain_point_1", ""),
                "Pain Point 2": r.get("pain_point_2", ""),
                "Pain Point 3": r.get("pain_point_3", ""),
                "Summary":      r.get("summary", "")[:80] + "…",
            })
        st.dataframe(pd.DataFrame(preview), use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 – BEDARFSFELDER-MATRIX
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    from enrichment import branches_store

    st.subheader("Bedarfsfelder-Matrix")
    st.caption(
        "Definiert, in welcher Branche und welchem Detail-Bereich das Enrichment "
        "Bedarf erkennen soll. Findet die KI keinen Detail-Treffer aus dieser Matrix, "
        "beschreibt sie das Bedarfsfeld in eigenen Worten (mit `*` markiert)."
    )

    if "matrix_cache" not in st.session_state:
        st.session_state.matrix_cache = branches_store.load_matrix()

    rows = branches_store.matrix_to_dataframe_rows(st.session_state.matrix_cache)
    df = pd.DataFrame(rows or [{"Branche": "", "Detail": ""}])

    edited = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key="matrix_editor",
        column_config={
            "Branche": st.column_config.TextColumn("Branche / Cluster", required=True),
            "Detail":  st.column_config.TextColumn("Detail / Dienstleistung"),
        },
        hide_index=True,
    )

    col_a, col_b, col_c = st.columns([1, 1, 2])
    with col_a:
        save_clicked = st.button("💾 Speichern", type="primary", key="matrix_save")
    with col_b:
        reset_clicked = st.button("↺ Default wiederherstellen", key="matrix_reset")
    with col_c:
        st.caption(f"Stand: {st.session_state.matrix_cache.get('updated_at', '—')}")

    if save_clicked:
        new_matrix = branches_store.dataframe_rows_to_matrix(edited.to_dict("records"))
        try:
            branches_store.save_matrix_local(new_matrix)
            sha = branches_store.commit_matrix_to_github(new_matrix)
            st.session_state.matrix_cache = new_matrix
            st.success(f"✅ Matrix gespeichert + auf GitHub committet ({sha[:7]}). "
                       f"Streamlit redeployed automatisch in ~30s.")
        except Exception as exc:
            # Lokal hat geklappt, GitHub evtl. nicht (z.B. lokal ohne Token)
            st.warning(f"⚠️ Lokal gespeichert, GitHub-Commit fehlgeschlagen: {exc}")
            st.session_state.matrix_cache = new_matrix

    if reset_clicked:
        default = {
            "version": 1,
            "branches": {
                "Lagerlogistik": ["Wareneingang", "Lagerhaltung", "Kommissionierung",
                                  "Bestandsführung", "Baustofflagerung"],
                "Distribution & Versand": ["Versand", "Distribution", "Stückgut", "Systemverkehr"],
                "Spezialtransporte": ["Konventionelle Strassentransporte", "Baustofftransport",
                                      "Lebensmittellogistik", "Pharmatransport", "Textillogistik",
                                      "Kombinierter Verkehr", "Internationale Transporte"],
                "Zusatzservices": ["Retourenlogistik", "Entsorgung",
                                   "Verzollung Import/Export", "Aufbereitung von Textilien"],
            },
        }
        st.session_state.matrix_cache = default
        st.rerun()

    with st.expander("ℹ️ So funktioniert die Matrix"):
        st.markdown(
            "- **Branche** = Cluster, **Detail** = konkrete Dienstleistung\n"
            "- Mehrere Details pro Branche → mehrere Zeilen mit gleicher Branche\n"
            "- LLM wählt 1–5 Bedarfsfelder pro Firma, priorisiert (1 = stärkster Bedarf)\n"
            "- `*` markiert Freitext-Treffer (LLM hat eigenes Detail erfunden)\n"
            "- Änderungen werden in `config/branches.json` auf GitHub committet → "
            "Streamlit Cloud redeployed automatisch."
        )

# ─── ROKA-Footer ──────────────────────────────────────────────────────────────
st.markdown(
    "<div class='roka-footer'>"
    "ROKA Consulting · KI-Logistik-Pionier der Schweiz · "
    "<a href='https://rokaconsulting.ch' style='color:#1279BE;text-decoration:none;'>rokaconsulting.ch</a> · "
    "roland.kalt@rokaconsulting.ch"
    "</div>",
    unsafe_allow_html=True,
)
