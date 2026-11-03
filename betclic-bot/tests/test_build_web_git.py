import json
import re
import subprocess
from datetime import timedelta

from betclic_bot import build_web, git_sync
from betclic_bot.ledger import LOST, WON, Ledger

from conftest import NOW


def _ledger(tmp_path):
    led = Ledger(tmp_path / "ledger.json", 10.0, NOW)
    for bid, kind in (("a", "SIMPLE"), ("b", "SIMPLE"), ("c", "COMBINE")):
        led.place({"id": bid, "kind": kind, "label": bid, "odd": 2.0, "profile": "SAFE" if kind == "SIMPLE" else "COMBINE",
                   "score": 60, "competition": "Premier League", "match": f"M {bid}", "market": "h2h",
                   "market_label": "Vainqueur du match", "selection": "X", "kickoff": "2026-11-03T20:00:00Z",
                   "headline": "stat <b>", "legs": [{"match": f"M {bid}", "competition": "PL", "selection": "X", "odd": 2.0,
                                                     "kickoff": "2026-11-03T20:00:00Z"}]}, 1.0, NOW)
    led.settle("a", WON, NOW + timedelta(days=1), "2-0")
    led.settle("b", LOST, NOW + timedelta(days=1, hours=1), "0-1")
    return led


def test_site_data(tmp_path):
    data = build_web.site_data(_ledger(tmp_path), NOW + timedelta(days=1, hours=2), site_url="https://x/")
    m = data["metrics"]
    assert (m["equity"], m["profit"], m["won"], m["lost"], m["pending"]) == (10.0, 0.0, 1, 1, 1)
    assert [p["v"] for p in data["equity"]] == [10.0, 11.0, 10.0]
    assert [p["id"] for p in data["positions"]] == ["c"]
    assert {b["id"]: b["balance"] for b in data["bets"]} == {"a": 9.0, "b": 9.0, "c": 7.0}
    profiles = {r["name"]: r for r in data["analytics"]["by_profile"]}
    assert profiles["Safe"]["winrate"] == 0.5 and profiles["Combiné"]["settled"] == 0


def test_build_writes_static_site(tmp_path):
    out = tmp_path / "docs"
    build_web.build(_ledger(tmp_path), out, NOW, site_url="https://x/")
    html = (out / "index.html").read_text()
    assert (out / "style.css").exists() and (out / "app.js").exists() and (out / ".nojekyll").exists()
    payload = re.search(r'<script id="fund-data" type="application/json">(.*?)</script>', html, re.S).group(1)
    assert json.loads(payload.replace("<\\/", "</"))["metrics"]["initial"] == 10.0
    assert "</b>" not in payload  # pas de balise fermante brute dans le JSON injecté
    css = (out / "style.css").read_text()
    assert "Inter" not in css.replace("Instrument", "") and "backdrop-filter" not in css
    for color in ("#F6F4F0", "#0F1012", "#166534", "#991B1B"):
        assert color in css


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)
    run("init", "-q", "-b", "main")
    run("config", "user.email", "t@example.com"); run("config", "user.name", "t")
    (repo / ".gitignore").write_text(".env\n")
    return repo, run


def test_git_sync_blocks_leaked_secret(tmp_path):
    repo, run = _repo(tmp_path)
    env = repo / ".env"
    env.write_text("ODDS_API_KEY=abcdef123456\nTELEGRAM_BOT_TOKEN=999:ZZZsecret\n")
    (repo / "page.html").write_text("token 999:ZZZsecret")
    result = git_sync.sync(repo, "update", env)
    assert not result.ok and "secrète" in result.detail
    assert subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=repo, capture_output=True, text=True).stdout == ""


def test_git_sync_commits_and_reports_push_failure(tmp_path):
    repo, run = _repo(tmp_path)
    env = repo / ".env"
    env.write_text("ODDS_API_KEY=abcdef123456\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "index.html").write_text("ok")
    result = git_sync.sync(repo, "update: bilan", env)
    assert result.committed and not result.ok and "push" in result.detail  # pas de remote dans le test
    files = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True).stdout.split()
    assert ".env" not in files and "docs/index.html" in files


def test_site_url_from_remote(tmp_path):
    repo, run = _repo(tmp_path)
    run("remote", "add", "origin", "https://github.com/Maxance/claude-betclic-fund.git")
    assert git_sync.site_url(repo) == "https://maxance.github.io/claude-betclic-fund/"
