"""
FastAPI route definitions for the Autonomous Trading Agent System.
"""
import asyncio
import os
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from analysis.scraper import MarketScraper
from api.models import AgentCreateRequest, BacktestRunRequest, PlaceBetRequest, SettleBetRequest
from api.websocket import ConnectionManager
from backtest.historical_data import HistoricalDataLoader
from backtest.simulator import BacktestEngine
from trading.paper_engine import PaperTradingEngine, SurvivalMode


def create_app(engine: PaperTradingEngine) -> FastAPI:
    app = FastAPI(
        title="Autonomous Trading Agent API",
        description="REST & WebSocket API for autonomous paper trading simulation and strategy analysis",
        version="1.0.0",
    )

    # A wildcard origin cannot be combined with credentials: browsers reject
    # the response outright. Allow credentialed access only for explicitly
    # configured origins.
    allowed_origins = [
        o.strip()
        for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
        if o.strip()
    ]
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    ws_manager = ConnectionManager()

    @app.on_event("startup")
    async def _capture_event_loop():
        # The engine emits events from synchronous code, so the broadcaster
        # needs a handle on the serving loop to schedule coroutines onto it.
        app.state.loop = asyncio.get_running_loop()

    def _broadcast_engine_event(event_name: str, data: Dict[str, Any]) -> None:
        loop = getattr(app.state, "loop", None)
        if loop is None or loop.is_closed():
            return
        message = {"event": event_name, "data": data}
        try:
            if loop is asyncio.get_event_loop_policy().get_event_loop() and loop.is_running():
                loop.create_task(ws_manager.broadcast(message))
            else:
                asyncio.run_coroutine_threadsafe(ws_manager.broadcast(message), loop)
        except RuntimeError:
            # Emitted from a non-async thread: hand off to the serving loop.
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast(message), loop)

    engine.add_listener(_broadcast_engine_event)

    scraper = MarketScraper()

    @app.get("/")
    def health_check():
        return {"status": "ok", "service": "Autonomous Trading Agent Engine"}

    @app.get("/agents")
    def list_agents():
        return engine.get_leaderboard()

    @app.get("/agents/{name}")
    def get_agent(name: str):
        agent = engine.agents.get(name)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return {
            "metrics": agent.calculate_metrics(),
            "bets": [b.to_dict() for b in agent.bets],
            "balance_history": agent.balance_history,
        }

    @app.post("/agents")
    def create_agent(req: AgentCreateRequest):
        try:
            mode = SurvivalMode(req.survival_mode.lower())
        except ValueError:
            mode = SurvivalMode.AGGRESSIVE

        agent = engine.create_agent(req.name, req.initial_bankroll, mode)
        return {"status": "created", "agent": agent.calculate_metrics()}

    @app.get("/markets")
    def get_markets():
        return scraper.scrape_polymarket()

    @app.post("/bets/place")
    def place_bet(req: PlaceBetRequest):
        bet = engine.place_bet(
            agent_name=req.agent_name,
            market=req.market,
            event=req.event,
            selection=req.selection,
            odds=req.odds,
            stake=req.stake,
            expected_value=req.expected_value,
        )
        if not bet:
            raise HTTPException(status_code=400, detail="Could not place bet. Check balance or agent status.")
        return bet.to_dict()

    @app.post("/bets/settle")
    def settle_bet(req: SettleBetRequest):
        bet = engine.settle_bet(
            agent_name=req.agent_name,
            bet_id=req.bet_id,
            won=req.won,
            is_cancelled=req.is_cancelled,
        )
        if not bet:
            raise HTTPException(status_code=400, detail="Could not settle bet.")
        return bet.to_dict()

    @app.post("/backtest/run")
    def run_backtest_endpoint(req: BacktestRunRequest):
        b_engine = BacktestEngine(initial_bankroll=req.initial_bankroll)
        if req.data_file:
            df = b_engine.load_historical_data(req.data_file)
        else:
            df = HistoricalDataLoader.generate_synthetic_data(num_records=200)

        def strat(state, row):
            edge = row["true_prob"] - (1.0 / row["odds"])
            if edge >= req.min_edge:
                b = row["odds"] - 1.0
                kelly = (b * row["true_prob"] - (1.0 - row["true_prob"])) / b if b > 0 else 0
                return max(0.0, state["bankroll"] * kelly * req.kelly_fraction)
            return 0.0

        results = b_engine.run_backtest(strat, df)
        return results

    @app.websocket("/ws/telemetry")
    async def websocket_telemetry(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    return app
