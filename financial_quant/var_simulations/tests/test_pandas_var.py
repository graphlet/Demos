from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from var_simulations.cli_pandas import _parse_confidence_levels
from var_simulations.pandas_var.engine import (
    build_scenario_matrix,
    compute_es,
    compute_market_values,
    compute_pnl_scenarios,
    compute_var,
    run_var_analysis,
)


class TestPandasVarCore(unittest.TestCase):
    def test_compute_market_values(self) -> None:
        portfolio = pd.DataFrame(
            {
                "ticker": ["AAA", "BBB"],
                "quantity": [10.0, 5.0],
                "current_price": [100.0, 20.0],
            }
        )

        result = compute_market_values(portfolio)

        self.assertEqual(result["mkt_value"].tolist(), [1000.0, 100.0])

    def test_build_matrix_and_pnl(self) -> None:
        returns = pd.DataFrame(
            {
                "date": ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02"],
                "ticker": ["AAA", "BBB", "AAA", "BBB"],
                "return": [0.01, -0.02, -0.03, 0.01],
            }
        )
        tickers = ["BBB", "AAA"]

        matrix = build_scenario_matrix(returns, tickers)
        pnl = compute_pnl_scenarios(matrix, [200.0, 100.0])

        self.assertEqual(matrix.columns.tolist(), ["BBB", "AAA"])
        self.assertAlmostEqual(pnl[0], -3.0)
        self.assertAlmostEqual(pnl[1], -1.0)

    def test_var_and_es(self) -> None:
        pnl = [-10.0, -8.0, -5.0, 1.0, 2.0]

        var_60 = compute_var(pnl, 0.6)
        es_60 = compute_es(pnl, 0.6)

        self.assertAlmostEqual(var_60, 5.0)
        self.assertAlmostEqual(es_60, 9.0)


class TestCliParsing(unittest.TestCase):
    def test_parse_confidence_levels(self) -> None:
        levels = _parse_confidence_levels("0.95, 0.99")
        self.assertEqual(levels, [0.95, 0.99])

        with self.assertRaises(ValueError):
            _parse_confidence_levels("1.0")


class TestRunVarAnalysis(unittest.TestCase):
    def test_small_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            portfolio = pd.DataFrame(
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
            returns = pd.DataFrame(
                {
                    "date": ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02"],
                    "ticker": ["AAA", "BBB", "AAA", "BBB"],
                    "return": [0.01, -0.02, -0.03, 0.01],
                }
            )
            market = pd.DataFrame(
                {
                    "ticker": ["AAA", "BBB"],
                    "sector": ["S1", "S2"],
                    "annual_drift": [0.05, 0.04],
                    "annual_vol": [0.2, 0.25],
                    "daily_vol": [0.0126, 0.0157],
                }
            )

            portfolio.to_parquet(data_dir / "portfolio.parquet", index=False)
            returns.to_parquet(data_dir / "historical_returns.parquet", index=False)
            market.to_parquet(data_dir / "market_params.parquet", index=False)

            result = run_var_analysis(data_dir, [0.95])

            self.assertEqual(result.scenario_count, 2)
            self.assertAlmostEqual(result.nav, 1100.0)
            self.assertAlmostEqual(result.portfolio_var[0.95], 29.0)
            self.assertIn("D1", result.desk_var)
            self.assertIn("S1", result.sector_var)
            self.assertIn("B1", result.book_var)


if __name__ == "__main__":
    unittest.main()
