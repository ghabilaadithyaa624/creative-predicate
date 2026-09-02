"""
Pydantic API request and response schemas.
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class AgentCreateRequest(BaseModel):
    name: str = Field(..., example="AlphaBot")
    initial_bankroll: float = Field(default=100.0, ge=1.0)
    survival_mode: str = Field(default="aggressive", example="aggressive")


class PlaceBetRequest(BaseModel):
    agent_name: str
    market: str
    event: str
    selection: str
    odds: float
    stake: float
    expected_value: float = 0.0


class SettleBetRequest(BaseModel):
    agent_name: str
    bet_id: str
    won: bool
    is_cancelled: bool = False


class BacktestRunRequest(BaseModel):
    initial_bankroll: float = 100.0
    strategy: str = "kelly"
    kelly_fraction: float = 0.25
    min_edge: float = 0.02
    data_file: Optional[str] = None
