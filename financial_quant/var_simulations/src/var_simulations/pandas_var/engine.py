from __future__ import annotations

from pathlib import Path

import pandas as pd

from var_simulations.pandas_var.loader import load_portfolio, load_returns
from var_simulations.pandas_var.report import VaRResult


def compute_market_values(portfolio_df: pd.DataFrame) -> pd.DataFrame:
    mkt_values: list[float] = []
    for _, row in portfolio_df.iterrows():
        mkt_values.append(float(row["quantity"]) * float(row["current_price"]))

    portfolio_df = portfolio_df.copy()
    portfolio_df["mkt_value"] = mkt_values
    return portfolio_df


def build_scenario_matrix(returns_df: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    pivot = returns_df.pivot(index="date", columns="ticker", values="return")
    return pivot.reindex(columns=tickers, fill_value=0.0)


def compute_pnl_scenarios(scenario_matrix: pd.DataFrame, mkt_values: list[float]) -> list[float]:
    pnl_scenarios: list[float] = []
    for date in scenario_matrix.index:
        day_returns = scenario_matrix.loc[date]
        daily_pnl = 0.0
        for ticker_return, mkt_val in zip(day_returns, mkt_values):
            daily_pnl += float(ticker_return) * float(mkt_val)
        pnl_scenarios.append(daily_pnl)
    return pnl_scenarios


def compute_var(pnl_scenarios: list[float], confidence: float) -> float:
    sorted_pnl = sorted(pnl_scenarios)
    cutoff_idx = int((1.0 - confidence) * len(sorted_pnl))
    cutoff_idx = min(max(cutoff_idx, 0), max(len(sorted_pnl) - 1, 0))
    return -sorted_pnl[cutoff_idx] if sorted_pnl else 0.0


def compute_es(pnl_scenarios: list[float], confidence: float) -> float:
    sorted_pnl = sorted(pnl_scenarios)
    cutoff_idx = int((1.0 - confidence) * len(sorted_pnl))
    tail = sorted_pnl[:cutoff_idx]
    return -sum(tail) / len(tail) if tail else 0.0


def _compute_risk_maps(
    pnl_scenarios: list[float], confidence_levels: list[float]
) -> tuple[dict[float, float], dict[float, float]]:
    var_map: dict[float, float] = {}
    es_map: dict[float, float] = {}
    for confidence in confidence_levels:
        var_map[confidence] = compute_var(pnl_scenarios, confidence)
        es_map[confidence] = compute_es(pnl_scenarios, confidence)
    return var_map, es_map


def _run_group_breakdown(
    portfolio_df: pd.DataFrame,
    scenario_matrix: pd.DataFrame,
    group_column: str,
    confidence_levels: list[float],
) -> tuple[
    dict[str, dict[float, float]],
    dict[str, dict[float, float]],
    dict[str, float],
]:
    group_var: dict[str, dict[float, float]] = {}
    group_es: dict[str, dict[float, float]] = {}
    group_nav: dict[str, float] = {}

    for group in portfolio_df[group_column].dropna().unique().tolist():
        mask = portfolio_df[group_column] == group
        sub_tickers = portfolio_df.loc[mask, "ticker"].tolist()
        sub_mkt_vals = portfolio_df.loc[mask, "mkt_value"].tolist()
        sub_matrix = scenario_matrix[sub_tickers]
        sub_pnl = compute_pnl_scenarios(sub_matrix, sub_mkt_vals)
        var_map, es_map = _compute_risk_maps(sub_pnl, confidence_levels)

        group_name = str(group)
        group_var[group_name] = var_map
        group_es[group_name] = es_map
        group_nav[group_name] = float(sum(sub_mkt_vals))

    return group_var, group_es, group_nav


def run_var_analysis(data_dir: Path, confidence_levels: list[float]) -> VaRResult:
    portfolio = load_portfolio(data_dir)
    returns = load_returns(data_dir)

    portfolio = compute_market_values(portfolio)
    tickers = portfolio["ticker"].tolist()
    scenario_matrix = build_scenario_matrix(returns, tickers)

    all_mkt_values = portfolio["mkt_value"].tolist()
    portfolio_pnl = compute_pnl_scenarios(scenario_matrix, all_mkt_values)
    portfolio_var, portfolio_es = _compute_risk_maps(portfolio_pnl, confidence_levels)

    desk_var, desk_es, desk_nav = _run_group_breakdown(
        portfolio, scenario_matrix, "desk", confidence_levels
    )
    sector_var, sector_es, sector_nav = _run_group_breakdown(
        portfolio, scenario_matrix, "sector", confidence_levels
    )
    book_var, book_es, book_nav = _run_group_breakdown(
        portfolio, scenario_matrix, "book", confidence_levels
    )

    return VaRResult(
        nav=float(sum(all_mkt_values)),
        scenario_count=len(portfolio_pnl),
        confidence_levels=confidence_levels,
        portfolio_var=portfolio_var,
        portfolio_es=portfolio_es,
        desk_var=desk_var,
        desk_es=desk_es,
        sector_var=sector_var,
        sector_es=sector_es,
        book_var=book_var,
        book_es=book_es,
        desk_nav=desk_nav,
        sector_nav=sector_nav,
        book_nav=book_nav,
        pnl_scenarios=sorted(portfolio_pnl),
    )
