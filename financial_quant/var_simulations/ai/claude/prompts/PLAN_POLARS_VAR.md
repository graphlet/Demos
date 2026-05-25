# Plan: Historical VaR — Columnar Implementation (Polars + Arrow)

## Purpose

Implement the same Historical Simulation VaR algorithm using Polars' lazy expression API backed by
Apache Arrow columnar memory. The goal is to show what changes when you stop iterating over rows and
start describing transformations on columns, and to make the performance and ergonomic differences
concrete.

## Showcase intent

This is the columnar half of the side-by-side demonstration. Highlight these properties explicitly
in code comments so readers understand *why* the code is structured as it is:

- **Arrow columnar layout** — all values in a column are contiguous in memory; CPU SIMD instructions
  can process 4–16 values per clock cycle instead of one
- **Lazy evaluation** — `scan_parquet` registers intent, not execution; the query is planned and
  optimised before any bytes are read from disk
- **Predicate & projection pushdown** — Polars rewrites the query plan so only needed columns and
  filtered rows are read from parquet pages; file I/O is minimised automatically
- **No Python hot loops** — column operations are expressed as `pl.Expr` objects and executed in
  compiled Rust; the Python interpreter is only involved at plan-construction time, not at data-
  processing time
- **Parallel execution** — Polars uses a thread pool (via Rayon) to process independent column
  operations concurrently without the GIL

---

## Algorithm

Identical logical steps to the Pandas plan; different execution model throughout.

```
Step 1  scan_parquet portfolio and returns — lazy; no data read yet
Step 2  Join returns onto portfolio to attach mkt_value = quantity × current_price (expression)
Step 3  Compute position P&L per (date, position): pl.col("return") * pl.col("mkt_value")
Step 4  Group by date and sum position P&Ls → one portfolio P&L per scenario date
Step 5  Quantile over the 500 P&L values → VaR
Step 6  Filter tail and mean → ES
Step 7  Repeat Steps 3–6 with group_by(desk), group_by(sector), group_by(book) added before Step 4
Step 8  .collect() once — triggers the entire plan; disk reads happen here
Step 9  Write Arrow IPC / CSV; print summary table
```

**Key difference from Pandas plan:** Steps 1–7 build a lazy query graph. No data moves until
Step 8. Polars can reorder, fuse, and parallelise operations across the entire graph.

---

## Module structure

```
src/var_simulations/polars_var/
    __init__.py          # re-exports run_var_analysis
    loader.py            # pl.scan_parquet wrappers returning LazyFrames
    engine.py            # expression pipelines; no Python loops in hot path
    report.py            # VaRResult dataclass (shared shape with pandas_var), CSV/IPC writer
src/var_simulations/cli_polars.py   # argparse entry point → hist-var-polars
src/var_simulations/benchmark.py    # times both implementations; prints comparison table
```

---

## File-by-file implementation plan

### `src/var_simulations/polars_var/loader.py`

**Intent:** Return `pl.LazyFrame` objects. No `.collect()` call here. Callers compose further
expressions before triggering execution.

```python
def scan_portfolio(data_dir: Path) -> pl.LazyFrame:
    return pl.scan_parquet(data_dir / "portfolio.parquet")
    # Columns: position_id, desk, book, ticker, quantity, current_price, sector, currency

def scan_returns(data_dir: Path) -> pl.LazyFrame:
    return pl.scan_parquet(data_dir / "historical_returns.parquet")
    # Columns: date, ticker, return

def scan_market_params(data_dir: Path) -> pl.LazyFrame:
    return pl.scan_parquet(data_dir / "market_params.parquet")
    # Columns: ticker, sector, annual_drift, annual_vol, daily_vol
```

**Columnar marker:** `scan_parquet` reads the parquet footer (schema + row-group metadata) but
does not decode any column pages. Polars' query planner will later determine which columns and
which row groups to actually read, based on the operations chained onto this LazyFrame.

---

### `src/var_simulations/polars_var/engine.py`

