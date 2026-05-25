# Demos

A collection of interactive demo applications for talks and presentations, built with Python and [Streamlit](https://streamlit.io/).

## Subprojects

| Subproject | Description |
|---|---|
| [`financial_quant/`](./financial_quant/) | Financial quantitative calculations — options pricing (Black-Scholes), portfolio risk metrics, and Monte Carlo simulations |
| [`digital_assets/`](./digital_assets/) | Digital assets & crypto — portfolio tracker, DeFi yield calculator, and tokenomics modeller |

## Requirements

- Python 3.10+
- UV package manager (`brew install uv`)
- Follow setup steps in each subproject README

## AI tooling

- Central AI setup and precedence rules: [AI_INSTRUCTIONS.md](./AI_INSTRUCTIONS.md)
- Copilot baseline instructions: [`.github/copilot-instructions.md`](./.github/copilot-instructions.md)
- Claude baseline instructions: [`CLAUDE.md`](./CLAUDE.md)

## Running a demo

```bash
# Financial quant demo
cd financial_quant
uv sync
uv run streamlit run app.py

# Digital assets demo
cd digital_assets
uv sync
uv run streamlit run app.py
```
