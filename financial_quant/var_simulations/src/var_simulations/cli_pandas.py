from __future__ import annotations

import argparse
from pathlib import Path

from var_simulations.pandas_var.engine import run_var_analysis
from var_simulations.pandas_var.report import format_summary_table, write_results_csv


def _parse_confidence_levels(raw: str) -> list[float]:
    levels: list[float] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        value = float(token)
        if value <= 0.0 or value >= 1.0:
            raise ValueError("Confidence values must be between 0 and 1.")
        levels.append(value)

    if not levels:
        raise ValueError("At least one confidence level is required.")
    return levels


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hist-var-pandas",
        description="Run historical simulation VaR with pandas and explicit loops.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("../simulated_data_lab/data/var_demo"),
        help="Path to fixture parquet files.",
    )
    parser.add_argument(
        "--confidence",
        type=str,
        default="0.95,0.99",
        help="Comma-separated confidence levels.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory where CSV outputs are written.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console summary output.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    confidence_levels = _parse_confidence_levels(args.confidence)
    result = run_var_analysis(args.data_dir, confidence_levels)

    write_results_csv(result, args.output_dir)

    if not args.quiet:
        print(format_summary_table(result))
        print("")
    print(f"Wrote CSV outputs to: {args.output_dir}")


if __name__ == "__main__":
    main()
