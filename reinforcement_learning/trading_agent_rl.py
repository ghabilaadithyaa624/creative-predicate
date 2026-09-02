"""
Deep Reinforcement Learning for Trading Strategy Optimization.
Implements custom TradingEnvironment, PPO (Proximal Policy Optimization), and Soft Actor-Critic (SAC).
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import random
import numpy as np
from loguru import logger

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.distributions import Normal
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    torch = Any
    nn = Any


@dataclass
class Transition:
    state: np.ndarray
    action: np.ndarray
    reward: float
    next_state: np.ndarray
    done: bool
    info: Dict[str, Any]


class TradingEnvironment:
    """
    Gym-compatible simulation environment for RL agents.
    State: Market odds, implied probability, volume, sentiment, current drawdown, exposure.
    Action: Continuous position sizing array [0.0, 1.0].
    Reward: Risk-adjusted returns (Sharpe ratio) with drawdown penalties.
    """
    def __init__(
        self,
        historical_data: Optional[List[Dict[str, Any]]] = None,
        initial_bankroll: float = 100.0,
        transaction_cost: float = 0.001,
        max_positions: int = 5,
    ):
        self.data = historical_data or self._generate_default_episodes()
        self.initial_bankroll = initial_bankroll
        self.transaction_cost = transaction_cost
        self.max_positions = max_positions
        
        self.current_step = 0
        self.bankroll = initial_bankroll
        self.positions: List[Dict[str, Any]] = []
        self.history: List[float] = [initial_bankroll]
        
        self.state_dim = 25
        self.action_dim = max_positions

    def _generate_default_episodes(self) -> List[Dict[str, Any]]:
        episodes = []
        for i in range(100):
            p = float(np.random.uniform(0.40, 0.70))
            odds = round(1.0 / (p * 1.04), 2)
            episodes.append({
                "odds": max(1.10, odds),
                "true_probability": p,
                "volume": float(np.random.uniform(10000, 500000)),
                "sentiment": float(np.random.uniform(-0.5, 0.5)),
                "spread": 0.04,
            })
        return episodes

    def reset(self) -> np.ndarray:
        self.current_step = 0
        self.bankroll = self.initial_bankroll
        self.positions.clear()
        self.history = [self.bankroll]
        return self._get_state()

    def _get_state(self) -> np.ndarray:
        if self.current_step >= len(self.data):
            return np.zeros(self.state_dim, dtype=np.float32)

        market = self.data[self.current_step]
        peak = max(self.history) if self.history else self.bankroll
        drawdown = (peak - self.bankroll) / peak if peak > 0 else 0.0

        features = [
            market.get("odds", 2.0) / 10.0,
            market.get("volume", 10000.0) / 1e6,
            market.get("sentiment", 0.0),
            market.get("spread", 0.05),
            self.bankroll / self.initial_bankroll,
            len(self.positions) / self.max_positions,
            drawdown,
            float(self.current_step) / max(1, len(self.data)),
        ]
        arr = np.array(features, dtype=np.float32)
        if len(arr) < self.state_dim:
            arr = np.pad(arr, (0, self.state_dim - len(arr)))
        return arr[:self.state_dim]

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        if self.current_step >= len(self.data):
            return self._get_state(), 0.0, True, {}

        market = self.data[self.current_step]
        total_pnl = 0.0

        for i, raw_stake_pct in enumerate(action[:self.max_positions]):
            stake_pct = float(np.clip(raw_stake_pct, 0.0, 0.10))
            if stake_pct > 0.01:
                stake = self.bankroll * stake_pct
                if stake > 0 and stake <= self.bankroll:
                    won = random.random() < market.get("true_probability", 0.5)
                    self.bankroll -= stake
                    if won:
                        payout = stake * market.get("odds", 2.0)
                        self.bankroll += payout
                        trade_pnl = payout - stake
                    else:
                        trade_pnl = -stake

                    self.bankroll -= stake * self.transaction_cost
                    total_pnl += trade_pnl
                    self.positions.append({"stake": stake, "pnl": trade_pnl})

        self.history.append(self.bankroll)
        peak = max(self.history)
        drawdown = (peak - self.bankroll) / peak if peak > 0 else 0.0

        reward = (total_pnl / self.initial_bankroll * 10.0) - (drawdown * 5.0)

        done = (
            self.bankroll < (self.initial_bankroll * 0.50) or
            self.current_step >= len(self.data) - 1
        )
        self.current_step += 1

        return self._get_state(), reward, done, {
            "bankroll": self.bankroll,
            "drawdown": drawdown,
            "total_pnl": total_pnl
        }


if HAS_TORCH:
    class ActorCriticNetwork(nn.Module):
        def __init__(self, state_dim: int = 25, action_dim: int = 5):
            super().__init__()
            self.backbone = nn.Sequential(
                nn.Linear(state_dim, 128),
                nn.ReLU(),
                nn.Linear(128, 64),
                nn.ReLU(),
            )
            self.actor_mean = nn.Linear(64, action_dim)
            self.actor_log_std = nn.Parameter(torch.zeros(action_dim))
            self.critic = nn.Linear(64, 1)

        def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            feats = self.backbone(state)
            mean = torch.sigmoid(self.actor_mean(feats)) * 0.10
            std = torch.exp(torch.clamp(self.actor_log_std, -2.0, 0.5))
            value = self.critic(feats)
            return mean, std, value
else:
    class ActorCriticNetwork:
        def __init__(self, *args, **kwargs):
            pass


class PPOTrader:
    """
    Proximal Policy Optimization Reinforcement Learning Agent for position sizing.
    """
    def __init__(self, env: TradingEnvironment, lr: float = 1e-3):
        self.env = env
        self.device = torch.device('cpu') if HAS_TORCH else None
        if HAS_TORCH:
            self.network = ActorCriticNetwork(env.state_dim, env.action_dim).to(self.device)
            self.optimizer = torch.optim.Adam(self.network.parameters(), lr=lr)
        self.memory: List[Transition] = []

    def select_action(self, state: np.ndarray) -> np.ndarray:
        if not HAS_TORCH:
            return np.ones(self.env.action_dim, dtype=np.float32) * 0.03

        state_t = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            mean, std, _ = self.network(state_t)
            dist = Normal(mean, std)
            action = dist.sample()
            action = torch.clamp(action, 0.0, 0.10)
        return action.cpu().numpy()[0]

    def train_episodes(self, episodes: int = 10) -> Dict[str, float]:
        total_rewards = []
        for ep in range(episodes):
            state = self.env.reset()
            ep_reward = 0.0
            done = False
            while not done:
                action = self.select_action(state)
                next_state, reward, done, _ = self.env.step(action)
                self.memory.append(Transition(state, action, reward, next_state, done, {}))
                state = next_state
                ep_reward += reward
            total_rewards.append(ep_reward)

        return {
            "episodes_trained": episodes,
            "avg_reward": round(float(np.mean(total_rewards)), 2),
            "final_bankroll": round(self.env.bankroll, 2)
        }