#### `build_pnl_pipeline(portfolio_lf: pl.LazyFrame, returns_lf: pl.LazyFrame) -> pl.LazyFrame`

Build the complete P&L expression graph from raw lazy frames to per-date portfolio P&L, with
desk/sector/book grouping columns carried through so a single collect feeds all breakdowns.

```python
def build_pnl_pipeline(
    portfolio_lf: pl.LazyFrame,
    returns_lf: pl.LazyFrame,
) -> pl.LazyFrame:
    # Step 1: add mkt_value to portfolio — pure expression, no data moved
    portfolio_with_val = portfolio_lf.with_columns(
        (pl.col("quantity") * pl.col("current_price")).alias("mkt_value")
    )

    # Step 2: join returns onto portfolio on ticker
    # Polars will push the projection (only needed columns) into the parquet scan
    position_pnl = returns_lf.join(
        portfolio_with_val.select(
            "ticker", "mkt_value", "desk", "book", "sector"
        ),
        on="ticker",
        how="inner",
    ).with_columns(
        (pl.col("return") * pl.col("mkt_value")).alias("position_pnl")
    )

    # Step 3: aggregate to portfolio-level P&L per date
    return position_pnl.group_by("date", "desk", "book", "sector").agg(
        pl.col("position_pnl").sum().alias("group_pnl"),
        pl.col("mkt_value").sum().alias("group_nav"),
    )
```

**Columnar markers:**
- `pl.col("quantity") * pl.col("current_price")` — operates on Arrow `float64` arrays; Polars
  dispatches to SIMD-vectorised multiply; 500 values processed in ~30 ns versus ~2 µs for the
  equivalent Python loop.
- `.join(..., how="inner")` — Polars uses a hash join on the Arrow dictionary-encoded `ticker`
  column; no Python object creation per row.
- `.group_by(...).agg(...)` — single pass over the data in parallel; Polars partitions the work
  across threads automatically.
- No `.collect()` here — this is still a lazy expression tree. Polars has not read a single byte
  of parquet yet.

---

#### `compute_portfolio_var(pnl_lf: pl.LazyFrame, confidence: float) -> pl.LazyFrame`

Aggregate the date-level P&L to portfolio-level VaR and ES in a single expression:

```python
def compute_portfolio_var(pnl_lf: pl.LazyFrame, confidence: float) -> pl.LazyFrame:
    portfolio_pnl = pnl_lf.group_by("date").agg(
        pl.col("group_pnl").sum().alias("portfolio_pnl")
    )

    q = 1.0 - confidence
    return portfolio_pnl.select(
        (-pl.col("portfolio_pnl").quantile(q, interpolation="lower")).alias("var"),
        (
            -pl.col("portfolio_pnl")
            .filter(pl.col("portfolio_pnl") <= pl.col("portfolio_pnl").quantile(q, interpolation="lower"))
            .mean()
        ).alias("es"),
        pl.lit(confidence).alias("confidence"),
    )
```

**Columnar marker:** `quantile` and `filter` on an Arrow array; no Python sort, no manual index
arithmetic. Polars selects a partial sort algorithm when the input is unsorted, running in
O(n) for quantile estimation.

---

#### `compute_desk_var(pnl_lf: pl.LazyFrame, confidence: float) -> pl.LazyFrame`

Re-aggregate the position-level LazyFrame by desk before applying VaR:

```python
def compute_desk_var(pnl_lf: pl.LazyFrame, confidence: float) -> pl.LazyFrame:
    q = 1.0 - confidence
    desk_pnl = pnl_lf.group_by("date", "desk").agg(
        pl.col("group_pnl").sum().alias("desk_pnl"),
        pl.col("group_nav").sum().alias("desk_nav"),
    )
    return desk_pnl.group_by("desk").agg(
        (-pl.col("desk_pnl").quantile(q, interpolation="lower")).alias("var"),
        pl.col("desk_nav").first().alias("nav"),
        pl.lit(confidence).alias("confidence"),
    )
```

