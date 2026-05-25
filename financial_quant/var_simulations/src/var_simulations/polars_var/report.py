from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import polars as pl


RiskByConfidence = dict[float, float]
RiskByGroup = dict[str, RiskByConfidence]


@dataclass
class VaRResult:
    nav: float
    scenario_count: int
    confidence_levels: list[float]
    portfolio_var: RiskByConfidence
    portfolio_es: RiskByConfidence
    desk_var: RiskByGroup
    desk_es: RiskByGroup
    desk_nav: dict[str, float]
    sector_var: RiskByGroup
    sector_es: RiskByGroup
    sector_nav: dict[str, float]
    book_var: RiskByGroup
    book_es: RiskByGroup
    book_nav: dict[str, float]
    pnl_scenarios: list[float]
    raw_pnl_frame: pl.DataFrame


def _format_currency(value: float) -> str:
    return f"{value:,.0f}"


def _format_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def format_summary_table(result: VaRResult) -> str:
    lines: list[str] = []
    lines.append(
        "Portfolio Historical VaR"
        f" ({result.scenario_count} scenarios, NAV ${_format_currency(result.nav)})"
    )
    lines.append("-" * 72)
    lines.append(f"{'Level':<8}{'VaR $':>14}{'VaR %':>12}{'ES $':>14}{'ES %':>12}")

    for confidence in result.confidence_levels:
        var_value = result.portfolio_var[confidence]
        es_value = result.portfolio_es[confidence]
        lines.append(
            f"{confidence:>6.0%}"
            f"{_format_currency(var_value):>16}"
            f"{_format_pct(var_value / result.nav):>12}"
            f"{_format_currency(es_value):>14}"
            f"{_format_pct(es_value / result.nav):>12}"
        )

    if result.confidence_levels:
        top_confidence = max(result.confidence_levels)
        lines.append("")
        lines.append(f"Desk Breakdown (VaR {top_confidence:.0%})")
        lines.append("-" * 72)
        lines.append(f"{'Desk':<22}{'VaR $':>14}{'VaR %':>12}")

        for desk in sorted(result.desk_var):
            desk_var_value = result.desk_var[desk][top_confidence]
            desk_nav = result.desk_nav.get(desk, 0.0)
            desk_pct = (desk_var_value / desk_nav) if desk_nav else 0.0
            lines.append(
                f"{desk:<22}{_format_currency(desk_var_value):>14}{_format_pct(desk_pct):>12}"
            )

    return "\n".join(lines)


def write_results_csv(result: VaRResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / "var_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["confidence", "var", "var_pct_nav", "es", "es_pct_nav"])
        for confidence in result.confidence_levels:
            var_value = result.portfolio_var[confidence]
            es_value = result.portfolio_es[confidence]
            writer.writerow(
                [
                    confidence,
                    var_value,
                    var_value / result.nav if result.nav else 0.0,
                    es_value,
                    es_value / result.nav if result.nav else 0.0,
                ]
            )

    breakdown_path = output_dir / "var_breakdown.csv"
    with breakdown_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["dimension", "group", "confidence", "var", "es"])

        for dimension, var_map, es_map in (
            ("desk", result.desk_var, result.desk_es),
            ("sector", result.sector_var, result.sector_es),
            ("book", result.book_var, result.book_es),
        ):
            for group in sorted(var_map):
                for confidence in result.confidence_levels:
                    writer.writerow(
                        [
                            dimension,
                            group,
                            confidence,
                            var_map[group][confidence],
                            es_map[group][confidence],
                        ]
                    )


def write_arrow_ipc(result: VaRResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "pnl_scenarios.arrow"
    result.raw_pnl_frame.write_ipc(output_path)
    return output_path
