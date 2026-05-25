# Plan: Historical VaR — Traditional Implementation (Pandas + Loops)

## Purpose

Implement Historical Simulation VaR using row-oriented, imperative Python — the style familiar to most quant
developers before columnar tools became mainstream. This implementation deliberately uses Python loops,
`iterrows`, and materialised intermediate DataFrames to make the contrasts with the Polars version visible.

## Showcase intent

This is one half of a side-by-side demonstration. The goal is not bad code — it is *representative* code:
what an experienced pandas developer would write before adopting a columnar mindset. Keep loops explicit and
avoid sneaking in numpy vectorisation in the hot path.

---

## Algorithm

Historical Simulation VaR replays a portfolio against a window of actual historical daily returns and reads
the loss distribution directly from the resulting P&L scenarios, without fitting any parametric distribution.

```
Step 1  Load portfolio positions (500 rows: ticker, quantity, current_price, desk, book, sector)
Step 2  Compute market value per position: mkt_value = quantity × current_price
Step 3  Load historical returns (250 000 rows long-format: date, ticker, return)
Step 4  Pivot returns to a scenario matrix: shape (500 dates × 500 tickers)
Step 5  For each scenario date, compute portfolio P&L = Σ (mkt_value_i × return_i_on_date)
Step 6  Sort the 500 P&L scenarios ascending
Step 7  VaR at level α = −scenarios[floor((1−α) × N)]
Step 8  ES  at level α = −mean(scenarios below the VaR threshold)
Step 9  Repeat Steps 5–8 for desk, book, and sector sub-portfolios
Step 10 Write results to CSV and print a formatted summary table
```

**Known numbers (from fixture data)**
- Portfolio NAV: ~$168 M across 5 desks, 11 sectors, 500 positions
- Scenario window: 500 business days (2024-06-24 → 2026-05-22)
- Portfolio VaR 99%: ~$3.18 M (1.89 % NAV); VaR 95%: ~$2.11 M (1.25 % NAV)
- ES 99%: ~$3.99 M (2.37 % NAV)

---

## Module structure

```
src/var_simulations/pandas_var/
    __init__.py          # re-exports run_var_analysis
    loader.py            # eager pd.read_parquet wrappers
    engine.py            # loop-based P&L engine + VaR/ES calculations
    report.py            # VaRResult dataclass, CSV writer, console table
src/var_simulations/cli_pandas.py   # argparse entry point → hist-var-pandas
```

---

## File-by-file implementation plan

### `src/var_simulations/pandas_var/loader.py`

**Intent:** Load the three parquet files into plain pandas DataFrames. Keep types as-is; do no
transformation here.

```
DATA_FILES = {
    "portfolio":  "portfolio.parquet",
    "returns":    "historical_returns.parquet",
    "market":     "market_params.parquet",
}

load_portfolio(data_dir: Path) -> pd.DataFrame
    pd.read_parquet(data_dir / "portfolio.parquet")
    Returns columns: position_id, desk, book, ticker, quantity, current_price, sector, currency

load_returns(data_dir: Path) -> pd.DataFrame
    pd.read_parquet(data_dir / "historical_returns.parquet")
    Returns columns: date (date32 → object/datetime), ticker, return

load_market_params(data_dir: Path) -> pd.DataFrame
    pd.read_parquet(data_dir / "market_params.parquet")
    Returns columns: ticker, sector, annual_drift, annual_vol, daily_vol
```

**Traditional marker:** `pd.read_parquet` deserialises the entire file eagerly into a pandas DataFrame
backed by numpy arrays. All 250 000 rows of returns land in memory before any computation begins.

---

### `src/var_simulations/pandas_var/engine.py`

**Intent:** Implement VaR with explicit Python loops to make the row-oriented pattern visible.

#### `compute_market_values(portfolio_df: pd.DataFrame) -> pd.DataFrame`

Add a `mkt_value` column using `iterrows`:

```python
mkt_values = []
for _, row in portfolio_df.iterrows():
    mkt_values.append(row["quantity"] * row["current_price"])
portfolio_df = portfolio_df.copy()
portfolio_df["mkt_value"] = mkt_values
return portfolio_df
```

