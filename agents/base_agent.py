"""
Base autonomous agent with lifecycle, event observation, and perception-reason-action loops.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import uuid
import asyncio
from loguru import logger

from agents.survival_manager import SurvivalRule, SurvivalMode
from trading.paper_engine import PaperTradingEngine, AgentState as PaperAgentState, Bet


class AgentStatus(str, Enum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    TERMINATED = "terminated"
    ERROR = "error"


class BaseAgent(ABC):
    """
    Abstract base class for autonomous trading agents.
    Implements:
    - Perceive -> Reason -> Act cycle
    - Circuit breaker evaluation
    - Observer event dispatch
    - State tracking
    """

    def __init__(
        self,
        name: str,
        trading_engine: PaperTradingEngine,
        initial_bankroll: float = 100.0,
        survival_mode: SurvivalMode = SurvivalMode.AGGRESSIVE,
        survival_rule: Optional[SurvivalRule] = None,
        tick_interval: float = 10.0,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.trading_engine = trading_engine
        self.survival_mode = survival_mode
        self.survival_rule = survival_rule or SurvivalRule.from_mode(survival_mode)
        self.tick_interval = tick_interval
        self.config = config or {}
        
        self.status = AgentStatus.INITIALIZING
        self.history: List[Dict[str, Any]] = []
        self._observers: List[Callable[[str, Dict[str, Any]], None]] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # Register inside the paper trading engine
        self.paper_state = self.trading_engine.create_agent(
            name=self.name,
            initial_bankroll=initial_bankroll,
            survival_mode=survival_mode,
        )
        self.status = AgentStatus.ACTIVE
        logger.info(f"Initialized agent '{self.name}' with bankroll ${initial_bankroll:.2f} [{self.survival_mode.value}]")

    # ============ Observers & Events ============

    def add_observer(self, callback: Callable[[str, Dict[str, Any]], None]):
        self._observers.append(callback)

    def _notify_observers(self, event_name: str, data: Dict[str, Any]):
        for observer in self._observers:
            try:
                observer(event_name, data)
            except Exception as e:
                logger.error(f"Error in observer callback: {e}")

    # ============ Lifecycle ============

    async def initialize(self):
        """Pre-run setup hook."""
        self.status = AgentStatus.ACTIVE
        await self._setup()
        logger.info(f"Agent '{self.name}' setup completed.")

    async def _setup(self):
        """Override in subclasses for custom warmup or model loading."""
        pass

    async def run_loop(self):
        """Continuous execution loop."""
        await self.initialize()
        self._running = True
        logger.info(f"Agent '{self.name}' starting autonomous cycle loop...")

        try:
            while self._running and self.status == AgentStatus.ACTIVE:
                cycle_success = await self.run_cycle()
                if not cycle_success:
                    break
                await asyncio.sleep(self.tick_interval)
        except asyncio.CancelledError:
            logger.info(f"Agent '{self.name}' execution cancelled.")
        except Exception as e:
            logger.error(f"Agent '{self.name}' encountered error: {e}")
            self.status = AgentStatus.ERROR
        finally:
            self._running = False

    def stop(self):
        """Gracefully stop agent loop."""
        self._running = False
        if self.status != AgentStatus.TERMINATED:
            self.status = AgentStatus.PAUSED
        logger.info(f"Agent '{self.name}' stopped.")

    # ============ Core Cycle: Perceive -> Reason -> Act ============

    @abstractmethod
    async def perceive(self) -> Dict[str, Any]:
        """Gathers environmental information (odds, books, news, etc.)."""
        pass

    @abstractmethod
    async def reason(self, perception_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyzes data, runs models, determines edge and candidate actions."""
        pass

    @abstractmethod
    async def act(self, decisions: List[Dict[str, Any]]) -> List[Bet]:
        """Executes candidate bets through the paper trading engine."""
        pass

    async def run_cycle(self) -> bool:
        """
        Executes a single autonomous tick:
        1. Survival check
        2. Perceive
        3. Reason
        4. Act
        5. Record telemetry
        """
        # 1. Circuit breaker check
        metrics = self.paper_state.calculate_metrics()
        state_dict = {
            "bankroll": self.paper_state.current_bankroll,
            "initial_bankroll": self.paper_state.initial_bankroll,
            "consecutive_losses": self.paper_state.consecutive_losses,
            "current_drawdown": metrics["current_drawdown"],
            "win_rate": metrics["win_rate"],
            "total_bets": metrics["total_bets"],
        }
        is_alive, kill_reason = self.survival_rule.check(state_dict)
        if not is_alive:
            self.status = AgentStatus.TERMINATED
            self.paper_state.is_alive = False
            self.paper_state.kill_reason = kill_reason
            logger.warning(f" Agent '{self.name}' TERMINATED: {kill_reason}")
            self._notify_observers("agent_terminated", {"name": self.name, "reason": kill_reason})
            return False

        try:
            # 2. Perceive
            perception = await self.perceive()
            
            # 3. Reason
            decisions = await self.reason(perception)
            
            # 4. Act
            placed_bets = await self.act(decisions)
            
            # 5. Record
            cycle_record = {
                "timestamp": datetime.now().isoformat(),
                "name": self.name,
                "perception_summary": len(perception.get("markets", [])),
                "decisions_count": len(decisions),
                "placed_bets_count": len(placed_bets),
                "bankroll": self.paper_state.current_bankroll,
                "status": self.status.value,
            }
            self.history.append(cycle_record)
            self._notify_observers("cycle_completed", cycle_record)
            return True
            
        except Exception as e:
            logger.error(f"Cycle failed for agent '{self.name}': {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Detailed status summary."""
        metrics = self.paper_state.calculate_metrics()
        return {
            "name": self.name,
            "status": self.status.value,
            "survival_mode": self.survival_mode.value,
            "metrics": metrics,
            "history_length": len(self.history),
        }
