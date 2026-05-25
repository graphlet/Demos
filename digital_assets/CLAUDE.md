# digital_assets Guide

## Ownership

Owns the digital assets Streamlit experience:
- portfolio tracker
- DeFi yield calculator
- tokenomics modeller

## API and contracts

- Primary user entrypoint: `app.py`
- Package namespace reserved at `src/digital_assets/`
- External API usage (CoinGecko) must degrade gracefully on failure

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
