from __future__ import annotations

from pathlib import Path

import pandas as pd


DATA_FILES = {
    "portfolio": "portfolio.parquet",
    "returns": "historical_returns.parquet",
    "market": "market_params.parquet",
}


def load_portfolio(data_dir: Path) -> pd.DataFrame:
    return pd.read_parquet(data_dir / DATA_FILES["portfolio"])


def load_returns(data_dir: Path) -> pd.DataFrame:
    return pd.read_parquet(data_dir / DATA_FILES["returns"])


def load_market_params(data_dir: Path) -> pd.DataFrame:
    return pd.read_parquet(data_dir / DATA_FILES["market"])
