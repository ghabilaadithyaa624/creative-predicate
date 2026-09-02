"""
Guards for the backend/frontend split.

The reorganisation moved config/settings.py one level deeper. Its paths were
derived from `Path(__file__).parent.parent`, which silently began resolving to
<repo>/backend instead of <repo>, relocating data/, logs/ and results/ inside
the backend package. No existing test touched settings, so nothing caught it.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_settings_paths_anchor_to_repo_root():
    from backend.config.settings import Settings

    s = Settings()
    assert s.base_dir == REPO_ROOT
    assert s.data_dir == REPO_ROOT / "data"
    assert s.logs_dir == REPO_ROOT / "logs"
    # Must not be buried inside the package.
    assert "backend" not in s.data_dir.relative_to(REPO_ROOT).parts


def test_default_agents_yaml_is_discoverable():
    from backend.config.settings import Settings

    s = Settings()
    assert (s.base_dir / "backend" / "config" / "agents.yaml").exists()


def test_dashboard_entrypoint_exists_where_cli_expects_it():
    """`main.py dashboard` shells out to this path; a move must not break it."""
    assert (REPO_ROOT / "frontend" / "dashboard" / "app.py").exists()


def test_backend_does_not_import_frontend():
    """
    The dependency must run one way: frontend -> backend. A backend module
    importing the Streamlit layer would make the API unimportable without it.
    """
    offenders = []
    for path in (REPO_ROOT / "backend").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import frontend", "from frontend")):
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {stripped}")
    assert not offenders, "backend must not depend on frontend:\n" + "\n".join(offenders)


def test_no_stale_top_level_package_imports():
    """
    Catch imports still pointing at the pre-split namespaces (e.g.
    `from trading.paper_engine import ...`), including string targets used by
    mock.patch, which a plain import rewrite misses.
    """
    moved = [
        "agents", "analysis", "api", "backtest", "blockchain", "config",
        "federated", "feeds", "memory", "ml_models", "monte_carlo",
        "neuromorphic", "notifications", "quantum", "reinforcement_learning",
        "risk", "scheduler", "swarm", "trading", "vision", "dashboard",
    ]
    offenders = []
    for path in REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(REPO_ROOT)
        if rel.parts[0] in {".venv", "build", "dist"} or "egg-info" in str(rel):
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            for pkg in moved:
                if s.startswith(f"from {pkg} ") or s.startswith(f"from {pkg}."):
                    offenders.append(f"{rel}:{i}: {s}")
                if s.startswith(f"import {pkg}.") or s == f"import {pkg}":
                    offenders.append(f"{rel}:{i}: {s}")
                if f'patch("{pkg}.' in s or f"patch('{pkg}." in s:
                    offenders.append(f"{rel}:{i}: {s}")
    assert not offenders, "stale pre-split imports:\n" + "\n".join(offenders)


def test_package_imports_resolve():
    """Both namespaces must be importable from a clean interpreter."""
    code = (
        "import backend, frontend;"
        "from backend.trading.paper_engine import PaperTradingEngine;"
        "from backend.analysis.scraper import MarketScraper;"
        "from backend.agents.polymarket_agent import PolymarketAgent;"
        "print('ok')"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout
