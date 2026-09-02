"""
Circuit breaker and survival manager for autonomous agents.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple, Dict, Any
from loguru import logger


class SurvivalMode(str, Enum):
    AGGRESSIVE = "aggressive"      # Die if bankroll < 50%
    CONSERVATIVE = "conservative"  # Die if bankroll < 80%
    TERMINAL = "terminal"          # Die on any loss or < 100%
    CUSTOM = "custom"


@dataclass
class SurvivalRule:
    """
    Evaluates circuit-breaker trigger conditions.
    """
    min_bankroll_pct: float = 0.50
    max_drawdown_pct: float = 0.30
    max_consecutive_losses: int = 10
    min_win_rate: float = 0.0
    time_limit_hours: Optional[int] = None

    @classmethod
    def from_mode(cls, mode: str | SurvivalMode) -> "SurvivalRule":
        mode_val = mode.value if isinstance(mode, SurvivalMode) else str(mode).lower()
        if mode_val == "conservative":
            return cls(min_bankroll_pct=0.80, max_drawdown_pct=0.20, max_consecutive_losses=5)
        elif mode_val == "terminal":
            return cls(min_bankroll_pct=1.00, max_drawdown_pct=0.05, max_consecutive_losses=1)
        elif mode_val == "aggressive":
            return cls(min_bankroll_pct=0.50, max_drawdown_pct=0.40, max_consecutive_losses=10)
        return cls()

    def check(self, state_dict: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        bankroll = state_dict.get("bankroll", 100.0)
        initial_bankroll = state_dict.get("initial_bankroll", 100.0)
        consecutive_losses = state_dict.get("consecutive_losses", 0)
        drawdown = state_dict.get("current_drawdown", 0.0)
        win_rate = state_dict.get("win_rate", 0.0)
        total_bets = state_dict.get("total_bets", 0)

        # 1. Bankroll floor
        min_allowed = initial_bankroll * self.min_bankroll_pct
        if bankroll < min_allowed:
            return False, f"Bankroll (${bankroll:.2f}) dropped below {self.min_bankroll_pct*100:.0f}% threshold (${min_allowed:.2f})"

        # 2. Maximum drawdown
        if drawdown > self.max_drawdown_pct:
            return False, f"Peak drawdown ({drawdown*100:.1f}%) exceeded limit ({self.max_drawdown_pct*100:.1f}%)"

        # 3. Consecutive loss limit
        if consecutive_losses >= self.max_consecutive_losses:
            return False, f"Consecutive loss streak reached {consecutive_losses} (limit: {self.max_consecutive_losses})"

        # 4. Minimum win rate check after sample size
        if total_bets >= 20 and win_rate < self.min_win_rate:
            return False, f"Win rate ({win_rate*100:.1f}%) below minimum required ({self.min_win_rate*100:.1f}%)"

        return True, None
