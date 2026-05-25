# Plan: VaR Demo Synthetic Data Generator

## Context

**Target file:** `src/simulated_data_lab/generate_var_demo_data.py`
**Output directory:** `data/var_demo/` (under project root)
**Entry point:** run directly with `uv run python src/simulated_data_lab/generate_var_demo_data.py`

This script is a one-shot data fixture generator for two downstream demos:
- **Historical VaR** — needs portfolio + historical daily returns
- **Monte Carlo VaR** — needs portfolio + per-ticker drift/vol + correlation structure

Both demos operate on the same portfolio, so all three outputs must be internally consistent
(tickers in portfolio ↔ tickers in returns ↔ tickers in market params).

---

## Output files

```
data/var_demo/
├── portfolio.parquet           # 500 rows
├── historical_returns.parquet  # ~250 000 rows
├── market_params.parquet       # 500 rows (one per unique ticker)
├── sector_correlation.parquet  # 11 × 11 sector-level correlation matrix
└── README.md                   # schema and relationship docs
```

### `portfolio.parquet` schema

| column        | dtype   | notes                                              |
|---------------|---------|----------------------------------------------------|
| position_id   | str     | `POS-00001` … `POS-00500`                          |
| desk          | str     | one of 5 desks (see below)                         |
| book          | str     | `<desk>_B1` … `<desk>_B3` — 3 books per desk       |
| ticker        | str     | unique per position; links to returns and params   |
| quantity      | int     | long positive, short negative; range ±100 – ±10 000|
| current_price | float   | USD-equivalent; range ~10 – 500                    |
| sector        | str     | 11 GICS sectors                                    |
| currency      | str     | USD / EUR / GBP / JPY / HKD                        |

Desk layout (100 positions each):

| desk              | region          | currencies        |
|-------------------|-----------------|-------------------|
| US_LargeCap       | North America   | USD               |
| US_SmallMidCap    | North America   | USD               |
| European_Equities | Europe          | EUR, GBP          |
| AsiaPac_Equities  | Asia Pacific    | JPY, HKD          |
| EmergingMarkets   | EM              | USD (ADR-style)   |

~20% of positions should be short (negative quantity) to make VaR non-trivial.

### `historical_returns.parquet` schema

| column  | dtype       | notes                                           |
|---------|-------------|-------------------------------------------------|
| date    | date32      | last 500 business days ending today             |
| ticker  | str         | foreign key → portfolio.ticker                  |
| return  | float64     | daily log-return; ~N(0, σ) with fat tails       |

Row count: 500 tickers × 500 days = 250 000 rows exactly.
Sorted by (date, ticker) for efficient columnar reads.

### `market_params.parquet` schema

| column       | dtype   | notes                                           |
|--------------|---------|-------------------------------------------------|
| ticker       | str     | primary key; same universe as portfolio         |
| sector       | str     | denormalized for convenience                    |
| annual_drift | float64 | = mean(daily_return) × 252                      |
| annual_vol   | float64 | = std(daily_return) × √252                      |
| daily_vol    | float64 | = std(daily_return); kept for direct MC use     |

Derived purely from `historical_returns` — no independent draws.

### `sector_correlation.parquet` schema

Wide format: 11 rows × 11 columns, index = sector name, columns = sector name.
Values are realized Pearson correlations of sector-mean daily returns computed from
`historical_returns`. Positive-definite by construction (sector-mean returns are full
time series, so realized corr is always PSD).

---

## Generation algorithm

### Step 1 — Ticker universe (500 tickers)

Build a ticker registry DataFrame with columns: ticker, sector, currency, region.

Distribution across desks/sectors should be realistic but not exact:
- US tickers: 3–4 uppercase letters, e.g. `ALVN`, `BRXT`, `CMQP`
- EU tickers: 4 letters + suffix `.L` (London) or `.PA` (Paris), e.g. `BNKR.L`
- Asia tickers: 4 letters + `.HK` or `.T`, e.g. `TNKH.HK`
- EM tickers: 4 letters + `.SA` or `.NS`, e.g. `PTRB.SA`

Use a fixed seed-seeded RNG to draw ticker strings; ensure no duplicates.

Sectors (11 GICS): Technology, Financials, Healthcare, ConsumerDiscretionary,
ConsumerStaples, Energy, Materials, Industrials, Utilities, RealEstate,
CommunicationServices.

### Step 2 — Portfolio (500 positions)

One position per ticker — no ticker appears twice. Assign each ticker to one desk
deterministically based on its region. Assign books round-robin within desk.

Current price: lognormal draw, μ=4.5, σ=0.8 (gives realistic $10–$500 range).
Quantity: 80% long (uniform 100–10 000), 20% short (negate). Round to nearest 10.

### Step 3 — Correlated historical returns (250 000 rows)

Goal: returns that look realistic with sector clustering and fat tails.

**Algorithm:**
1. Build a 500×500 target correlation matrix `Σ_target`:
   - Same-ticker: 1.0
   - Same-sector: draw ρ ~ Uniform(0.45, 0.70)
   - Cross-sector: draw ρ ~ Uniform(0.05, 0.25)
   - Add a small market factor: add `β_i * β_j * 0.15` where `β_i ~ Uniform(0.7, 1.3)`
   - Clip to [−1, 1]; ensure PSD by eigenvalue floor: set negative eigenvalues to 1e-6,
     renormalize. Use `numpy.linalg.eigh` for speed.

2. Cholesky-decompose the cleaned matrix: `L = cholesky(Σ_clean)`.

3. Draw `Z ~ N(0, I)` of shape (500 days, 500 tickers).

4. Correlated normals: `R_normal = Z @ L.T`

