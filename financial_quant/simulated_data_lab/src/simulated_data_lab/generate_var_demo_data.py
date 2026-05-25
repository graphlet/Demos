from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SECTORS: list[str] = [
    "Technology",
    "Financials",
    "Healthcare",
    "ConsumerDiscretionary",
    "ConsumerStaples",
    "Energy",
    "Materials",
    "Industrials",
    "Utilities",
    "RealEstate",
    "CommunicationServices",
]

DESK_SPECS: list[dict[str, object]] = [
    {
        "desk": "US_LargeCap",
        "region": "North America",
        "currencies": ["USD"],
        "suffixes": [""],
        "count": 100,
    },
    {
        "desk": "US_SmallMidCap",
        "region": "North America",
        "currencies": ["USD"],
        "suffixes": [""],
        "count": 100,
    },
    {
        "desk": "European_Equities",
        "region": "Europe",
        "currencies": ["EUR", "GBP"],
        "suffixes": [".L", ".PA"],
        "count": 100,
    },
    {
        "desk": "AsiaPac_Equities",
        "region": "Asia Pacific",
        "currencies": ["JPY", "HKD"],
        "suffixes": [".HK", ".T"],
        "count": 100,
    },
    {
        "desk": "EmergingMarkets",
        "region": "EM",
        "currencies": ["USD"],
        "suffixes": [".SA", ".NS"],
        "count": 100,
    },
]


def build_ticker_universe(n_tickers: int, rng: np.random.Generator) -> pd.DataFrame:
    if n_tickers != 500:
        raise ValueError("This fixture generator expects exactly 500 tickers.")

    rows: list[dict[str, str]] = []
    seen_tickers: set[str] = set()

    sector_weights = np.array([0.14, 0.13, 0.12, 0.11, 0.08, 0.08, 0.08, 0.10, 0.05, 0.05, 0.06])

    alphabet = np.array(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))

    for spec in DESK_SPECS:
        desk = str(spec["desk"])
        region = str(spec["region"])
        currencies = list(spec["currencies"])
        suffixes = list(spec["suffixes"])
        count = int(spec["count"])

        generated = 0
        while generated < count:
            base = "".join(rng.choice(alphabet, size=4, replace=True).tolist())
            suffix = str(rng.choice(suffixes))
            ticker = f"{base}{suffix}"
            if ticker in seen_tickers:
                continue

            seen_tickers.add(ticker)
            generated += 1
            rows.append(
                {
                    "ticker": ticker,
                    "sector": str(rng.choice(SECTORS, p=sector_weights)),
                    "currency": str(rng.choice(currencies)),
                    "region": region,
                    "desk": desk,
                }
            )

    tickers_df = pd.DataFrame(rows)
    if len(tickers_df) != n_tickers:
        raise RuntimeError(f"Expected {n_tickers} tickers, got {len(tickers_df)}.")

    return tickers_df


