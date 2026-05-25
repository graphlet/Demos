from __future__ import annotations

import argparse
import resource
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from var_simulations.cli_pandas import _parse_confidence_levels
from var_simulations.pandas_var.engine import run_var_analysis as run_pandas_var
from var_simulations.polars_var.engine import run_var_analysis as run_polars_var


@dataclass
class BenchmarkStats:
    implementation: str
    mean_ms: float
    min_ms: float
    max_ms: float
    peak_mb: float


def _rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return usage / (1024 * 1024) if usage > 10_000_000 else usage / 1024


def benchmark_implementation(
    impl_name: str,
    run_fn: Callable[[], object],
    iterations: int = 5,
) -> BenchmarkStats:
    durations_ms: list[float] = []
    peak_mb = _rss_mb()

    for _ in range(iterations):
        start = time.perf_counter()
        run_fn()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        durations_ms.append(elapsed_ms)
        peak_mb = max(peak_mb, _rss_mb())

    return BenchmarkStats(
        implementation=impl_name,
        mean_ms=statistics.mean(durations_ms),
        min_ms=min(durations_ms),
        max_ms=max(durations_ms),
        peak_mb=peak_mb,
    )


def print_comparison_table(pandas_stats: BenchmarkStats, polars_stats: BenchmarkStats) -> None:
    mean_speedup = pandas_stats.mean_ms / polars_stats.mean_ms if polars_stats.mean_ms else 0.0
    min_speedup = pandas_stats.min_ms / polars_stats.min_ms if polars_stats.min_ms else 0.0
    mem_ratio = pandas_stats.peak_mb / polars_stats.peak_mb if polars_stats.peak_mb else 0.0

    print("Implementation        Mean (ms)    Min (ms)    Peak MB")
    print("--------------------------------------------------------")
    print(
        f"{pandas_stats.implementation:<20}"
        f"{pandas_stats.mean_ms:>10.1f}"
        f"{pandas_stats.min_ms:>12.1f}"
        f"{pandas_stats.peak_mb:>11.1f}"
    )
    print(
        f"{polars_stats.implementation:<20}"
        f"{polars_stats.mean_ms:>10.1f}"
        f"{polars_stats.min_ms:>12.1f}"
        f"{polars_stats.peak_mb:>11.1f}"
    )
    print(
        f"{'Speedup/Ratio':<20}"
        f"{mean_speedup:>10.2f}x"
        f"{min_speedup:>12.2f}x"
        f"{mem_ratio:>11.2f}x"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hist-var-benchmark",
        description="Benchmark pandas and polars historical VaR implementations.",
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
        "--iterations",
        type=int,
        default=5,
        help="Number of runs per implementation.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    confidence_levels = _parse_confidence_levels(args.confidence)

    pandas_stats = benchmark_implementation(
        "Pandas + loops",
        lambda: run_pandas_var(args.data_dir, confidence_levels),
        iterations=args.iterations,
    )
    polars_stats = benchmark_implementation(
        "Polars + Arrow",
        lambda: run_polars_var(args.data_dir, confidence_levels),
        iterations=args.iterations,
    )

    print_comparison_table(pandas_stats, polars_stats)


if __name__ == "__main__":
    main()
