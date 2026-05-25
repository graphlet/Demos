# var_simulations Guide

## Ownership

Owns historical simulation VaR workflows for quant research and risk testing.

## API and contracts

- Package namespace: `src/var_simulations/`
- Keep data contracts explicit once generators/loaders are added
- Keep random draws deterministic when seeded inputs are used

## Commands

Setup:
```bash
uv sync
```

Validation:
```bash
python3 -m compileall src
```
