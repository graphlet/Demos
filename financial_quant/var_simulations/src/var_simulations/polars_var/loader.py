from __future__ import annotations

from pathlib import Path

import polars as pl


def scan_portfolio(data_dir: Path) -> pl.LazyFrame:
    return pl.scan_parquet(data_dir / "portfolio.parquet")


def scan_returns(data_dir: Path) -> pl.LazyFrame:
    return pl.scan_parquet(data_dir / "historical_returns.parquet")


def scan_market_params(data_dir: Path) -> pl.LazyFrame:
    return pl.scan_parquet(data_dir / "market_params.parquet")
