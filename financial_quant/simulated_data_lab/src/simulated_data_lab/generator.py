from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from tqdm import tqdm


@dataclass
class Scenario:
    name: str
    symbols: list[str]
    start_date: str
    freq: str
    periods_per_symbol: int
    chunk_size: int
    seed: int
    start_price: float
    annual_drift: float
    annual_volatility: float
    volume_lambda: int
    output_format: str


def load_scenario(path: Path) -> Scenario:
    with path.open("r", encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle)

    return Scenario(
        name=str(raw.get("name", "unnamed-scenario")),
        symbols=[str(x) for x in raw.get("symbols", ["AAPL"])],
        start_date=str(raw.get("start_date", "2024-01-01")),
        freq=str(raw.get("freq", "1min")),
        periods_per_symbol=int(raw.get("periods_per_symbol", 10000)),
        chunk_size=int(raw.get("chunk_size", 200000)),
        seed=int(raw.get("seed", 42)),
        start_price=float(raw.get("start_price", 100.0)),
        annual_drift=float(raw.get("annual_drift", 0.08)),
        annual_volatility=float(raw.get("annual_volatility", 0.2)),
        volume_lambda=int(raw.get("volume_lambda", 25000)),
        output_format=str(raw.get("output_format", "parquet")).lower(),
    )


def _simulate_symbol_chunk(
    *,
    symbol: str,
    start_ts: pd.Timestamp,
    periods: int,
    freq: str,
    prev_close: float,
    annual_drift: float,
    annual_volatility: float,
    volume_lambda: int,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, float]:
    dt = 1.0 / 252.0
    shocks = rng.normal(
        loc=(annual_drift - 0.5 * annual_volatility**2) * dt,
        scale=annual_volatility * math.sqrt(dt),
        size=periods,
    )

    close = prev_close * np.cumprod(np.exp(shocks))
    open_ = np.empty_like(close)
    open_[0] = prev_close
    open_[1:] = close[:-1]

    spread = np.abs(rng.normal(loc=0.0, scale=annual_volatility * 0.03, size=periods))
    high = np.maximum(open_, close) * (1.0 + spread)
    low = np.minimum(open_, close) * (1.0 - spread)
    volume = rng.poisson(lam=volume_lambda, size=periods) + 1

    df = pd.DataFrame(
        {
            "symbol": symbol,
            "timestamp": pd.date_range(start=start_ts, periods=periods, freq=freq),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume.astype("int64"),
            "log_return": shocks,
        }
    )
    return df, float(close[-1])


def generate_dataset(scenario: Scenario, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    scenario_dir = output_dir / scenario.name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "scenario": scenario.name,
        "symbols": scenario.symbols,
        "start_date": scenario.start_date,
        "freq": scenario.freq,
        "periods_per_symbol": scenario.periods_per_symbol,
        "chunk_size": scenario.chunk_size,
        "seed": scenario.seed,
        "output_format": scenario.output_format,
        "parts": [],
    }

    rng = np.random.default_rng(scenario.seed)
    offset = pd.tseries.frequencies.to_offset(scenario.freq)
    part_idx = 0

    for symbol in scenario.symbols:
        prev_close = scenario.start_price
        start_base = pd.Timestamp(scenario.start_date)

        for start in tqdm(range(0, scenario.periods_per_symbol, scenario.chunk_size), desc=f"{symbol} chunks"):
            chunk_n = min(scenario.chunk_size, scenario.periods_per_symbol - start)
            chunk_start = start_base + start * offset

            chunk_df, prev_close = _simulate_symbol_chunk(
                symbol=symbol,
                start_ts=chunk_start,
                periods=chunk_n,
                freq=scenario.freq,
                prev_close=prev_close,
                annual_drift=scenario.annual_drift,
                annual_volatility=scenario.annual_volatility,
                volume_lambda=scenario.volume_lambda,
                rng=rng,
            )

            part_name = f"part_{part_idx:06d}_{symbol}"
            if scenario.output_format == "csv":
                part_path = scenario_dir / f"{part_name}.csv"
                chunk_df.to_csv(part_path, index=False)
            else:
                part_path = scenario_dir / f"{part_name}.parquet"
                chunk_df.to_parquet(part_path, index=False)

            manifest["parts"].append(
                {
                    "part": part_name,
                    "symbol": symbol,
                    "rows": int(chunk_n),
                    "path": str(part_path.name),
                    "start_ts": str(chunk_df["timestamp"].iloc[0]),
                    "end_ts": str(chunk_df["timestamp"].iloc[-1]),
                }
            )
            part_idx += 1

    manifest_path = scenario_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    return scenario_dir
