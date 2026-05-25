# Financial Quant Calculator

An interactive Streamlit application covering core quantitative finance calculations:

- **Black-Scholes Options Pricing** — price European calls and puts, compute the Greeks
- **Portfolio Risk Metrics** — annualised return, volatility, Sharpe ratio, and Value-at-Risk
- **Monte Carlo Simulation** — simulate asset price paths and estimate option payoffs

## Setup (UV)

Use these commands every time:

```bash
brew install uv
cd financial_quant
uv sync
uv run streamlit run app.py
```

## Run

```bash
uv run streamlit run app.py
```

## Related Subproject: Simulated Data Lab

For synthetic dataset generation workflows (including large, chunked outputs), use:

- [`simulated_data_lab/`](./simulated_data_lab/)

Quick start:

```bash
cd simulated_data_lab
uv sync
uv run sim-quant-data --config configs/equities_small.yaml --output-dir output
```

## Related Subproject: VaR Simulations

For VaR simulation workflows, use:

- [`var_simulations/`](./var_simulations/)

Quick start:

```bash
cd var_simulations
uv sync
```