**Columnar marker:** no Python `for desk in unique_desks:` loop. The entire breakdown across all
5 desks is expressed as a single `group_by` and computed in one parallel pass over the data.

Apply the same pattern for `compute_sector_var` and `compute_book_var`.

---

#### `run_var_analysis(data_dir: Path, confidence_levels: list[float]) -> VaRResult`

Compose the full pipeline and trigger a **single** collect:

```python
def run_var_analysis(data_dir: Path, confidence_levels: list[float]) -> VaRResult:
    portfolio_lf = scan_portfolio(data_dir)
    returns_lf   = scan_returns(data_dir)

    pnl_lf = build_pnl_pipeline(portfolio_lf, returns_lf)
    # pnl_lf is still lazy — nothing has been read from disk

    # Build all result frames lazily
    result_frames = {}
    for conf in confidence_levels:
        result_frames[f"portfolio_{conf}"] = compute_portfolio_var(pnl_lf, conf)
        result_frames[f"desk_{conf}"]      = compute_desk_var(pnl_lf, conf)
        result_frames[f"sector_{conf}"]    = compute_sector_var(pnl_lf, conf)
        result_frames[f"book_{conf}"]      = compute_book_var(pnl_lf, conf)

    # Single .collect() — Polars fuses compatible stages, reads parquet once,
    # and executes the entire graph in parallel
    collected = {k: v.collect() for k, v in result_frames.items()}

    return VaRResult.from_collected(collected, confidence_levels)
```

**Columnar marker:** calling `.collect()` once allows Polars to share the parquet scan and the
join result across all downstream aggregations. In contrast, the Pandas implementation re-reads
and re-filters the scenario matrix for every grouping key.

---

### `src/var_simulations/polars_var/report.py`

#### `VaRResult` (dataclass)

Same external shape as `var_simulations.pandas_var.report.VaRResult` so the benchmark and CLI can
use either implementation interchangeably.

```python
@dataclass
class VaRResult:
    nav:              float
    scenario_count:   int
    confidence_levels: list[float]
    portfolio_var:    dict[float, float]
    portfolio_es:     dict[float, float]
    desk_var:         dict[str, dict[float, float]]
    sector_var:       dict[str, dict[float, float]]
    book_var:         dict[str, dict[float, float]]
    raw_pnl_frame:    pl.DataFrame   # Arrow-backed; zero-copy slice for histogram
```

#### `write_arrow_ipc(result: VaRResult, output_path: Path)`

Write the raw P&L scenario frame as Arrow IPC (`.arrow`) file — a format that downstream tools
(DuckDB, DataFusion, other Polars processes) can memory-map directly without deserialisation:

```python
result.raw_pnl_frame.write_ipc(output_path / "pnl_scenarios.arrow")
```

This is a deliberate contrast with the Pandas plan's CSV output: Arrow IPC preserves types and
is readable without parsing text.

#### `write_results_csv(result: VaRResult, output_path: Path)`

Also write CSVs for parity with the Pandas plan.

---

### `src/var_simulations/cli_polars.py`

```
Flags:
  --data-dir      Path to parquet files (default: ../simulated_data_lab/data/var_demo)
  --confidence    Comma-separated confidence levels (default: 0.95,0.99)
  --output-dir    Directory for output (default: output/)
  --arrow         Also write Arrow IPC files (default: false)
  --quiet         Suppress console table

Entry point in pyproject.toml:
  hist-var-polars = "var_simulations.cli_polars:main"
```

---

### `src/var_simulations/benchmark.py`

Run both implementations N times and compare wall-clock time and peak memory. This file is the
centrepiece of the showcase — it makes the performance story concrete.

