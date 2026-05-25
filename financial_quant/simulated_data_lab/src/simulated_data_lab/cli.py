from __future__ import annotations

import argparse
from pathlib import Path

from simulated_data_lab.generator import generate_dataset, load_scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sim-quant-data",
        description="Generate large synthetic market datasets for quant workflows.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to scenario YAML file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory where generated chunks and manifest will be written.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    scenario = load_scenario(args.config)
    scenario_dir = generate_dataset(scenario, args.output_dir)

    print(f"Scenario: {scenario.name}")
    print(f"Output directory: {scenario_dir}")
    print("Generation complete.")


if __name__ == "__main__":
    main()
