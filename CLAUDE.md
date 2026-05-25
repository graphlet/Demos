# Repository Guide

## Architecture overview

This repository contains independent Python demo subprojects:
- digital_assets: Streamlit app for crypto and tokenomics demos
- financial_quant: Streamlit app for quantitative finance demos
- financial_quant/simulated_data_lab: config-driven synthetic dataset generator
- shared: common utilities intended for reuse across subprojects

## Conventions

- Package and environment management is done with uv.
- Dependencies live in each subproject `pyproject.toml`.
- Run project commands with `uv run ...` from the target subproject.
- Keep business logic in `src/` packages as projects mature; keep UI entrypoints small.

## Cross-project rules

- Avoid importing directly across subprojects unless a module is promoted into `shared`.
- Reusable utilities should move into `shared/src/shared/`.
- Keep README setup instructions concise and uv-first.
- Add project-specific guidance in each subproject `CLAUDE.md`.