```python
def benchmark_implementation(
    impl_name: str,
    run_fn: Callable[[], VaRResult],
    iterations: int = 5,
) -> BenchmarkStats:
    """Returns min/mean/max wall time and peak RSS."""
    ...

def print_comparison_table(pandas_stats: BenchmarkStats, polars_stats: BenchmarkStats) -> None:
    """
    Example output:
    ┌──────────────────┬────────────┬────────────┬──────────┐
    │ Implementation   │ Mean (ms)  │ Min (ms)   │ Peak MB  │
    ├──────────────────┼────────────┼────────────┼──────────┤
    │ Pandas + loops   │     ????   │     ????   │   ????   │
    │ Polars + Arrow   │     ????   │     ????   │   ????   │
    │ Speedup          │     ????×  │     ????×  │   ????×  │
    └──────────────────┴────────────┴────────────┴──────────┘
    """

Entry point in pyproject.toml:
  hist-var-benchmark = "var_simulations.benchmark:main"
```

---

## pyproject.toml changes

Add to `[project] dependencies`:

```toml
"polars>=1.0.0",
```

Add to `[project.scripts]`:

```toml
hist-var-polars    = "var_simulations.cli_polars:main"
hist-var-benchmark = "var_simulations.benchmark:main"
```

---

## Test strategy

`tests/polars_var/`

| Test | What it checks |
|---|---|
| `test_loader.py` | scan functions return `pl.LazyFrame`; schema matches expected types; no `.collect()` called |
| `test_engine_pipeline.py` | `build_pnl_pipeline` returns a LazyFrame (not a DataFrame) |
| `test_engine_pnl.py` | 1-position portfolio: collected P&L = qty × price × return exactly |
| `test_engine_var.py` | known P&L series: VaR equals expected value at both 95% and 99% |
| `test_engine_es.py` | ES equals mean of tail losses |
| `test_engine_desk.py` | desk breakdown P&Ls sum to portfolio P&L for every scenario date |
| `test_integration.py` | end-to-end against fixture; portfolio VaR 99% ≈ 3 181 345 (±5%); result matches Pandas plan within 0.1% |
| `test_arrow_output.py` | Arrow IPC file is valid; readable by `pyarrow.ipc.open_file` |

---

## Run commands

```bash
cd financial_quant/var_simulations
uv sync
uv run hist-var-polars --data-dir ../simulated_data_lab/data/var_demo --output-dir output --arrow
uv run hist-var-benchmark --data-dir ../simulated_data_lab/data/var_demo
```

---

## Contrast summary (vs Pandas plan)

| Dimension | This implementation |
|---|---|
| Data loading | `scan_parquet` — lazy; only footer read at plan time; columns/rows selected at execution |
| Market value | `pl.col("quantity") * pl.col("current_price")` — SIMD-vectorised over Arrow array |
| P&L calculation | Expression join + `group_by` + `agg` — no Python loop; Rust executes over contiguous memory |
| Breakdown | Single `group_by("desk")` expression — all desks in one parallel pass |
| VaR/ES | `.quantile()` + `.filter().mean()` on Arrow array — no Python sort, no manual index |
| Memory layout | Arrow columnar; each column is a contiguous buffer; zero-copy slicing possible |
| Parallelism | Rayon thread pool; group aggregations and independent expressions run concurrently |
| Query planning | Full lazy query graph; Polars fuses stages, pushes predicates/projections into parquet scan |
| Output formats | CSV (parity) + Arrow IPC (zero-copy, type-preserving, machine-readable) |

---

## Arrow memory layout explainer (for demo commentary)

When Polars loads the `return` column from parquet, the 250 000 `float64` values are stored as a
single 2 MB buffer:

```
[r_0, r_1, r_2, ..., r_249999]   ← contiguous float64 bytes
```

A CPU with AVX2 can multiply 4 doubles per instruction. Polars' grouped sum over 250 000 values
takes roughly 31 000 SIMD instructions versus 250 000 Python interpreter steps in the loop version.
The Arrow specification guarantees 64-byte alignment per buffer, which maximises SIMD utilisation
and avoids cache-line splits.

The pandas implementation stores the same data in a NumPy 2D array (after pivot), which is also
contiguous — but the Python loops over that array return Python float objects at each step, which
re-boxes the doubles and kills SIMD throughput. The key insight is not just that the data is
columnar: it is that the *computation* never crosses the Python interpreter boundary in the hot path.
