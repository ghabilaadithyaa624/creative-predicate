"""
Global settings and environment configuration.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# This file lives at <repo>/backend/config/settings.py, so the repository root
# is three parents up. Anchoring on it keeps data/, logs/ and results/ at the
# repo root rather than burying them inside the backend package.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class AgentConfig:
    name: str = "AlphaBot"
    initial_bankroll: float = 100.0
    survival_mode: str = "aggressive"  # aggressive, conservative, terminal
    tick_interval_seconds: float = 60.0
    max_concurrent_bets: int = 5
    markets: List[str] = field(default_factory=lambda: ["polymarket", "sports"])


@dataclass
class RiskConfig:
    kelly_fraction: float = 0.25
    min_edge: float = 0.02
    max_bet_pct: float = 0.05
    max_drawdown_pct: float = 0.30
    max_consecutive_losses: int = 10
    enable_circuit_breaker: bool = True


@dataclass
class VisionConfig:
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    ocr_languages: List[str] = field(default_factory=lambda: ["en"])
    screenshot_on_decision: bool = True


@dataclass
class Settings:
    # settings.py lives at <repo>/backend/config/, so the repo root is three
    # parents up. Getting this wrong silently relocates data/ and logs/ inside
    # the backend package.
    base_dir: Path = field(default_factory=lambda: _REPO_ROOT)
    data_dir: Path = field(default_factory=lambda: _REPO_ROOT / "data")
    logs_dir: Path = field(default_factory=lambda: _REPO_ROOT / "logs")

    agent: AgentConfig = field(default_factory=AgentConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    dashboard_port: int = 8501

    database_url: str = "sqlite:///data/trading.db"
    redis_url: str = "redis://localhost:6379/0"

    def ensure_directories(self):
        """Create necessary workspace folders if they don't exist."""
        for d in [
            self.data_dir,
            self.data_dir / "historical",
            self.data_dir / "cache",
            self.logs_dir,
            self.base_dir / "models",
            self.base_dir / "results",
        ]:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load_from_yaml(cls, yaml_path: Optional[str | Path] = None) -> "Settings":
        settings = cls()
        settings.ensure_directories()

        path = Path(yaml_path) if yaml_path else settings.base_dir / "backend" / "config" / "agents.yaml"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = yaml.safe_load(f) or {}

            if "agent" in data:
                settings.agent = AgentConfig(**data["agent"])
            if "risk" in data:
                settings.risk = RiskConfig(**data["risk"])
            if "vision" in data:
                settings.vision = VisionConfig(**data["vision"])

        return settings


_global_settings: Optional[Settings] = None


def get_settings(yaml_path: Optional[str | Path] = None) -> Settings:
    global _global_settings
    if _global_settings is None or yaml_path is not None:
        _global_settings = Settings.load_from_yaml(yaml_path)
    return _global_settings