def build_portfolio(tickers_df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    portfolio = tickers_df.copy().reset_index(drop=True)

    position_ids = [f"POS-{i:05d}" for i in range(1, len(portfolio) + 1)]
    portfolio.insert(0, "position_id", position_ids)

    books: list[str] = []
    for desk in portfolio["desk"].tolist():
        # Round-robin assignment preserves exactly 3 books per desk.
        idx_within_desk = len([x for x in books if x.startswith(f"{desk}_")])
        books.append(f"{desk}_B{(idx_within_desk % 3) + 1}")
    portfolio.insert(2, "book", books)

    raw_prices = rng.lognormal(mean=4.5, sigma=0.8, size=len(portfolio))
    prices = np.clip(raw_prices, 10.0, 500.0)

    abs_qty = rng.integers(10, 1001, size=len(portfolio)) * 10
    is_short = rng.random(len(portfolio)) < 0.20
    quantities = abs_qty.copy()
    quantities[is_short] *= -1

    portfolio["quantity"] = quantities.astype(np.int64)
    portfolio["current_price"] = prices.astype(np.float64)

    # Keep column order explicit for downstream demos.
    portfolio = portfolio[
        [
            "position_id",
            "desk",
            "book",
            "ticker",
            "quantity",
            "current_price",
            "sector",
            "currency",
            "region",
        ]
    ]

    return portfolio


def nearest_psd(matrix: np.ndarray) -> np.ndarray:
    symmetric = (matrix + matrix.T) / 2.0
    eigvals, eigvecs = np.linalg.eigh(symmetric.astype(np.float64))
    eigvals = np.clip(eigvals, 1e-6, None)
    reconstructed = (eigvecs * eigvals) @ eigvecs.T
    d = np.sqrt(np.diag(reconstructed))
    normalized = reconstructed / np.outer(d, d)
    np.fill_diagonal(normalized, 1.0)
    return normalized.astype(np.float64)


def build_correlation_matrix(tickers_df: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    n = len(tickers_df)
    sectors = tickers_df["sector"].to_numpy()

    same_sector = sectors[:, None] == sectors[None, :]

    sector_corr = rng.uniform(0.45, 0.70, size=(n, n)).astype(np.float32)
    cross_corr = rng.uniform(0.05, 0.25, size=(n, n)).astype(np.float32)

    corr = np.where(same_sector, sector_corr, cross_corr).astype(np.float32)
    corr = (corr + corr.T) / 2.0

    betas = rng.uniform(0.7, 1.3, size=n).astype(np.float32)
    corr += np.outer(betas, betas) * 0.15

    corr = np.clip(corr, -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)

    corr_psd = nearest_psd(corr)
    eigvals = np.linalg.eigvalsh(corr_psd)
    if np.min(eigvals) < -1e-8:
        raise RuntimeError("Correlation matrix is not PSD after cleanup.")

    return corr_psd.astype(np.float32)


def generate_historical_returns(
    tickers_df: pd.DataFrame, corr: np.ndarray, rng: np.random.Generator
) -> pd.DataFrame:
    n_days = 500
    n_tickers = len(tickers_df)

    corr64 = corr.astype(np.float64)
    l_matrix = np.linalg.cholesky(corr64)

    z = rng.normal(0.0, 1.0, size=(n_days, n_tickers)).astype(np.float32)
    r_normal = z @ l_matrix.T.astype(np.float32)

    nu = 5.0
    scales = np.sqrt(nu / rng.chisquare(df=nu, size=n_days)).astype(np.float32)
    r_scaled = r_normal * scales[:, None]

    sigma = rng.uniform(0.008, 0.018, size=n_tickers).astype(np.float32)
    mu = rng.uniform(-0.0001, 0.0003, size=n_tickers).astype(np.float32)
    r_final = r_scaled * sigma[None, :] + mu[None, :]

    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n_days)

    returns_df = pd.DataFrame(r_final.astype(np.float64), columns=tickers_df["ticker"].tolist())
    returns_df.insert(0, "date", dates)
    returns_long = returns_df.melt(id_vars=["date"], var_name="ticker", value_name="return")
    returns_long["date"] = pd.to_datetime(returns_long["date"]).dt.date
    returns_long = returns_long.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)

    return returns_long


def compute_market_params(returns_df: pd.DataFrame, tickers_df: pd.DataFrame) -> pd.DataFrame:
    params = (
        returns_df.groupby("ticker", as_index=False)["return"]
        .agg(
            annual_drift=lambda x: x.mean() * 252.0,
            annual_vol=lambda x: x.std() * np.sqrt(252.0),
            daily_vol="std",
        )
        .astype({"annual_drift": "float64", "annual_vol": "float64", "daily_vol": "float64"})
    )

    sector_map = tickers_df[["ticker", "sector"]].drop_duplicates()
    params = params.merge(sector_map, on="ticker", how="left")
    params = params[["ticker", "sector", "annual_drift", "annual_vol", "daily_vol"]]

    return params


def compute_sector_correlation(returns_df: pd.DataFrame, tickers_df: pd.DataFrame) -> pd.DataFrame:
    wide = returns_df.pivot(index="date", columns="ticker", values="return")
    ticker_to_sector = tickers_df.set_index("ticker")["sector"]
    sector_returns = wide.T.groupby(ticker_to_sector).mean().T
    sector_corr = sector_returns.corr()
    sector_corr = sector_corr.reindex(index=SECTORS, columns=SECTORS)
    return sector_corr


