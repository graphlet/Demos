# VaR Simulations

Value-at-Risk (VaR) simulation project scaffold for quantitative finance workflows.

This subproject is currently bootstrapped only, with no simulation logic implemented yet.

## Project Structure

```text
var_simulations/
  ai/
    copilot/prompts/
    claude/prompts/
    skills/
  configs/
  data/
    raw/
    processed/
    samples/
  notebooks/
  output/
  src/var_simulations/
  pyproject.toml
```

## Setup (UV)

Use these commands every time:

```bash
brew install uv
cd financial_quant/var_simulations
uv sync
```

## Next Step

When ready, add simulation modules under `src/var_simulations/` and wire runnable commands.
