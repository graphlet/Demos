from __future__ import annotations

import argparse
from pathlib import Path

from var_simulations.cli_pandas import _parse_confidence_levels
from var_simulations.polars_var.engine import run_var_analysis
from var_simulations.polars_var.report import (
    format_summary_table,
    write_arrow_ipc,
    write_results_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hist-var-polars",
        description="Run historical simulation VaR with Polars lazy expressions.",
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
        help="Directory where output files are written.",
    )
    parser.add_argument(
        "--arrow",
        action="store_true",
        help="Also write Arrow IPC output for scenario P&L.",
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
    if args.arrow:
        write_arrow_ipc(result, args.output_dir)

    if not args.quiet:
        print(format_summary_table(result))
        print("")

    print(f"Wrote outputs to: {args.output_dir}")


if __name__ == "__main__":
    main()
