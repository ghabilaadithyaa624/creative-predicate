"""
Paper trading simulation engine for autonomous agents.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import json
import uuid


class BetStatus(str, Enum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    CANCELLED = "cancelled"
    PUSH = "push"


class SurvivalMode(str, Enum):
    AGGRESSIVE = "aggressive"      # Die if bankroll < 50%
    CONSERVATIVE = "conservative"  # Die if bankroll < 80%
    TERMINAL = "terminal"          # Die on any loss or < 100%
    CUSTOM = "custom"


@dataclass
class Bet:
    id: str
    agent_name: str
    market: str                     # "polymarket", "sports", etc.
    event: str                      # "Lakers vs Warriors"
    selection: str                  # "Lakers Win"
    odds: float                     # Decimal odds (e.g. 2.50)
    stake: float                    # Bet amount
    expected_value: float           # Expected value (edge)
    timestamp: datetime = field(default_factory=datetime.now)
    status: BetStatus = BetStatus.PENDING
    result: Optional[float] = None  # Payout received (0 if lost, stake * odds if won)
    settled_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def pnl(self) -> float:
        if self.status == BetStatus.WON:
            return (self.result or (self.stake * self.odds)) - self.stake
        elif self.status == BetStatus.LOST:
            return -self.stake
        elif self.status in (BetStatus.CANCELLED, BetStatus.PUSH):
            return 0.0
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "market": self.market,
            "event": self.event,
            "selection": self.selection,
            "odds": self.odds,
            "stake": self.stake,
            "expected_value": self.expected_value,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "result": self.result,
            "pnl": self.pnl,
            "settled_at": self.settled_at.isoformat() if self.settled_at else None,
            "metadata": self.metadata,
        }


@dataclass
class AgentState:
    name: str
    initial_bankroll: float
    current_bankroll: float
    bets: List[Bet] = field(default_factory=list)
    survival_mode: SurvivalMode = SurvivalMode.AGGRESSIVE
    is_alive: bool = True
    kill_reason: Optional[str] = None
    peak_bankroll: float = 100.0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    balance_history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not self.balance_history:
            self.balance_history.append({
                "timestamp": datetime.now().isoformat(),
                "bankroll": self.current_bankroll,
                "event": "initialization"
            })
        self.peak_bankroll = max(self.peak_bankroll, self.current_bankroll)

    def calculate_metrics(self) -> Dict[str, Any]:
        total_bets = len(self.bets)
        settled_bets = [b for b in self.bets if b.status in (BetStatus.WON, BetStatus.LOST)]
        won_bets = [b for b in settled_bets if b.status == BetStatus.WON]
        lost_bets = [b for b in settled_bets if b.status == BetStatus.LOST]
        pending_bets = [b for b in self.bets if b.status == BetStatus.PENDING]
        
        win_rate = (len(won_bets) / len(settled_bets)) if settled_bets else 0.0
        total_staked = sum(b.stake for b in self.bets)
        total_profit = self.current_bankroll - self.initial_bankroll
        roi = (total_profit / self.initial_bankroll * 100.0) if self.initial_bankroll > 0 else 0.0
        
        current_drawdown = (self.peak_bankroll - self.current_bankroll) / self.peak_bankroll if self.peak_bankroll > 0 else 0.0
        
        # Calculate profit factor
        gross_profit = sum(b.pnl for b in won_bets)
        gross_loss = abs(sum(b.pnl for b in lost_bets))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

        return {
            "name": self.name,
            "is_alive": self.is_alive,
            "kill_reason": self.kill_reason,
            "current_bankroll": round(self.current_bankroll, 2),
            "initial_bankroll": round(self.initial_bankroll, 2),
            "peak_bankroll": round(self.peak_bankroll, 2),
            "total_profit": round(total_profit, 2),
            "roi_percent": round(roi, 2),
            "total_bets": total_bets,
            "settled_bets": len(settled_bets),
            "pending_bets": len(pending_bets),
            "won_bets": len(won_bets),
            "lost_bets": len(lost_bets),
            "win_rate": round(win_rate, 4),
            "consecutive_wins": self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses,
            "current_drawdown": round(current_drawdown, 4),
            "profit_factor": round(profit_factor, 2),
        }

    def check_survival(self, custom_threshold: Optional[float] = None) -> bool:
        """Circuit breaker check to kill agent if conditions are breached."""
        if not self.is_alive:
            return False

        threshold_map = {
            SurvivalMode.AGGRESSIVE: 0.50,
            SurvivalMode.CONSERVATIVE: 0.80,
            SurvivalMode.TERMINAL: 1.00,
            SurvivalMode.CUSTOM: custom_threshold if custom_threshold is not None else 0.50,
        }
        threshold = threshold_map.get(self.survival_mode, 0.50)
        min_required_bankroll = self.initial_bankroll * threshold

        if self.current_bankroll < min_required_bankroll:
            self.is_alive = False
            self.kill_reason = f"Bankroll (${self.current_bankroll:.2f}) dropped below {threshold*100:.0f}% threshold (${min_required_bankroll:.2f})"
            self.balance_history.append({
                "timestamp": datetime.now().isoformat(),
                "bankroll": self.current_bankroll,
                "event": f"TERMINATED: {self.kill_reason}"
            })
            return False
        return True


class PaperTradingEngine:
    """
    Core paper trading engine managing accounts, orders, execution, and settlements.
    """

    def __init__(self, initial_bankroll: float = 100.0):
        self.initial_bankroll = initial_bankroll
        self.agents: Dict[str, AgentState] = {}
        self._listeners: List[Callable[[str, Dict[str, Any]], None]] = []

    def add_listener(self, listener: Callable[[str, Dict[str, Any]], None]):
        self._listeners.append(listener)

    def _emit(self, event_name: str, payload: Dict[str, Any]):
        for listener in self._listeners:
            try:
                listener(event_name, payload)
            except Exception:
                pass

    def create_agent(
        self,
        name: str,
        initial_bankroll: Optional[float] = None,
        survival_mode: SurvivalMode = SurvivalMode.AGGRESSIVE,
    ) -> AgentState:
        bankroll = initial_bankroll if initial_bankroll is not None else self.initial_bankroll
        agent = AgentState(
            name=name,
            initial_bankroll=bankroll,
            current_bankroll=bankroll,
            survival_mode=survival_mode,
            peak_bankroll=bankroll,
        )
        self.agents[name] = agent
        self._emit("agent_created", {"name": name, "bankroll": bankroll, "mode": survival_mode.value})
        return agent

    def place_bet(
        self,
        agent_name: str,
        market: str,
        event: str,
        selection: str,
        odds: float,
        stake: float,
        expected_value: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Bet]:
        """Place a paper bet and lock the stake."""
        agent = self.agents.get(agent_name)
        if not agent:
            return None
        if not agent.is_alive:
            return None
        if stake <= 0 or stake > agent.current_bankroll:
            return None

        # Deduct stake from available bankroll
        agent.current_bankroll -= stake
        
        bet_id = f"bet_{uuid.uuid4().hex[:8]}"
        bet = Bet(
            id=bet_id,
            agent_name=agent_name,
            market=market,
            event=event,
            selection=selection,
            odds=odds,
            stake=stake,
            expected_value=expected_value,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )
        agent.bets.append(bet)
        agent.balance_history.append({
            "timestamp": datetime.now().isoformat(),
            "bankroll": agent.current_bankroll,
            "event": f"Placed bet {bet_id} on {event} (${stake:.2f})"
        })
        
        self._emit("bet_placed", bet.to_dict())
        return bet

    def settle_bet(
        self,
        agent_name: str,
        bet_id: str,
        won: bool,
        is_push: bool = False,
        is_cancelled: bool = False,
    ) -> Optional[Bet]:
        """Settle an existing bet outcome."""
        agent = self.agents.get(agent_name)
        if not agent:
            return None

        bet = next((b for b in agent.bets if b.id == bet_id), None)
        if not bet or bet.status != BetStatus.PENDING:
            return None

        bet.settled_at = datetime.now()

        if is_cancelled:
            bet.status = BetStatus.CANCELLED
            bet.result = bet.stake
            agent.current_bankroll += bet.stake
        elif is_push:
            bet.status = BetStatus.PUSH
            bet.result = bet.stake
            agent.current_bankroll += bet.stake
        elif won:
            bet.status = BetStatus.WON
            payout = bet.stake * bet.odds
            bet.result = payout
            agent.current_bankroll += payout
            agent.consecutive_wins += 1
            agent.consecutive_losses = 0
            if agent.current_bankroll > agent.peak_bankroll:
                agent.peak_bankroll = agent.current_bankroll
        else:
            bet.status = BetStatus.LOST
            bet.result = 0.0
            agent.consecutive_losses += 1
            agent.consecutive_wins = 0

        agent.balance_history.append({
            "timestamp": datetime.now().isoformat(),
            "bankroll": agent.current_bankroll,
            "event": f"Settled {bet_id}: {bet.status.value.upper()} (PnL: ${bet.pnl:+.2f})"
        })

        agent.check_survival()
        self._emit("bet_settled", bet.to_dict())
        return bet

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Rank all active and historical agents by profit."""
        results = [agent.calculate_metrics() for agent in self.agents.values()]
        return sorted(results, key=lambda x: x["total_profit"], reverse=True)

    def get_agent_history(self, agent_name: str) -> List[Dict[str, Any]]:
        agent = self.agents.get(agent_name)
        if not agent:
            return []
        return [bet.to_dict() for bet in agent.bets]
