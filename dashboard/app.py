"""
Interactive Streamlit Dashboard for Autonomous Paper Trading Simulation & Analysis.
"""
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from trading.paper_engine import PaperTradingEngine, SurvivalMode, BetStatus
from analysis.scraper import MarketScraper
from backtest.simulator import BacktestEngine
from backtest.historical_data import HistoricalDataLoader


def run_dashboard(port: int = 8501):
    """Entry point for Streamlit dashboard."""
    st.set_page_config(
        page_title="Autonomous Trading Agent Monitor",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Custom styling
    st.markdown("""
        <style>
        .metric-card {
            background-color: #1e2130;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #2e344e;
        }
        .alive-badge {
            color: #00ff88;
            font-weight: bold;
        }
        .dead-badge {
            color: #ff3366;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("🤖 Autonomous Trading Agent Monitor & Lab")
    st.caption("Real-time telemetry, paper trading simulation, survival circuit breakers, and backtesting")

    # Session State Initialization
    if "engine" not in st.session_state:
        engine = PaperTradingEngine(initial_bankroll=100.0)
        # Create default demo bots
        engine.create_agent("AlphaKelly_Bot", 100.0, SurvivalMode.AGGRESSIVE)
        engine.create_agent("Conservative_Bot", 100.0, SurvivalMode.CONSERVATIVE)
        engine.create_agent("Terminal_Bot", 100.0, SurvivalMode.TERMINAL)
        st.session_state.engine = engine

    engine: PaperTradingEngine = st.session_state.engine

    # Sidebar
    st.sidebar.header("🕹️ Agent Control Panel")
    selected_agent_name = st.sidebar.selectbox("Select Active Agent", list(engine.agents.keys()))
    current_agent = engine.agents.get(selected_agent_name)

    st.sidebar.divider()
    st.sidebar.subheader("➕ Create New Agent")
    new_name = st.sidebar.text_input("Agent Name", value=f"Bot_{len(engine.agents)+1}")
    new_bankroll = st.sidebar.number_input("Initial Bankroll ($)", min_value=10.0, max_value=100000.0, value=100.0)
    new_mode = st.sidebar.selectbox("Survival Circuit Mode", ["Aggressive (50%)", "Conservative (80%)", "Terminal (100%)"])

    if st.sidebar.button("Deploy Agent", use_container_width=True):
        mode_enum = (
            SurvivalMode.CONSERVATIVE if "Conservative" in new_mode
            else SurvivalMode.TERMINAL if "Terminal" in new_mode
            else SurvivalMode.AGGRESSIVE
        )
        engine.create_agent(new_name, new_bankroll, mode_enum)
        st.sidebar.success(f"Agent '{new_name}' deployed successfully!")
        st.rerun()

    # Main Tabs
    tab_live, tab_backtest, tab_market, tab_agents, tab_survival = st.tabs([
        "📊 Live Monitor",
        "🧪 Strategy Backtest",
        "🌐 Market Analysis",
        "🏆 Leaderboard",
        "⚡ Survival Circuit Breakers",
    ])

    # 1. LIVE MONITOR
    with tab_live:
        if current_agent:
            metrics = current_agent.calculate_metrics()
            
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Current Bankroll", f"${metrics['current_bankroll']:.2f}", f"{metrics['roi_percent']:+.1f}%")
            c2.metric("Win Rate", f"{metrics['win_rate']*100:.1f}%", f"{metrics['won_bets']}W / {metrics['lost_bets']}L")
            c3.metric("Profit / Loss", f"${metrics['total_profit']:+.2f}")
            c4.metric("Max Drawdown", f"{metrics['current_drawdown']*100:.1f}%")
            
            status_html = '<span class="alive-badge">● ACTIVE (ALIVE)</span>' if metrics['is_alive'] else f'<span class="dead-badge">● TERMINATED</span>'
            c5.markdown(f"**Status**<br>{status_html}", unsafe_allow_html=True)

            st.divider()

            # Actions: Trigger simulated cycle
            col_act1, col_act2, col_act3 = st.columns([1, 1, 2])
            with col_act1:
                if st.button("▶️ Run Autonomous Cycle", use_container_width=True):
                    scraper = MarketScraper()
                    markets = scraper.scrape_polymarket()
                    if markets and current_agent.is_alive:
                        m = markets[0]
                        stake = round(current_agent.current_bankroll * 0.05, 2)
                        if stake >= 1.0:
                            b = engine.place_bet(
                                agent_name=selected_agent_name,
                                market=m.source,
                                event=m.event_name,
                                selection="Yes",
                                odds=m.odds_home,
                                stake=stake,
                                expected_value=0.04,
                            )
                            st.toast(f"Placed bet on {m.event_name} for ${stake:.2f}")
                            st.rerun()
            with col_act2:
                if st.button("🎲 Auto-Settle Pending Bets", use_container_width=True):
                    for bet in list(current_agent.bets):
                        if bet.status == BetStatus.PENDING:
                            won = np.random.random() < (1.0 / bet.odds)
                            engine.settle_bet(selected_agent_name, bet.id, won=won)
                    st.toast("Settled open bets.")
                    st.rerun()

            # Bankroll Progression Chart
            st.subheader("📈 Bankroll History")
            history = current_agent.balance_history
            if history:
                df_hist = pd.DataFrame(history)
                fig_equity = px.line(
                    df_hist,
                    x="timestamp",
                    y="bankroll",
                    title=f"Equity Progression: {selected_agent_name}",
                    markers=True,
                )
                fig_equity.add_hline(
                    y=current_agent.initial_bankroll,
                    line_dash="dash",
                    line_color="gray",
                    annotation_text="Initial Capital",
                )
                
                # Death threshold line
                thresh_ratio = 0.8 if current_agent.survival_mode == SurvivalMode.CONSERVATIVE else (1.0 if current_agent.survival_mode == SurvivalMode.TERMINAL else 0.5)
                fig_equity.add_hline(
                    y=current_agent.initial_bankroll * thresh_ratio,
                    line_dash="dot",
                    line_color="red",
                    annotation_text=f"Kill Threshold ({thresh_ratio*100:.0f}%)",
                )
                st.plotly_chart(fig_equity, use_container_width=True)

            # Bets Table
            st.subheader("📋 Bet Ledger")
            if current_agent.bets:
                df_bets = pd.DataFrame([b.to_dict() for b in current_agent.bets])
                st.dataframe(df_bets[["id", "event", "selection", "odds", "stake", "status", "pnl", "timestamp"]], use_container_width=True)
            else:
                st.info("No bets placed yet for this agent.")

    # 2. STRATEGY BACKTEST
    with tab_backtest:
        st.header("🧪 Strategy Backtesting & Monte Carlo Lab")
        st.write("Evaluate quantitative edge and Kelly fraction strategies against historical and synthetic market distributions.")

        b_col1, b_col2, b_col3 = st.columns(3)
        b_initial = b_col1.number_input("Backtest Initial Capital ($)", 50.0, 100000.0, 100.0)
        b_kelly = b_col2.slider("Kelly Fraction", 0.05, 1.0, 0.25, step=0.05)
        b_edge = b_col3.slider("Minimum Edge Threshold (%)", 0.0, 10.0, 2.0, step=0.5) / 100.0

        uploaded_csv = st.file_uploader("Upload Historical Odds CSV (Optional)", type=["csv"])

        if st.button("🚀 Run Backtest Simulation", type="primary"):
            b_engine = BacktestEngine(initial_bankroll=b_initial)
            if uploaded_csv:
                df_data = pd.read_csv(uploaded_csv)
            else:
                df_data = HistoricalDataLoader.generate_synthetic_data(num_records=300)

            def backtest_strat(state, row):
                edge = row["true_prob"] - (1.0 / row["odds"])
                if edge >= b_edge:
                    b = row["odds"] - 1.0
                    if b > 0:
                        raw_k = (b * row["true_prob"] - (1.0 - row["true_prob"])) / b
                        target_stake = state["bankroll"] * raw_k * b_kelly
                        return max(0.0, min(target_stake, state["bankroll"] * 0.08))
                return 0.0

            res = b_engine.run_backtest(backtest_strat, df_data)
            mc_res = b_engine.monte_carlo_simulation(backtest_strat, df_data, n_simulations=300)

            st.success("Simulation Completed!")

            # Metric Cards
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Final Bankroll", f"${res['final_bankroll']:.2f}", f"{res['roi_percent']:+.1f}%")
            r2.metric("Win Rate", f"{res['win_rate']*100:.1f}%", f"{res['won_bets']}W / {res['lost_bets']}L")
            r3.metric("Sharpe Ratio", f"{res['sharpe_ratio']:.2f}")
            r4.metric("Max Drawdown", f"{res['max_drawdown']*100:.1f}%")

            # Charts
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(y=res["equity_curve"], mode="lines", name="Equity Curve", line=dict(color="#00ff88", width=2)))
            fig_eq.update_layout(title="Simulated Portfolio Trajectory", xaxis_title="Trade Number", yaxis_title="Bankroll ($)")
            st.plotly_chart(fig_eq, use_container_width=True)

            # Monte Carlo Summary
            st.subheader("🎲 Monte Carlo Risk Distribution (300 Iterations)")
            mc_col1, mc_col2, mc_col3, mc_col4 = st.columns(4)
            mc_col1.metric("Mean Final Capital", f"${mc_res['mean_final_bankroll']:.2f}")
            mc_col2.metric("Median Final Capital", f"${mc_res['median_final_bankroll']:.2f}")
            mc_col3.metric("Probability of Profit", f"{mc_res['probability_of_profit']*100:.1f}%")
            mc_col4.metric("Probability of Ruin (<50%)", f"{mc_res['probability_of_ruin']*100:.1f}%")

    # 3. MARKET ANALYSIS
    with tab_market:
        st.header("🌐 Prediction Markets & Odds Perception")
        scraper = MarketScraper()
        markets = scraper.scrape_polymarket()

        st.subheader("📡 Live Streamed Markets")
        market_rows = []
        for m in markets:
            implied_home = round(1.0 / m.odds_home * 100, 1)
            implied_away = round(1.0 / m.odds_away * 100, 1)
            vig = round((implied_home + implied_away) - 100.0, 1)
            market_rows.append({
                "Event": m.event_name,
                "Category": m.category,
                "Yes Odds": m.odds_home,
                "No Odds": m.odds_away,
                "Yes Implied (%)": f"{implied_home}%",
                "No Implied (%)": f"{implied_away}%",
                "Vig Overround (%)": f"{vig}%",
                "24h Volume": f"${m.volume:,.0f}" if m.volume else "$0",
            })
        st.dataframe(pd.DataFrame(market_rows), use_container_width=True)

        # Expected Value distribution bar chart
        if markets:
            ev_data = [
                {"Event": m.event_name[:25], "EV_Yes": round(((0.55 * m.odds_home) - 1.0) * 100, 1)}
                for m in markets
            ]
            df_ev = pd.DataFrame(ev_data)
            fig_bar = px.bar(
                df_ev,
                x="Event",
                y="EV_Yes",
                color="EV_Yes",
                color_continuous_scale=["red", "yellow", "green"],
                title="Model Estimated Expected Value (Edge %) by Market",
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    # 4. LEADERBOARD
    with tab_agents:
        st.header("🏆 Agent Performance Leaderboard")
        leaderboard = engine.get_leaderboard()
        if leaderboard:
            df_lead = pd.DataFrame(leaderboard)
            st.dataframe(df_lead[[
                "name", "is_alive", "current_bankroll", "total_profit", "roi_percent",
                "win_rate", "total_bets", "profit_factor", "current_drawdown", "kill_reason"
            ]], use_container_width=True)
        else:
            st.info("No agents active.")

    # 5. SURVIVAL CIRCUIT BREAKERS
    with tab_survival:
        st.header("⚡ Circuit Breaker & Survival Mechanics")
        st.markdown("""
        The autonomous framework implements strict survival constraints:
        - **Aggressive Mode**: Agent is terminated if bankroll drops below **50%** of starting capital.
        - **Conservative Mode**: Agent is terminated if bankroll drops below **80%** or max drawdown exceeds **20%**.
        - **Terminal Mode**: Zero tolerance for ruin — any breach below initial capital or multiple losses terminates the agent immediately.
        """)

        st.subheader("Simulate Shock Loss")
        shock_agent = st.selectbox("Select Agent to Shock", list(engine.agents.keys()), key="shock_select")
        loss_pct = st.slider("Drain Bankroll (%)", 10, 90, 55)

        if st.button("⚠️ Apply Shock Loss"):
            target_agent = engine.agents.get(shock_agent)
            if target_agent and target_agent.is_alive:
                drain_amount = target_agent.current_bankroll * (loss_pct / 100.0)
                target_agent.current_bankroll -= drain_amount
                target_agent.check_survival()
                st.warning(f"Drained ${drain_amount:.2f} from {shock_agent}. Survival checked.")
                st.rerun()


if __name__ == "__main__":
    run_dashboard()
