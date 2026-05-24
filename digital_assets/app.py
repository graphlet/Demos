"""Digital Assets Demo — Streamlit App.

Sections
--------
1. Crypto Portfolio Tracker
2. DeFi Yield Calculator (APR ↔ APY)
3. Tokenomics Modeller
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Digital Assets Demo",
    page_icon="🪙",
    layout="wide",
)

st.title("🪙 Digital Assets Demo")
st.markdown(
    "Interactive demos covering crypto portfolio tracking, DeFi yield calculations, "
    "and tokenomics modelling."
)

tab1, tab2, tab3 = st.tabs(
    ["Crypto Portfolio Tracker", "DeFi Yield Calculator", "Tokenomics Modeller"]
)

# ===========================================================================
# Tab 1 — Crypto Portfolio Tracker
# ===========================================================================
with tab1:
    st.header("Crypto Portfolio Tracker")
    st.markdown(
        "Enter your holdings and current prices below. "
        "Prices can be fetched live via [CoinGecko](https://www.coingecko.com/) "
        "or entered manually."
    )

    # Default portfolio
    DEFAULT_HOLDINGS: list[dict] = [
        {"Asset": "Bitcoin (BTC)", "Symbol": "BTC", "Quantity": 0.5, "Avg Cost ($)": 45000.0, "Current Price ($)": 67000.0},
        {"Asset": "Ethereum (ETH)", "Symbol": "ETH", "Quantity": 5.0, "Avg Cost ($)": 2800.0, "Current Price ($)": 3500.0},
        {"Asset": "Solana (SOL)", "Symbol": "SOL", "Quantity": 50.0, "Avg Cost ($)": 120.0, "Current Price ($)": 175.0},
        {"Asset": "Chainlink (LINK)", "Symbol": "LINK", "Quantity": 200.0, "Avg Cost ($)": 12.0, "Current Price ($)": 18.0},
        {"Asset": "Uniswap (UNI)", "Symbol": "UNI", "Quantity": 100.0, "Avg Cost ($)": 8.0, "Current Price ($)": 11.0},
    ]

    try:
        import requests  # noqa: PLC0415

        @st.cache_data(ttl=120)
        def fetch_prices(coin_ids: list[str]) -> dict[str, float]:
            ids = ",".join(coin_ids)
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return {k: v["usd"] for k, v in response.json().items()}

        COINGECKO_IDS = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "LINK": "chainlink",
            "UNI": "uniswap",
        }

        if st.button("🔄 Fetch live prices from CoinGecko"):
            try:
                live = fetch_prices(list(COINGECKO_IDS.values()))
                for row in DEFAULT_HOLDINGS:
                    cg_id = COINGECKO_IDS.get(row["Symbol"])
                    if cg_id and cg_id in live:
                        row["Current Price ($)"] = live[cg_id]
                st.success("Live prices loaded.")
            except Exception as exc:  # noqa: BLE001
                st.warning(f"Could not fetch live prices ({exc}). Using manual values.")
    except ImportError:
        st.info("Install `requests` for live price fetching.")

    portfolio_df = pd.DataFrame(DEFAULT_HOLDINGS)
    edited = st.data_editor(
        portfolio_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Quantity": st.column_config.NumberColumn(format="%.4f"),
            "Avg Cost ($)": st.column_config.NumberColumn(format="$%.2f"),
            "Current Price ($)": st.column_config.NumberColumn(format="$%.2f"),
        },
    )

    if not edited.empty:
        edited["Current Value ($)"] = edited["Quantity"] * edited["Current Price ($)"]
        edited["Cost Basis ($)"] = edited["Quantity"] * edited["Avg Cost ($)"]
        edited["P&L ($)"] = edited["Current Value ($)"] - edited["Cost Basis ($)"]
        edited["P&L (%)"] = (edited["P&L ($)"] / edited["Cost Basis ($)"].replace(0, np.nan)) * 100

        total_value = edited["Current Value ($)"].sum()
        total_cost = edited["Cost Basis ($)"].sum()
        total_pnl = edited["P&L ($)"].sum()
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Portfolio Value", f"${total_value:,.2f}")
        c2.metric("Total Cost Basis", f"${total_cost:,.2f}")
        c3.metric("Total P&L", f"${total_pnl:,.2f}", delta=f"{total_pnl_pct:.2f}%")
        c4.metric("Unrealised Return", f"{total_pnl_pct:.2f}%")

        # Allocation pie
        fig_pie = px.pie(
            edited,
            values="Current Value ($)",
            names="Asset",
            title="Portfolio Allocation by Current Value",
            hole=0.35,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

        # P&L bar chart
        fig_bar = px.bar(
            edited,
            x="Asset",
            y="P&L (%)",
            color="P&L (%)",
            color_continuous_scale=["#f44336", "#ffffff", "#4caf50"],
            color_continuous_midpoint=0,
            title="P&L (%) per Asset",
            text_auto=".1f",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ===========================================================================
# Tab 2 — DeFi Yield Calculator
# ===========================================================================
with tab2:
    st.header("DeFi Yield Calculator")
    st.markdown(
        "Compare **APR** (simple interest) vs **APY** (compound interest) "
        "and project earnings over time."
    )

    col_y1, col_y2 = st.columns([1, 2])

    with col_y1:
        principal = st.number_input("Principal ($)", value=10_000.0, min_value=1.0, step=500.0)
        apr = st.number_input("APR (%)", value=12.0, min_value=0.0, max_value=1000.0, step=0.5)
        compound_n = st.selectbox(
            "Compounding frequency",
            ["Daily (365×)", "Weekly (52×)", "Monthly (12×)", "Quarterly (4×)", "Annually (1×)"],
        )
        compound_map = {
            "Daily (365×)": 365,
            "Weekly (52×)": 52,
            "Monthly (12×)": 12,
            "Quarterly (4×)": 4,
            "Annually (1×)": 1,
        }
        n = compound_map[compound_n]
        horizon_years = st.slider("Investment horizon (years)", 1, 10, 3)
        reinvest = st.checkbox("Reinvest yield (auto-compound)", value=True)

    with col_y2:
        r = apr / 100
        apy = (1 + r / n) ** n - 1

        ya1, ya2 = st.columns(2)
        ya1.metric("APR", f"{apr:.2f}%")
        ya2.metric("APY", f"{apy * 100:.4f}%")

        years = np.arange(0, horizon_years + 1)
        if reinvest:
            values = principal * (1 + r / n) ** (n * years)
        else:
            values = principal * (1 + r * years)
        earnings = values - principal

        fig_yield = go.Figure()
        fig_yield.add_trace(go.Bar(x=years, y=earnings, name="Earnings ($)", marker_color="#4caf50"))
        fig_yield.add_trace(go.Scatter(x=years, y=values, mode="lines+markers", name="Total value ($)", yaxis="y2", line_color="#2196f3"))
        fig_yield.update_layout(
            title="Projected Portfolio Growth",
            xaxis_title="Year",
            yaxis_title="Earnings ($)",
            yaxis2=dict(title="Total value ($)", overlaying="y", side="right"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_yield, use_container_width=True)

        # Summary table
        rows = []
        for yr in years:
            v = principal * (1 + r / n) ** (n * yr) if reinvest else principal * (1 + r * yr)
            rows.append({"Year": int(yr), "Value ($)": round(v, 2), "Earnings ($)": round(v - principal, 2), "Return (%)": round((v / principal - 1) * 100, 2)})
        st.dataframe(pd.DataFrame(rows).set_index("Year"), use_container_width=True)

# ===========================================================================
# Tab 3 — Tokenomics Modeller
# ===========================================================================
with tab3:
    st.header("Tokenomics Modeller")
    st.markdown(
        "Model a token's supply schedule, stakeholder allocation, "
        "and implied market-cap projections."
    )

    col_t1, col_t2 = st.columns([1, 2])

    with col_t1:
        st.subheader("Supply & Vesting")
        max_supply = st.number_input("Max supply (tokens)", value=1_000_000_000, min_value=1_000, step=1_000_000, format="%d")
        initial_circ_pct = st.slider("Initial circulating supply (%)", 1, 80, 15)
        emission_years = st.slider("Full emission period (years)", 1, 10, 4)

        st.subheader("Allocation (%)")
        alloc_team = st.slider("Team & Advisors", 0, 40, 15)
        alloc_investors = st.slider("Investors / VCs", 0, 40, 20)
        alloc_ecosystem = st.slider("Ecosystem / Grants", 0, 50, 30)
        alloc_community = st.slider("Community / Public", 0, 60, 25)
        alloc_reserve = 100 - alloc_team - alloc_investors - alloc_ecosystem - alloc_community
        st.metric("Reserve / Treasury (auto)", f"{alloc_reserve}%", delta=None if alloc_reserve >= 0 else "⚠️ Over 100%")

        st.subheader("Price Assumption")
        token_price = st.number_input("Current token price ($)", value=0.10, min_value=0.00001, step=0.01, format="%.5f")

    with col_t2:
        # Allocation pie
        if alloc_reserve >= 0:
            alloc_labels = ["Team & Advisors", "Investors / VCs", "Ecosystem / Grants", "Community / Public", "Reserve / Treasury"]
            alloc_values = [alloc_team, alloc_investors, alloc_ecosystem, alloc_community, alloc_reserve]
            fig_alloc = px.pie(
                values=alloc_values,
                names=alloc_labels,
                title="Token Allocation",
                hole=0.35,
            )
            st.plotly_chart(fig_alloc, use_container_width=True)

        # Emission schedule — linear unlock after initial supply
        months = np.arange(0, emission_years * 12 + 1)
        initial_circ = max_supply * initial_circ_pct / 100
        full_supply = max_supply

        # Linear interpolation from initial to full supply over emission_years
        circulating = np.clip(
            initial_circ + (full_supply - initial_circ) * (months / (emission_years * 12)),
            initial_circ,
            full_supply,
        )
        market_cap = circulating * token_price
        fdv = full_supply * token_price

        fig_em = go.Figure()
        fig_em.add_trace(go.Scatter(
            x=months / 12,
            y=circulating / 1e6,
            mode="lines",
            name="Circulating supply (M)",
            fill="tozeroy",
            line_color="#7c4dff",
        ))
        fig_em.update_layout(
            title="Token Emission Schedule",
            xaxis_title="Year",
            yaxis_title="Circulating supply (millions)",
        )
        st.plotly_chart(fig_em, use_container_width=True)

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Market Cap (current circ.)", f"${market_cap[0]:,.0f}")
        mc2.metric("Fully Diluted Valuation (FDV)", f"${fdv:,.0f}")
        mc3.metric("FDV / Market Cap ratio", f"{fdv / market_cap[0]:.1f}×" if market_cap[0] > 0 else "—")

        # Market cap over emission schedule
        fig_mc = px.line(
            x=months / 12,
            y=market_cap,
            labels={"x": "Year", "y": "Market cap ($)"},
            title="Implied Market Cap over Emission Schedule",
        )
        fig_mc.add_hline(y=fdv, line_dash="dash", line_color="red", annotation_text="FDV")
        st.plotly_chart(fig_mc, use_container_width=True)
