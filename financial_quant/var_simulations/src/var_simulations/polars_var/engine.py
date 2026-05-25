from __future__ import annotations

from pathlib import Path

import polars as pl

from var_simulations.polars_var.loader import scan_portfolio, scan_returns
from var_simulations.polars_var.report import VaRResult


def build_pnl_pipeline(
    portfolio_lf: pl.LazyFrame,
    returns_lf: pl.LazyFrame,
) -> pl.LazyFrame:
    # Keep portfolio valuation in the lazy graph so Polars can optimize projections.
    portfolio_with_value = portfolio_lf.with_columns(
        (pl.col("quantity") * pl.col("current_price")).alias("mkt_value")
    )

    position_pnl = returns_lf.join(
        portfolio_with_value.select("ticker", "mkt_value", "desk", "book", "sector"),
        on="ticker",
        how="inner",
    ).with_columns((pl.col("return") * pl.col("mkt_value")).alias("position_pnl"))

    return position_pnl.group_by("date", "desk", "book", "sector").agg(
        pl.col("position_pnl").sum().alias("group_pnl"),
        pl.col("mkt_value").sum().alias("group_nav"),
    )


def _compute_var_es(pnl_df: pl.DataFrame, confidence: float) -> tuple[float, float]:
    q = 1.0 - confidence
    metrics = pnl_df.select(
        (-pl.col("pnl").quantile(q, interpolation="lower")).alias("var"),
        (
            -pl.col("pnl")
            .filter(pl.col("pnl") <= pl.col("pnl").quantile(q, interpolation="lower"))
            .mean()
        ).alias("es"),
    )
    return float(metrics["var"][0] or 0.0), float(metrics["es"][0] or 0.0)


def _compute_group_metrics(
    group_date_pnl: pl.DataFrame,
    group_col: str,
    confidence_levels: list[float],
) -> tuple[
    dict[str, dict[float, float]],
    dict[str, dict[float, float]],
    dict[str, float],
]:
    group_var: dict[str, dict[float, float]] = {}
    group_es: dict[str, dict[float, float]] = {}

    nav_df = group_date_pnl.group_by(group_col).agg(pl.col("nav").first().alias("nav"))
    group_nav = {
        str(row[group_col]): float(row["nav"]) for row in nav_df.iter_rows(named=True)
    }

    for confidence in confidence_levels:
        q = 1.0 - confidence
        metrics = group_date_pnl.group_by(group_col).agg(
            (-pl.col("pnl").quantile(q, interpolation="lower")).alias("var"),
            (
                -pl.col("pnl")
                .filter(pl.col("pnl") <= pl.col("pnl").quantile(q, interpolation="lower"))
                .mean()
            ).alias("es"),
        )

        for row in metrics.iter_rows(named=True):
            group = str(row[group_col])
            group_var.setdefault(group, {})[confidence] = float(row["var"] or 0.0)
            group_es.setdefault(group, {})[confidence] = float(row["es"] or 0.0)

    return group_var, group_es, group_nav


def run_var_analysis(data_dir: Path, confidence_levels: list[float]) -> VaRResult:
    portfolio_lf = scan_portfolio(data_dir)
    returns_lf = scan_returns(data_dir)

    group_pnl_df = build_pnl_pipeline(portfolio_lf, returns_lf).collect()

    portfolio_pnl_df = group_pnl_df.group_by("date").agg(
        pl.col("group_pnl").sum().alias("pnl")
    )
    portfolio_sorted = portfolio_pnl_df.sort("pnl")

    portfolio_var: dict[float, float] = {}
    portfolio_es: dict[float, float] = {}
    for confidence in confidence_levels:
        var_value, es_value = _compute_var_es(portfolio_sorted, confidence)
        portfolio_var[confidence] = var_value
        portfolio_es[confidence] = es_value

    desk_date_pnl = group_pnl_df.group_by("date", "desk").agg(
        pl.col("group_pnl").sum().alias("pnl"),
        pl.col("group_nav").sum().alias("nav"),
    )
    sector_date_pnl = group_pnl_df.group_by("date", "sector").agg(
        pl.col("group_pnl").sum().alias("pnl"),
        pl.col("group_nav").sum().alias("nav"),
    )
    book_date_pnl = group_pnl_df.group_by("date", "book").agg(
        pl.col("group_pnl").sum().alias("pnl"),
        pl.col("group_nav").sum().alias("nav"),
    )

    desk_var, desk_es, desk_nav = _compute_group_metrics(
        desk_date_pnl, "desk", confidence_levels
    )
    sector_var, sector_es, sector_nav = _compute_group_metrics(
        sector_date_pnl, "sector", confidence_levels
    )
    book_var, book_es, book_nav = _compute_group_metrics(
        book_date_pnl, "book", confidence_levels
    )

    return VaRResult(
        nav=float(sum(desk_nav.values())),
        scenario_count=portfolio_sorted.height,
        confidence_levels=confidence_levels,
        portfolio_var=portfolio_var,
        portfolio_es=portfolio_es,
        desk_var=desk_var,
        desk_es=desk_es,
        desk_nav=desk_nav,
        sector_var=sector_var,
        sector_es=sector_es,
        sector_nav=sector_nav,
        book_var=book_var,
        book_es=book_es,
        book_nav=book_nav,
        pnl_scenarios=portfolio_sorted.get_column("pnl").to_list(),
        raw_pnl_frame=portfolio_sorted.rename({"pnl": "portfolio_pnl"}),
    )
