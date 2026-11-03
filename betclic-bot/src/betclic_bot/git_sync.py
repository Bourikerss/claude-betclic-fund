"""Publication quotidienne sur GitHub : `git add`, `commit`, `push origin main`.

Garde-fous avant chaque commit :
- un fichier `.env` (ou `*.env`) indexé bloque la publication ;
- les valeurs secrètes de `betclic-bot/.env` (clé API, token Telegram…) sont cherchées dans
  le diff indexé : si l'une apparaît, rien n'est commité.
"""
from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from dotenv import dotenv_values

log = logging.getLogger(__name__)
SECRET_KEYS = ("ODDS_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


@dataclass
class SyncResult:
    ok: bool
    detail: str
    committed: bool = False


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=check, timeout=120)


def repo_root(start: Path) -> Optional[Path]:
    try:
        out = _git(Path(start), "rev-parse", "--show-toplevel").stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    return Path(out) if out else None


def site_url(repo: Path) -> str:
    """URL GitHub Pages déduite du remote `origin` (https://<compte>.github.io/<dépôt>/)."""
    try:
        remote = _git(repo, "remote", "get-url", "origin").stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return ""
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", remote)
    return f"https://{m.group(1).lower()}.github.io/{m.group(2)}/" if m else ""


def secret_values(env_file: Path) -> List[str]:
    values = dotenv_values(env_file) if env_file.exists() else {}
    return [v for k, v in values.items() if k in SECRET_KEYS and v and len(v) >= 6]


def leaked(diff: str, secrets: Iterable[str]) -> bool:
    return any(s in diff for s in secrets)


def sync(repo: Path, message: str, env_file: Path, branch: str = "main") -> SyncResult:
    try:
        _git(repo, "add", "-A")
        staged = _git(repo, "diff", "--cached", "--name-only").stdout.split("\n")
        if any(Path(name).name == ".env" or name.endswith(".env") for name in staged if name):
            _git(repo, "reset", "-q")
            return SyncResult(False, "Publication bloquée : un fichier .env est indexé")
        if leaked(_git(repo, "diff", "--cached").stdout, secret_values(env_file)):
            _git(repo, "reset", "-q")
            return SyncResult(False, "Publication bloquée : une valeur secrète du .env apparaît dans le diff")
        if not [n for n in staged if n]:
            return SyncResult(True, "Rien à publier")
        _git(repo, "commit", "-q", "-m", message)
        push = _git(repo, "push", "-q", "origin", branch, check=False)
        if push.returncode != 0:
            return SyncResult(False, f"Commit fait, push en échec : {push.stderr.strip()[:200]}", committed=True)
        return SyncResult(True, "Publié", committed=True)
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        log.error("git_sync : %s", detail)
        return SyncResult(False, f"Erreur git : {str(detail).strip()[:200]}")