5. Fat tails via Student-t scaling:
   - Draw `ν = 5` degrees of freedom scaling factors per day: `s ~ sqrt(ν / chi2(ν, size=500))`
   - `R_scaled = R_normal * s[:, None]`  (same scaling applied across all tickers on a day —
     this models market-wide stress events correctly)

6. Per-ticker vol scaling: draw `σ_i ~ Uniform(0.008, 0.018)` for each ticker.
   Shift and scale: `R_final[:, i] = R_scaled[:, i] * σ_i + μ_i`
   where `μ_i ~ Uniform(-0.0001, 0.0003)` (tiny positive drift).

7. Melt to long format (date, ticker, return). Sort by (date, ticker).

### Step 4 — Market parameters

Compute from `historical_returns` directly:
```python
params = returns.groupby("ticker")["return"].agg(
    annual_drift=lambda x: x.mean() * 252,
    annual_vol=lambda x: x.std() * np.sqrt(252),
    daily_vol="std",
).reset_index()
```
Join sector from ticker registry.

### Step 5 — Sector correlation matrix

```python
# pivot to wide: shape (500 days, 500 tickers)
wide = returns.pivot(index="date", columns="ticker", values="return")
# map tickers to sectors; compute sector mean return per day
sector_returns = wide.T.groupby(ticker_to_sector).mean().T  # (500 days, 11 sectors)
sector_corr = sector_returns.corr()  # (11, 11)
```

---

## Script structure

Single file, top-to-bottom with these named functions:

```
build_ticker_universe(n_tickers, rng)         → pd.DataFrame
build_portfolio(tickers_df, rng)              → pd.DataFrame
build_correlation_matrix(tickers_df, rng)     → np.ndarray  [500×500]
nearest_psd(matrix)                           → np.ndarray
generate_historical_returns(tickers_df, corr, rng) → pd.DataFrame
compute_market_params(returns_df, tickers_df) → pd.DataFrame
compute_sector_correlation(returns_df, tickers_df) → pd.DataFrame
write_readme(output_dir)                      → None
main()                                        → None  [orchestrator; fixed seed = 42]
```

`main()` steps:
1. Parse optional `--output-dir` CLI arg (default: `data/var_demo`)
2. Create `rng = np.random.default_rng(42)`
3. Call each builder in order
4. Write parquets with `pyarrow` engine, `snappy` compression
5. Write README.md
6. Print row counts and file sizes to stdout

---

## Non-negotiables

- **Reproducibility**: all randomness flows from `np.random.default_rng(42)`. No calls to
  `random`, `np.random.seed`, or `pd.DataFrame.sample` with uncontrolled seeds.
- **Schema consistency**: the ticker set in `portfolio`, `historical_returns`, and
  `market_params` must be identical — assert this before writing.
- **No external data**: numpy and pandas only. No yfinance, no requests, no subprocess.
- **Single file**: everything in `generate_var_demo_data.py`; no helper modules.
- **Runnable on laptop**: target < 30 s wall-clock, < 2 GB peak RAM. The 500×500 Cholesky
  is the hot spot — keep the matrix float32 during generation, cast to float64 only for
  the final output.
- **Dependencies already in pyproject.toml**: numpy, pandas, pyarrow. No new deps.

---

## Verification

After implementation, run:

```bash
cd /Users/kamlesh/dev/git/Demos/financial_quant/simulated_data_lab
uv run python src/simulated_data_lab/generate_var_demo_data.py
```

Then verify:

```bash
python3 - <<'EOF'
import pandas as pd, os

base = "data/var_demo"
port = pd.read_parquet(f"{base}/portfolio.parquet")
rets = pd.read_parquet(f"{base}/historical_returns.parquet")
params = pd.read_parquet(f"{base}/market_params.parquet")
scorr = pd.read_parquet(f"{base}/sector_correlation.parquet")

assert len(port) == 500, f"portfolio: {len(port)}"
assert len(rets) == 250_000, f"returns: {len(rets)}"
assert len(params) == 500, f"params: {len(params)}"
assert scorr.shape == (11, 11), f"sector_corr shape: {scorr.shape}"
assert set(port.ticker) == set(rets.ticker.unique()), "ticker mismatch port/returns"
assert set(port.ticker) == set(params.ticker), "ticker mismatch port/params"
assert port.desk.nunique() == 5
assert port.groupby("desk")["book"].nunique().eq(3).all()
assert rets.date.nunique() == 500
print("All assertions passed.")
for f in ["portfolio","historical_returns","market_params","sector_correlation"]:
    size = os.path.getsize(f"{base}/{f}.parquet") / 1024
    print(f"  {f}.parquet  {size:.0f} KB")
EOF
```

---

## README content to generate (data/var_demo/README.md)

The README must describe:
1. Purpose: fixture data for Historical VaR and Monte Carlo VaR demos
2. Schema table for each file (column, type, description)
3. Relationship diagram (text):
   ```
   portfolio.ticker ──► historical_returns.ticker
   portfolio.ticker ──► market_params.ticker
   market_params.sector ──► sector_correlation [row/col index]
   ```
4. How to regenerate: the exact uv run command
5. Seed value and what it controls

---

## Implementation order

1. Scaffold `main()` + CLI arg parsing + output dir creation
2. `build_ticker_universe` — deterministic ticker strings, sector and region assignment
3. `build_portfolio` — position assembly, price/quantity draws
4. `build_correlation_matrix` + `nearest_psd` — the numerically sensitive part; test
   that all eigenvalues ≥ 0 before proceeding
5. `generate_historical_returns` — Cholesky draw + t-scaling + melt
6. `compute_market_params` and `compute_sector_correlation` — pure aggregations
7. `write_readme`
8. Wire everything in `main()`, add assertion block, write parquets
9. Run verification block above
