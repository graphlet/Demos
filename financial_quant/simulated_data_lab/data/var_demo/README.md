# VaR Demo Data Fixtures

Purpose: deterministic synthetic fixture data for Historical VaR and Monte Carlo VaR demos.

## Files

### portfolio.parquet

| column | type | description |
|---|---|---|
| position_id | string | Position identifier, POS-00001 to POS-00500 |
| desk | string | Trading desk |
| book | string | Desk book, B1 to B3 |
| ticker | string | Unique instrument identifier |
| quantity | int64 | Position size; negative means short |
| current_price | float64 | Spot price in local currency terms |
| sector | string | GICS sector |
| currency | string | Reporting currency |
| region | string | Geographic region |

### historical_returns.parquet

| column | type | description |
|---|---|---|
| date | date32 | Business date |
| ticker | string | Instrument identifier |
| return | float64 | Daily log return |

### market_params.parquet

| column | type | description |
|---|---|---|
| ticker | string | Instrument identifier |
| sector | string | Denormalized sector |
| annual_drift | float64 | Mean daily return multiplied by 252 |
| annual_vol | float64 | Daily return std multiplied by sqrt(252) |
| daily_vol | float64 | Daily return standard deviation |

### sector_correlation.parquet

| field | type | description |
|---|---|---|
| index | string | Sector name |
| columns | string | Sector names |
| values | float64 | Pearson correlation of sector mean daily returns |

## Relationships

portfolio.ticker -> historical_returns.ticker
portfolio.ticker -> market_params.ticker
market_params.sector -> sector_correlation row/column index

## Regeneration

Run from project root `financial_quant/simulated_data_lab`:

uv run python src/simulated_data_lab/generate_var_demo_data.py

## Reproducibility

Seed is fixed at 42. It controls ticker generation, portfolio construction, correlation structure,
return simulation, and all derived outputs.
