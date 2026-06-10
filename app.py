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

# ─── ROKA Brand CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* ROKA Brand-Farben: #1279BE (primary), #0E5E96 (dark), #303030 (text) */
  .result-card {
    border-left: 5px solid #1279BE;
    padding: 0.8rem 1.2rem;
    margin-bottom: 0.8rem;
    background-color: #F8F8F8;
  }
  .pain-tag {
    display: inline-block;
    border-radius: 6px;
    padding: 4px 12px;
    margin: 3px 4px 3px 0;
    font-size: 0.85rem;
    background-color: rgba(18, 121, 190, 0.15);
    border: 1px solid rgba(18, 121, 190, 0.4);
    color: #0E5E96;
    font-weight: 500;
  }
  /* Header-Style */
  h1, h2, h3 {
    color: #1279BE !important;
  }
  h1 { font-weight: 600 !important; }
  /* Buttons abgerundet */
  .stButton > button[kind="primary"] {
    background-color: #1279BE;
    border-color: #1279BE;
  }
  .stButton > button[kind="primary"]:hover {
    background-color: #0E5E96;
    border-color: #0E5E96;
  }
  /* ROKA-Footer */
  .roka-footer {
    text-align: center;
    color: #757575;
    font-size: 0.8rem;
    padding: 1rem;
    border-top: 1px solid #C5C5C5;
    margin-top: 2rem;
  }
</style>
""", unsafe_allow_html=True)

# ─── Session state ────────────────────────────────────────────────────────────
if "results"             not in st.session_state: st.session_state.results = []
if "running"             not in st.session_state: st.session_state.running = False
if "log"                 not in st.session_state: st.session_state.log = []
if "excel_cache"         not in st.session_state: st.session_state.excel_cache = None
if "show_inline_results" not in st.session_state: st.session_state.show_inline_results = False

# ─── Header ───────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.markdown(
        "<div style='font-size:2.5rem;line-height:1;color:#1279BE;'>🏢</div>",
        unsafe_allow_html=True,
    )
with col_title:
    st.markdown(
        "<h1 style='margin:0;color:#1279BE;'>Firmen News & Daten Enrichment</h1>"
        "<div style='color:#757575;font-size:0.95rem;margin-top:4px;'>"
        "DreierFashion4You · Vertriebsvorbereitung · powered by "
        "<a href='https://rokaconsulting.ch' style='color:#1279BE;text-decoration:none;'>ROKA Consulting</a>"
        "</div>",
        unsafe_allow_html=True,
    )
st.divider()

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    if st.session_state.get("authenticated"):
        st.caption(f"👤 {st.session_state.get('display_name', '')}")
        if st.button("Abmelden", key="logout_btn"):
            for k in ("authenticated", "display_name", "login_user", "login_pw"):
                st.session_state.pop(k, None)
            st.rerun()
        st.divider()
    st.markdown("### ⚙️ Einstellungen")

    # API-Keys nur sichtbar wenn ?admin=1 in URL (für Admin/Support)
    import config
    _is_admin = st.query_params.get("admin") == "1"
    if _is_admin:
        with st.expander("🔧 API-Status (Admin)", expanded=False):
            for label, val in [
                ("SerpAPI",    config.SERPAPI_KEY),
                ("Firecrawl",  config.FIRECRAWL_KEY),
                ("Perplexity", config.PERPLEXITY_KEY),
                ("Anthropic",  config.ANTHROPIC_KEY),
                ("ZEFIX",      config.ZEFIX_USER),
                ("SMTP",       config.SMTP_PASS),
            ]:
                status = "✅" if val else "❌ fehlt"
                st.write(f"{status} {label}")
        # E-Mail-Versand: Eingabe NUR in Tab 3 (Export), nicht doppelt
    # Bestehende Excel: Eingabe NUR in Tab 3 (Export), nicht doppelt
    sidebar_email = ""
    send_after = False
    existing_file = None

    # ── Notfall-Download immer verfügbar ─────────────────────────────────
    st.divider()
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
tab1, tab2, tab3 = st.tabs(["📋 Firmen eingeben", "📊 Ergebnisse", "📤 Export"])

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
                    result = pipeline.run(raw, progress_callback=_cb)
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

            # Finale Excel mit existierender Excel-Datei mergen
            existing_bytes = existing_file.getvalue() if existing_file else None
            st.session_state.excel_cache = output.results_to_excel(
                [r for r in st.session_state.results if "_error" not in r] or st.session_state.results,
                existing_bytes,
            )

            # Auto-Mail
            if send_after and sidebar_email and st.session_state.results:
                try:
                    to_list = [e.strip() for e in sidebar_email.split(",") if e.strip()]
                    output.send_email(to_list, st.session_state.results, st.session_state.excel_cache)
                    st.success(f"📧 E-Mail gesendet an: {', '.join(to_list)}")
                except Exception as exc:
                    st.error(f"E-Mail Fehler: {exc}")

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
**Schritt 3** – Ergebnisse ansehen, als Excel herunterladen oder per Mail senden

**Was die App recherchiert:**
- 📰 Aktuelle News & Pressemitteilungen (SerpAPI)
- 🏗️ Bau- und Expansionspläne
- 💼 Offene Stellen (Logistik / Supply Chain)
- 🏛️ Verbandsmitgliedschaften
- 🏢 Stammdaten (ZEFIX Handelsregister via Firecrawl)
- 🤖 KI-Analyse: 3 belegte Pain Points (Claude)
- 🎯 **Miller-Heiman Vertriebsbriefing** (Buying Influences, Talking Points, Red Flags)
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

        col_dl, col_mail = st.columns(2)

        with col_dl:
            st.markdown("**📥 Excel herunterladen**")
            st.download_button(
                label="Excel herunterladen",
                data=st.session_state.excel_cache,
                file_name=f"Enrichment_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
            st.caption("Direkt in Teams/SharePoint hochladen oder als Attachment verwenden.")

        with col_mail:
            st.markdown("**📧 Per Mail senden**")
            export_mail = st.text_input(
                "Empfänger (kommagetrennt für mehrere)",
                key="export_mail_field",
                placeholder="vertrieb@dreier.ch",
            )
            if st.button("Jetzt senden", key="send_mail_btn"):
                if not export_mail.strip():
                    st.warning("Bitte Empfänger angeben.")
                elif not config.SMTP_PASS:
                    st.warning("⚠️ SMTP-Passwort in Streamlit Secrets noch nicht gesetzt. Bitte Admin kontaktieren.")
                else:
                    try:
                        to_list = [e.strip() for e in export_mail.split(",") if e.strip()]
                        output.send_email(to_list, st.session_state.results, st.session_state.excel_cache)
                        st.success(f"✅ Gesendet an {', '.join(to_list)}")
                    except Exception as exc:
                        st.error(f"E-Mail-Versand fehlgeschlagen: {exc}")
                        st.caption("Hinweis: Bei wiederholten Fehlern Admin kontaktieren.")

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

# ─── ROKA-Footer ──────────────────────────────────────────────────────────────
st.markdown(
    "<div class='roka-footer'>"
    "ROKA Consulting · KI-Logistik-Pionier der Schweiz · "
    "<a href='https://rokaconsulting.ch' style='color:#1279BE;text-decoration:none;'>rokaconsulting.ch</a> · "
    "roland.kalt@rokaconsulting.ch"
    "</div>",
    unsafe_allow_html=True,
)