def write_readme(output_dir: Path) -> None:
    content = """# VaR Demo Data Fixtures

Purpose: deterministic synthetic fixture data for Historical VaR and Monte Carlo VaR demos.

## Files

### portfolio.parquet

| column | type | description |
|---|---|---|
| position_id | string | Position identifier, POS-00001 to POS-00500 |
| desk | string | Trading desk |
| book | string | Desk book, B1 to B3 |
| ticker | string | Unique instrument identifier |
| quantity | int64 | Position size; negative means short |
| current_price | float64 | Spot price in local currency terms |
| sector | string | GICS sector |
| currency | string | Reporting currency |
| region | string | Geographic region |

### historical_returns.parquet

| column | type | description |
|---|---|---|
| date | date32 | Business date |
| ticker | string | Instrument identifier |
| return | float64 | Daily log return |

### market_params.parquet

| column | type | description |
|---|---|---|
| ticker | string | Instrument identifier |
| sector | string | Denormalized sector |
| annual_drift | float64 | Mean daily return multiplied by 252 |
| annual_vol | float64 | Daily return std multiplied by sqrt(252) |
| daily_vol | float64 | Daily return standard deviation |

### sector_correlation.parquet

| field | type | description |
|---|---|---|
| index | string | Sector name |
| columns | string | Sector names |
| values | float64 | Pearson correlation of sector mean daily returns |

## Relationships

portfolio.ticker -> historical_returns.ticker
portfolio.ticker -> market_params.ticker
market_params.sector -> sector_correlation row/column index

## Regeneration

Run from project root `financial_quant/simulated_data_lab`:

uv run python src/simulated_data_lab/generate_var_demo_data.py

## Reproducibility

Seed is fixed at 42. It controls ticker generation, portfolio construction, correlation structure,
return simulation, and all derived outputs.
"""
    (output_dir / "README.md").write_text(content, encoding="utf-8")


def _format_file_size_kb(path: Path) -> str:
    return f"{(path.stat().st_size / 1024.0):.0f} KB"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="generate-var-demo-data",
        description="Generate synthetic fixtures for Historical and Monte Carlo VaR demos.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/var_demo"),
        help="Directory where fixture parquet files will be written.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(42)

    tickers_df = build_ticker_universe(500, rng)
    portfolio_df = build_portfolio(tickers_df, rng)
    corr_matrix = build_correlation_matrix(tickers_df, rng)
    returns_df = generate_historical_returns(tickers_df, corr_matrix, rng)
    market_params_df = compute_market_params(returns_df, tickers_df)
    sector_corr_df = compute_sector_correlation(returns_df, tickers_df)

    portfolio_tickers = set(portfolio_df["ticker"].tolist())
    returns_tickers = set(returns_df["ticker"].unique().tolist())
    params_tickers = set(market_params_df["ticker"].tolist())

    assert portfolio_tickers == returns_tickers, "Ticker mismatch between portfolio and returns."
    assert portfolio_tickers == params_tickers, "Ticker mismatch between portfolio and market params."

    portfolio_path = output_dir / "portfolio.parquet"
    returns_path = output_dir / "historical_returns.parquet"
    params_path = output_dir / "market_params.parquet"
    sector_corr_path = output_dir / "sector_correlation.parquet"

    portfolio_cols = [
        "position_id",
        "desk",
        "book",
        "ticker",
        "quantity",
        "current_price",
        "sector",
        "currency",
    ]
    portfolio_df[portfolio_cols].to_parquet(
        portfolio_path,
        engine="pyarrow",
        compression="snappy",
        index=False,
    )
    returns_df.to_parquet(
        returns_path,
        engine="pyarrow",
        compression="snappy",
        index=False,
    )
    market_params_df.to_parquet(
        params_path,
        engine="pyarrow",
        compression="snappy",
        index=False,
    )
    sector_corr_df.to_parquet(
        sector_corr_path,
        engine="pyarrow",
        compression="snappy",
        index=True,
    )

    write_readme(output_dir)

    print("Generated VaR demo fixtures:")
    print(f"  portfolio rows: {len(portfolio_df):,}")
    print(f"  historical_returns rows: {len(returns_df):,}")
    print(f"  market_params rows: {len(market_params_df):,}")
    print(f"  sector_correlation shape: {sector_corr_df.shape}")
    print("Files:")
    print(f"  {portfolio_path.name}: {_format_file_size_kb(portfolio_path)}")
    print(f"  {returns_path.name}: {_format_file_size_kb(returns_path)}")
    print(f"  {params_path.name}: {_format_file_size_kb(params_path)}")
    print(f"  {sector_corr_path.name}: {_format_file_size_kb(sector_corr_path)}")


if __name__ == "__main__":
    main()
