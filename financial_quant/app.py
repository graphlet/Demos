"""Financial Quantitative Calculator — Streamlit Demo App.

Sections
--------
1. Black-Scholes Options Pricing & Greeks
2. Portfolio Risk Metrics
3. Monte Carlo Asset-Price Simulation
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy.stats import norm

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Financial Quant Calculator",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Financial Quant Calculator")
st.markdown(
    "Interactive demos for options pricing, portfolio risk metrics, "
    "and Monte Carlo simulation."
)

tab1, tab2, tab3 = st.tabs(
    ["Black-Scholes & Greeks", "Portfolio Risk Metrics", "Monte Carlo Simulation"]
)

# ===========================================================================
# Helper functions
# ===========================================================================

def black_scholes(S: float, K: float, T: float, r: float, sigma: float, option: str = "call") -> float:
    """Compute Black-Scholes price for a European option."""
    if T <= 0 or sigma <= 0:
        intrinsic = max(S - K, 0) if option == "call" else max(K - S, 0)
        return intrinsic
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option == "call":
        price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return price


def greeks(S: float, K: float, T: float, r: float, sigma: float, option: str = "call") -> dict:
    """Compute the five standard Greeks."""
    if T <= 0 or sigma <= 0:
        return {"delta": float("nan"), "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    nd1_pdf = norm.pdf(d1)
    sqrt_T = math.sqrt(T)
    if option == "call":
        delta = norm.cdf(d1)
        rho = K * T * math.exp(-r * T) * norm.cdf(d2) / 100
        theta = (
            -S * nd1_pdf * sigma / (2 * sqrt_T)
            - r * K * math.exp(-r * T) * norm.cdf(d2)
        ) / 365
    else:
        delta = norm.cdf(d1) - 1
        rho = -K * T * math.exp(-r * T) * norm.cdf(-d2) / 100
        theta = (
            -S * nd1_pdf * sigma / (2 * sqrt_T)
            + r * K * math.exp(-r * T) * norm.cdf(-d2)
        ) / 365
    gamma = nd1_pdf / (S * sigma * sqrt_T)
    vega = S * nd1_pdf * sqrt_T / 100
    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega, "rho": rho}


# ===========================================================================
# Tab 1 — Black-Scholes & Greeks
# ===========================================================================
with tab1:
    st.header("Black-Scholes Options Pricing & Greeks")

    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.subheader("Inputs")
        S = st.number_input("Spot price (S)", value=100.0, min_value=0.01, step=1.0)
        K = st.number_input("Strike price (K)", value=100.0, min_value=0.01, step=1.0)
        T = st.number_input("Time to expiry (years)", value=1.0, min_value=0.001, max_value=10.0, step=0.05)
        r = st.number_input("Risk-free rate (%)", value=5.0, min_value=0.0, max_value=30.0, step=0.1) / 100
        sigma = st.number_input("Volatility / σ (%)", value=20.0, min_value=0.1, max_value=200.0, step=0.5) / 100
        option_type = st.radio("Option type", ["call", "put"], horizontal=True)

    with col_right:
        call_price = black_scholes(S, K, T, r, sigma, "call")
        put_price = black_scholes(S, K, T, r, sigma, "put")
        selected_price = black_scholes(S, K, T, r, sigma, option_type)
        g = greeks(S, K, T, r, sigma, option_type)

        st.subheader("Prices")
        m1, m2 = st.columns(2)
        m1.metric("Call price", f"${call_price:.4f}")
        m2.metric("Put price", f"${put_price:.4f}")

        st.subheader("Greeks")
        gm1, gm2, gm3, gm4, gm5 = st.columns(5)
        gm1.metric("Delta (Δ)", f"{g['delta']:.4f}")
        gm2.metric("Gamma (Γ)", f"{g['gamma']:.4f}")
        gm3.metric("Theta (Θ) /day", f"{g['theta']:.4f}")
        gm4.metric("Vega (ν) /1%", f"{g['vega']:.4f}")
        gm5.metric("Rho (ρ) /1%", f"{g['rho']:.4f}")

        # Sensitivity chart — price vs spot
        spots = np.linspace(max(S * 0.5, 0.01), S * 1.5, 200)
        prices = [black_scholes(s, K, T, r, sigma, option_type) for s in spots]
        fig = px.line(
            x=spots,
            y=prices,
            labels={"x": "Spot price ($)", "y": f"{option_type.capitalize()} price ($)"},
            title=f"{option_type.capitalize()} price vs Spot (K={K}, T={T:.2f}y, σ={sigma*100:.0f}%)",
        )
        fig.add_vline(x=S, line_dash="dash", line_color="orange", annotation_text="Current S")
        fig.add_vline(x=K, line_dash="dot", line_color="red", annotation_text="Strike K")
        st.plotly_chart(fig, use_container_width=True)

# ===========================================================================
# Tab 2 — Portfolio Risk Metrics
# ===========================================================================
with tab2:
    st.header("Portfolio Risk Metrics")
    st.markdown(
        "Enter a comma-separated list of **daily returns** (e.g. `0.01, -0.005, 0.02, …`) "
        "or generate a random series below."
    )

    col_a, col_b = st.columns([1, 2])
    with col_a:
        use_random = st.checkbox("Generate random returns", value=True)
        if use_random:
            n_days = st.slider("Number of trading days", 50, 1000, 252)
            mu_input = st.number_input("Daily drift (%)", value=0.05, step=0.01) / 100
            sig_input = st.number_input("Daily volatility (%)", value=1.0, step=0.1) / 100
            rng = np.random.default_rng(42)
            daily_returns = rng.normal(mu_input, sig_input, n_days)
        else:
            raw = st.text_area("Daily returns (comma-separated)", value="0.01,-0.005,0.02,-0.01,0.015")
            try:
                daily_returns = np.array([float(x.strip()) for x in raw.split(",") if x.strip()])
            except ValueError:
                st.error("Could not parse returns — check your input.")
                daily_returns = np.array([])

        rf_rate = st.number_input("Risk-free rate (annual, %)", value=5.0, step=0.1) / 100
        var_conf = st.slider("VaR confidence level (%)", 90, 99, 95)

    with col_b:
        if daily_returns.size >= 2:
            ann_return = np.mean(daily_returns) * 252
            ann_vol = np.std(daily_returns, ddof=1) * math.sqrt(252)
            sharpe = (ann_return - rf_rate) / ann_vol if ann_vol > 0 else float("nan")
            var = np.percentile(daily_returns, 100 - var_conf)
            cvar = daily_returns[daily_returns <= var].mean() if (daily_returns <= var).any() else var
            max_dd_series = pd.Series((1 + daily_returns).cumprod())
            rolling_max = max_dd_series.cummax()
            drawdown = (max_dd_series - rolling_max) / rolling_max
            max_dd = drawdown.min()

            rm1, rm2, rm3 = st.columns(3)
            rm1.metric("Annualised Return", f"{ann_return*100:.2f}%")
            rm2.metric("Annualised Volatility", f"{ann_vol*100:.2f}%")
            rm3.metric("Sharpe Ratio", f"{sharpe:.3f}")
            rm4, rm5, rm6 = st.columns(3)
            rm4.metric(f"VaR {var_conf}% (daily)", f"{var*100:.2f}%")
            rm5.metric(f"CVaR {var_conf}% (daily)", f"{cvar*100:.2f}%")
            rm6.metric("Max Drawdown", f"{max_dd*100:.2f}%")

            # Equity curve
            equity = (1 + daily_returns).cumprod()
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(y=equity, mode="lines", name="Equity curve", line_color="#2196f3"))
            fig2.update_layout(
                title="Equity Curve (starting value = 1.0)",
                xaxis_title="Trading day",
                yaxis_title="Portfolio value",
            )
            st.plotly_chart(fig2, use_container_width=True)

            # Returns histogram
            fig3 = px.histogram(
                daily_returns * 100,
                nbins=40,
                labels={"value": "Daily return (%)"},
                title="Distribution of Daily Returns",
            )
            fig3.add_vline(x=var * 100, line_color="red", line_dash="dash", annotation_text=f"VaR {var_conf}%")
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("Enter at least 2 return values to see metrics.")

# ===========================================================================
# Tab 3 — Monte Carlo Simulation
# ===========================================================================
with tab3:
    st.header("Monte Carlo Asset-Price Simulation")
    st.markdown(
        "Simulate future price paths using **Geometric Brownian Motion** "
        "and estimate option payoffs."
    )

    col_mc_l, col_mc_r = st.columns([1, 2])
    with col_mc_l:
        mc_S0 = st.number_input("Initial price (S₀)", value=100.0, min_value=0.01, step=1.0, key="mc_s0")
        mc_mu = st.number_input("Annual drift μ (%)", value=8.0, step=0.5, key="mc_mu") / 100
        mc_sigma = st.number_input("Annual volatility σ (%)", value=20.0, min_value=0.1, step=0.5, key="mc_sigma") / 100
        mc_T = st.number_input("Time horizon (years)", value=1.0, min_value=0.1, max_value=10.0, step=0.1, key="mc_T")
        mc_steps = st.slider("Time steps", 50, 500, 252, key="mc_steps")
        mc_paths = st.slider("Number of paths", 10, 500, 100, key="mc_paths")
        mc_K = st.number_input("Call strike for payoff estimate", value=100.0, min_value=0.01, step=1.0, key="mc_K")
        mc_r = st.number_input("Risk-free rate (%)", value=5.0, step=0.1, key="mc_r") / 100

    with col_mc_r:
        dt = mc_T / mc_steps
        rng2 = np.random.default_rng(0)
        Z = rng2.standard_normal((mc_paths, mc_steps))
        # Visualisation paths use real-world drift μ
        increments = (mc_mu - 0.5 * mc_sigma**2) * dt + mc_sigma * math.sqrt(dt) * Z
        log_prices = np.log(mc_S0) + np.cumsum(increments, axis=1)
        paths = np.exp(log_prices)
        time_axis = np.linspace(dt, mc_T, mc_steps)

        # Option pricing uses risk-neutral paths (drift = r) on the same random draws
        rn_increments = (mc_r - 0.5 * mc_sigma**2) * dt + mc_sigma * math.sqrt(dt) * Z
        rn_log_prices = np.log(mc_S0) + np.cumsum(rn_increments, axis=1)
        rn_final_prices = np.exp(rn_log_prices[:, -1])
        final_prices = paths[:, -1]

        fig_mc = go.Figure()
        for i in range(min(mc_paths, 100)):
            fig_mc.add_trace(
                go.Scatter(
                    x=np.insert(time_axis, 0, 0),
                    y=np.insert(paths[i], 0, mc_S0),
                    mode="lines",
                    line=dict(width=0.7),
                    opacity=0.4,
                    showlegend=False,
                )
            )
        # Mean path
        mean_path = np.insert(np.exp(np.log(mc_S0) + (mc_mu - 0.5 * mc_sigma**2) * np.linspace(dt, mc_T, mc_steps)), 0, mc_S0)
        fig_mc.add_trace(
            go.Scatter(
                x=np.insert(time_axis, 0, 0),
                y=mean_path,
                mode="lines",
                line=dict(color="orange", width=2),
                name="Expected path",
            )
        )
        fig_mc.update_layout(
            title=f"GBM Price Paths (μ={mc_mu*100:.0f}%, σ={mc_sigma*100:.0f}%, {mc_paths} paths)",
            xaxis_title="Time (years)",
            yaxis_title="Price ($)",
        )
        st.plotly_chart(fig_mc, use_container_width=True)

        # Payoff / stats row — pricing uses risk-neutral paths
        payoffs = np.maximum(rn_final_prices - mc_K, 0)
        mc_call_price = math.exp(-mc_r * mc_T) * np.mean(payoffs)
        bs_price = black_scholes(mc_S0, mc_K, mc_T, mc_r, mc_sigma, "call")

        sm1, sm2, sm3, sm4 = st.columns(4)
        sm1.metric("MC call price (risk-neutral)", f"${mc_call_price:.4f}")
        sm2.metric("BS call price", f"${bs_price:.4f}")
        sm3.metric("Median final price", f"${np.median(final_prices):.2f}")
        sm4.metric("95th pct final price", f"${np.percentile(final_prices, 95):.2f}")

        fig_dist = px.histogram(
            final_prices,
            nbins=40,
            labels={"value": "Final price ($)"},
            title="Distribution of Final Prices",
        )
        fig_dist.add_vline(x=mc_K, line_dash="dash", line_color="red", annotation_text="Strike K")
        fig_dist.add_vline(x=mc_S0, line_dash="dot", line_color="green", annotation_text="S₀")
        st.plotly_chart(fig_dist, use_container_width=True)
