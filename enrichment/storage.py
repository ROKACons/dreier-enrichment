"""
Persistenz-Modul fuer Zwischenspeicherung der Enrichment-Ergebnisse.
Speichert jedes Resultat sofort nach Abschluss auf Disk - so geht bei
Verbindungsabbruch, Streamlit-Restart oder Browser-Crash NICHTS verloren.
"""
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path


def _storage_dir() -> Path:
    """Verzeichnis fuer Zwischenspeicherung - auf Streamlit Cloud /tmp persistent fuer Session."""
    base = Path(tempfile.gettempdir()) / "dreier_enrichment"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _state_file() -> Path:
    return _storage_dir() / "current_batch.json"


def init_batch(company_list: list[str]) -> dict:
    """Neuen Batch starten - ueberschreibt evtl. vorhandenen alten Batch."""
    state = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(company_list),
        "pending": list(company_list),
        "completed": [],          # Firmennamen die fertig sind
        "results": [],            # Tatsaechliche Ergebnisse
        "log": [],
        "finished": False,
    }
    _save(state)
    return state


def save_result(state: dict, company_input: str, result: dict, log_line: str) -> dict:
    """Ein einzelnes Ergebnis dauerhaft sichern."""
    state["results"].append(result)
    state["completed"].append(company_input)
    state["log"].append(log_line)
    if company_input in state["pending"]:
        state["pending"].remove(company_input)
    _save(state)
    return state


def mark_finished(state: dict) -> dict:
    state["finished"] = True
    state["finished_at"] = datetime.now().isoformat(timespec="seconds")
    _save(state)
    return state


def load_batch() -> dict | None:
    """Bestehenden Batch laden falls vorhanden."""
    f = _state_file()
    if not f.exists():
        return None
    try:
        with open(f, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except Exception:
        return None


def has_unfinished_batch() -> bool:
    state = load_batch()
    return bool(state and not state.get("finished") and state.get("pending"))


def clear_batch() -> None:
    """Aktuellen Batch loeschen (z.B. nach erfolgreichem Download)."""
    f = _state_file()
    if f.exists():
        f.unlink()


def _save(state: dict) -> None:
    """Atomares Schreiben - erst in temp, dann umbenennen."""
    target = _state_file()
    tmp = target.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fp:
            json.dump(state, fp, ensure_ascii=False, indent=2, default=str)
        tmp.replace(target)
    except Exception:
        # Bei Schreibfehler: nicht weiter blockieren, aber loggen
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def batch_summary(state: dict) -> dict:
    """Statistik fuer UI-Anzeige."""
    if not state:
        return {"total": 0, "done": 0, "pending": 0, "errors": 0}
    errors = sum(1 for r in state.get("results", []) if "_error" in r)
    return {
        "total":   state.get("total", 0),
        "done":    len(state.get("completed", [])),
        "pending": len(state.get("pending", [])),
        "errors":  errors,
        "started_at": state.get("started_at", ""),
    }
