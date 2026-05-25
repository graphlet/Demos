# simulated_data_lab Guide

## Ownership

Owns synthetic dataset generation for quant research and testing.

## API and contracts

- CLI entrypoint: `sim-quant-data`
- Core generator package: `src/simulated_data_lab/`
- Config contract: YAML files in `configs/`
- Output contract: chunk files + `manifest.json`

## Commands

Setup:
```bash
uv sync
```

Run small scenario:
```bash
uv run sim-quant-data --config configs/equities_small.yaml --output-dir output
```

Validation:
```bash
python3 -m compileall src
```