**Traditional marker:** `iterrows` deserialises each row into a Python dict, incurring object boxing
overhead per cell. A vectorised version (`qty * price`) would be ~50–100× faster on 500 rows; this
cost is small here but scales badly with dataset size.

---

#### `build_scenario_matrix(returns_df: pd.DataFrame, tickers: list[str]) -> pd.DataFrame`

Pivot long-format returns to a wide date × ticker matrix, then reindex to match the portfolio's
ticker order:

```python
pivot = returns_df.pivot(index="date", columns="ticker", values="return")
scenario_matrix = pivot.reindex(columns=tickers, fill_value=0.0)
missing = [t for t in tickers if t not in pivot.columns]
if missing:
    raise ValueError(f"Tickers with no return history: {missing}")
return scenario_matrix
```

Shape: (500, 500) — dates as rows, tickers as columns.

**Guard:** raising on entirely-absent tickers prevents silently underestimating risk via all-zero
returns. Per-date gaps (a ticker missing on one date) are still filled with 0.0 — acceptable for
a demo but worth noting as an assumption.

---

#### `compute_pnl_scenarios(scenario_matrix: pd.DataFrame, mkt_values: list[float]) -> list[float]`

Loop over every date (scenario) and manually sum position P&Ls:

```python
pnl_scenarios = []
for date in scenario_matrix.index:
    day_returns = scenario_matrix.loc[date]       # pandas Series
    daily_pnl = 0.0
    for ticker_return, mkt_val in zip(day_returns, mkt_values):
        daily_pnl += ticker_return * mkt_val
    pnl_scenarios.append(daily_pnl)
return pnl_scenarios
```

**Traditional marker:** two nested Python loops — outer over 500 dates, inner over 500 tickers —
produce 250 000 Python float multiplications. This is the canonical row-iteration pattern that
columnar engines replace with a single vectorised dot product on contiguous memory.

---

#### `compute_var_es(pnl_scenarios: list[float], confidence: float) -> tuple[float, float]`

Sort once, then compute both VaR and ES from the same sorted list to avoid redundant sorting:

```python
sorted_pnl = sorted(pnl_scenarios)
# cutoff_idx is the last index included in the tail (the VaR scenario itself).
# With 500 scenarios at 99%: int(0.01 * 500) - 1 = 4 → 5th worst loss (0-indexed).
cutoff_idx = max(int((1.0 - confidence) * len(sorted_pnl)) - 1, 0)
var = -sorted_pnl[cutoff_idx]
tail = sorted_pnl[: cutoff_idx + 1]
es = -sum(tail) / len(tail) if tail else 0.0
return var, es
```

**Convention note:** `cutoff_idx = int((1−α) × N) − 1` picks the Nth worst loss where N = floor((1−α) × N),
consistent with the Basel convention and the fixture numbers (VaR 99% ≈ $3.18 M at index 4 of 500 scenarios).

**Traditional marker:** sorting a plain Python list with `sorted()` rather than `numpy.sort` or a vectorised
percentile call. Sorting happens once per group per confidence level — every sub-portfolio triggers its own
`sorted()` call in the breakdown loops.

---

#### `run_var_analysis(data_dir: Path, confidence_levels: list[float]) -> VaRResult`

Orchestrate all steps and produce breakdown by desk, book, and sector:

```python
portfolio = load_portfolio(data_dir)
returns   = load_returns(data_dir)
portfolio = compute_market_values(portfolio)

tickers = portfolio["ticker"].tolist()
scenario_matrix = build_scenario_matrix(returns, tickers)

# Portfolio-level
all_mkt_vals = portfolio["mkt_value"].tolist()
portfolio_pnl = compute_pnl_scenarios(scenario_matrix, all_mkt_vals)

# Desk breakdown — loop over unique desks
desk_results = {}
for desk in portfolio["desk"].unique():
    mask = portfolio["desk"] == desk
    sub_tickers  = portfolio.loc[mask, "ticker"].tolist()
    sub_mkt_vals = portfolio.loc[mask, "mkt_value"].tolist()
    # scenario_matrix[sub_tickers] returns a DataFrame; compute_pnl_scenarios
    # accepts pd.DataFrame for the matrix and list[float] for mkt_values.
    sub_matrix   = scenario_matrix[sub_tickers]   # pd.DataFrame, shape (500, len(sub_tickers))
    desk_pnl     = compute_pnl_scenarios(sub_matrix, sub_mkt_vals)
    desk_results[desk] = desk_pnl

# Sector breakdown — same pattern
# Book breakdown — same pattern

# Compute VaR and ES for every confidence level × breakdown using compute_var_es
return VaRResult(...)
```

