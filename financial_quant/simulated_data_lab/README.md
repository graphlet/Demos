# Simulated Data Lab

Config-driven synthetic dataset generation for financial quantitative research and model development.

This subproject is designed for:
- rapid prototyping of market-like OHLCV datasets
- large-scale dataset creation using chunked output
- AI-assisted development workflows with both Copilot and Claude Code

## Project structure

```text
simulated_data_lab/
  ai/
    copilot/prompts/
    claude/prompts/
    skills/
  configs/
  data/
    raw/
    processed/
    samples/
  output/
  src/simulated_data_lab/
  pyproject.toml
```

## Setup (UV)

Use these commands every time:

```bash
brew install uv
cd financial_quant/simulated_data_lab
uv sync
```

## Quick start

```bash
cd financial_quant/simulated_data_lab
uv sync
```

Generate a smaller dataset:

```bash
uv run sim-quant-data --config configs/equities_small.yaml --output-dir output
```

Generate a large dataset profile:

```bash
uv run sim-quant-data --config configs/equities_large.yaml --output-dir output
```

## Outputs

Each run writes to a scenario folder under `output/`:
- chunk files (`part_*.parquet` or `part_*.csv`)
- `manifest.json` with metadata and chunk-level index

Chunked writing avoids high memory pressure and supports very large datasets.

## AI workflow folders

- `ai/copilot/prompts/`: store Copilot-specific prompt templates and task starters
- `ai/claude/prompts/`: store Claude Code prompt templates and instructions
- `ai/skills/`: store reusable domain skills, playbooks, and generation rules

## Extending generators

Current generator produces OHLCV + log returns via geometric Brownian motion.

You can add additional generators in `src/simulated_data_lab/` for:
- factor model datasets
- options surface simulation
- limit-order-book event simulation
- regime-switching market environments
