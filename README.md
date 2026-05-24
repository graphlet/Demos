# Demos

A collection of interactive demo applications for talks and presentations, built with Python and [Streamlit](https://streamlit.io/).

## Subprojects

| Subproject | Description |
|---|---|
| [`financial_quant/`](./financial_quant/) | Financial quantitative calculations — options pricing (Black-Scholes), portfolio risk metrics, and Monte Carlo simulations |
| [`digital_assets/`](./digital_assets/) | Digital assets & crypto — portfolio tracker, DeFi yield calculator, and tokenomics modeller |

## Requirements

- Python 3.9+
- Each subproject has its own `requirements.txt`. Install with:
  ```bash
  pip install -r <subproject>/requirements.txt
  ```

## Running a demo

```bash
# Financial quant demo
cd financial_quant
streamlit run app.py

# Digital assets demo
cd digital_assets
streamlit run app.py
```
