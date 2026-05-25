# financial_quant Guide

## Ownership

Owns quant finance Streamlit workflows:
- Black-Scholes pricing and Greeks
- portfolio risk metrics
- Monte Carlo simulation demos

## API and contracts

- Primary UI entrypoint: `app.py`
- Package namespace reserved at `src/financial_quant/`
- Keep numerical outputs deterministic when seeded inputs are used

## Commands

Setup:
```bash
uv sync
```

Run:
```bash
uv run streamlit run app.py
```

Validation:
```bash
python3 -m compileall app.py src
```