**Traditional marker:** breakdown loops iterate over unique grouping keys in Python and re-filter
the scenario matrix for each group. Every group incurs a full Python-loop P&L pass.

---

### `src/var_simulations/pandas_var/report.py`

#### `VaRResult` (dataclass)

```python
@dataclass
class VaRResult:
    nav:            float
    scenario_count: int
    confidence_levels: list[float]
    portfolio_var:  dict[float, float]   # confidence → VaR $
    portfolio_es:   dict[float, float]
    desk_var:       dict[str, dict[float, float]]   # desk → confidence → VaR $
    sector_var:     dict[str, dict[float, float]]
    book_var:       dict[str, dict[float, float]]
    pnl_scenarios:  list[float]          # unsorted raw P&L — sort before passing to histogram
```

#### `format_summary_table(result: VaRResult) -> str`

Print a plain-text table:

```
Portfolio Historical VaR  (500 scenarios, NAV $168,475,321)
─────────────────────────────────────────────────────────
Level    VaR $         VaR %     ES $          ES %
 95%     2,111,964      1.25%    2,623,814      1.56%
 99%     3,181,345      1.89%    3,991,376      2.37%

Desk Breakdown (VaR 99%)
─────────────────────────────────────────────────────────
Desk                   NAV $        VaR $     VaR %
US_LargeCap            ...          ...       ...
...
```

#### `write_results_csv(result: VaRResult, output_path: Path)`

Write two CSVs: `var_summary.csv` (portfolio-level) and `var_breakdown.csv` (desk/sector/book rows).

---

### `src/var_simulations/cli_pandas.py`

```
Flags:
  --data-dir      Path to parquet files (default: ../simulated_data_lab/data/var_demo)
  --confidence    Comma-separated confidence levels (default: 0.95,0.99)
  --output-dir    Directory for CSV output (default: output/)
  --quiet         Suppress console table

Entry point in pyproject.toml:
  hist-var-pandas = "var_simulations.cli_pandas:main"
```

---

## pyproject.toml changes

Add to `[project] dependencies`:

```
"scipy>=1.13.0",   # optional — only if we want scipy.stats.norm for comparison
```

No new required dependencies beyond what is already in the scaffold (`numpy`, `pandas`, `pyarrow`).

Add to `[project.scripts]`:

```
hist-var-pandas = "var_simulations.cli_pandas:main"
```

---

## Test strategy

`tests/pandas_var/`

| Test | What it checks |
|---|---|
| `test_loader.py` | load functions return expected dtypes and row counts |
| `test_engine_market_values.py` | iterrows loop produces correct mkt_value = qty × price |
| `test_engine_pnl.py` | P&L for a 1-position portfolio equals qty × price × return exactly |
| `test_engine_var_es.py` | `compute_var_es` on a known monotone P&L list: VaR = 5th worst at 99% (index 4 of 500); ES = mean of tail including that scenario |
| `test_integration.py` | end-to-end against fixture data; assert portfolio VaR 99% ≈ 3 181 345 (±5%) |

---

## Run commands

```bash
cd financial_quant/var_simulations
uv sync
uv run hist-var-pandas --data-dir ../simulated_data_lab/data/var_demo --output-dir output
```

---

## Contrast summary (vs Polars plan)

| Dimension | This implementation |
|---|---|
| Data loading | `pd.read_parquet` — eager, all rows in memory immediately |
| Market value | `iterrows` loop — one Python dict per row |
| P&L calculation | Nested Python loops — 250 000 multiplications in interpreter |
| Breakdown | Loop over unique keys, re-filter DataFrame per group |
| VaR/ES | Python `sorted()` + manual index |
| Memory layout | NumPy row-major (C order) under the hood; pandas copies data on column ops |
| Parallelism | Single-threaded; GIL prevents parallelism across Python loops |
| Query planning | None — every operation executes immediately as written |
