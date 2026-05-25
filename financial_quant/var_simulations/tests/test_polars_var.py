from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import polars as pl
import pyarrow.ipc as pa_ipc

from var_simulations.polars_var.engine import build_pnl_pipeline, run_var_analysis
from var_simulations.polars_var.loader import scan_portfolio, scan_returns
from var_simulations.polars_var.report import write_arrow_ipc


def _write_small_fixture(data_dir: Path) -> None:
    portfolio = pl.DataFrame(
        {
            "position_id": [1, 2],
            "desk": ["D1", "D2"],
            "book": ["B1", "B2"],
            "ticker": ["AAA", "BBB"],
            "quantity": [10.0, 5.0],
            "current_price": [100.0, 20.0],
            "sector": ["S1", "S2"],
            "currency": ["USD", "USD"],
        }
    )
    returns = pl.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02"],
            "ticker": ["AAA", "BBB", "AAA", "BBB"],
            "return": [0.01, -0.02, -0.03, 0.01],
        }
    )
    market = pl.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "sector": ["S1", "S2"],
            "annual_drift": [0.05, 0.04],
            "annual_vol": [0.2, 0.25],
            "daily_vol": [0.0126, 0.0157],
        }
    )

    portfolio.write_parquet(data_dir / "portfolio.parquet")
    returns.write_parquet(data_dir / "historical_returns.parquet")
    market.write_parquet(data_dir / "market_params.parquet")


class TestPolarsVar(unittest.TestCase):
    def test_scans_and_pipeline_are_lazy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            _write_small_fixture(data_dir)

            portfolio_lf = scan_portfolio(data_dir)
            returns_lf = scan_returns(data_dir)
            pnl_lf = build_pnl_pipeline(portfolio_lf, returns_lf)

            self.assertIsInstance(portfolio_lf, pl.LazyFrame)
            self.assertIsInstance(returns_lf, pl.LazyFrame)
            self.assertIsInstance(pnl_lf, pl.LazyFrame)

    def test_one_position_pnl_matches_qty_price_return(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            pl.DataFrame(
                {
                    "position_id": [1],
                    "desk": ["D1"],
                    "book": ["B1"],
                    "ticker": ["AAA"],
                    "quantity": [10.0],
                    "current_price": [100.0],
                    "sector": ["S1"],
                    "currency": ["USD"],
                }
            ).write_parquet(data_dir / "portfolio.parquet")
            pl.DataFrame(
                {
                    "date": ["2026-01-01"],
                    "ticker": ["AAA"],
                    "return": [0.01],
                }
            ).write_parquet(data_dir / "historical_returns.parquet")
            pl.DataFrame(
                {
                    "ticker": ["AAA"],
                    "sector": ["S1"],
                    "annual_drift": [0.05],
                    "annual_vol": [0.2],
                    "daily_vol": [0.0126],
                }
            ).write_parquet(data_dir / "market_params.parquet")

            result = run_var_analysis(data_dir, [0.95])
            self.assertEqual(result.scenario_count, 1)
            self.assertAlmostEqual(result.pnl_scenarios[0], 10.0)

    def test_end_to_end_and_breakdown_consistency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            _write_small_fixture(data_dir)

            result = run_var_analysis(data_dir, [0.95, 0.99])

            self.assertAlmostEqual(result.nav, 1100.0)
            self.assertAlmostEqual(result.portfolio_var[0.95], 29.0)
            self.assertAlmostEqual(result.portfolio_var[0.99], 29.0)

            pnl_lf = build_pnl_pipeline(scan_portfolio(data_dir), scan_returns(data_dir))
            group_df = pnl_lf.collect()
            portfolio_by_date = (
                group_df.group_by("date")
                .agg(pl.col("group_pnl").sum().alias("portfolio_pnl"))
                .sort("date")
            )
            desk_by_date = (
                group_df.group_by("date", "desk")
                .agg(pl.col("group_pnl").sum().alias("desk_pnl"))
                .group_by("date")
                .agg(pl.col("desk_pnl").sum().alias("desk_total"))
                .sort("date")
            )

            joined = portfolio_by_date.join(desk_by_date, on="date", how="inner")
            for row in joined.iter_rows(named=True):
                self.assertAlmostEqual(row["portfolio_pnl"], row["desk_total"])

    def test_arrow_output_is_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            _write_small_fixture(data_dir)

            result = run_var_analysis(data_dir, [0.95])
            arrow_path = write_arrow_ipc(result, data_dir)

            with pa_ipc.open_file(arrow_path) as reader:
                table = reader.read_all()

            self.assertGreaterEqual(table.num_rows, 1)


if __name__ == "__main__":
    unittest.main()
