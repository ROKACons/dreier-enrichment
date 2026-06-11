"""
Bedarfsfelder-Matrix: lokal lesen + auf GitHub committen.
Streamlit Cloud hat kein persistentes Filesystem -> nur GitHub ist verlaesslich.
"""
import json
from datetime import date
from pathlib import Path

from config import GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH

MATRIX_PATH = Path(__file__).resolve().parent.parent / "config" / "branches.json"


def load_matrix() -> dict:
    """Lade Matrix aus lokaler Datei (Repo-Stand bei letztem Deploy)."""
    if not MATRIX_PATH.exists():
        return {"version": 1, "branches": {}}
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def save_matrix_local(matrix: dict) -> None:
    MATRIX_PATH.parent.mkdir(parents=True, exist_ok=True)
    MATRIX_PATH.write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def commit_matrix_to_github(matrix: dict, message: str = "Update Bedarfsfelder-Matrix") -> str:
    """
    Committet die Matrix ueber die GitHub-API ins Repo.
    Streamlit Cloud erkennt das und re-deployed automatisch (~30s).
    Returns: Commit-SHA oder Fehlertext.
    """
    if not (GITHUB_TOKEN and GITHUB_REPO):
        raise RuntimeError(
            "GITHUB_TOKEN oder GITHUB_REPO fehlt in Secrets – "
            "Persistenz nicht moeglich."
        )

    from github import Github, GithubException

    matrix["updated_at"] = date.today().isoformat()
    content = json.dumps(matrix, ensure_ascii=False, indent=2) + "\n"

    gh = Github(GITHUB_TOKEN)
    repo = gh.get_repo(GITHUB_REPO)
    path = "config/branches.json"

    try:
        existing = repo.get_contents(path, ref=GITHUB_BRANCH)
        result = repo.update_file(
            path=path,
            message=message,
            content=content,
            sha=existing.sha,
            branch=GITHUB_BRANCH,
        )
    except GithubException as e:
        if e.status == 404:
            result = repo.create_file(
                path=path,
                message=message,
                content=content,
                branch=GITHUB_BRANCH,
            )
        else:
            raise

    return result["commit"].sha


def matrix_to_prompt_block(matrix: dict) -> str:
    """Kompakt fuer Claude-Prompt (spart Token gegenueber JSON-Indent)."""
    lines = []
    for branche, details in matrix.get("branches", {}).items():
        joined = " | ".join(details) if details else "(keine Details)"
        lines.append(f"- {branche}: {joined}")
    return "\n".join(lines) if lines else "(Matrix leer)"


def matrix_to_dataframe_rows(matrix: dict) -> list[dict]:
    """Flache Liste fuer st.data_editor."""
    rows = []
    for branche, details in matrix.get("branches", {}).items():
        if not details:
            rows.append({"Branche": branche, "Detail": ""})
            continue
        for d in details:
            rows.append({"Branche": branche, "Detail": d})
    return rows


def dataframe_rows_to_matrix(rows: list[dict]) -> dict:
    """Inverse: Editor-Output -> Matrix-Dict."""
    out: dict[str, list[str]] = {}
    for row in rows:
        branche = (row.get("Branche") or "").strip()
        detail = (row.get("Detail") or "").strip()
        if not branche:
            continue
        out.setdefault(branche, [])
        if detail and detail not in out[branche]:
            out[branche].append(detail)
    return {"version": 1, "branches": out}
