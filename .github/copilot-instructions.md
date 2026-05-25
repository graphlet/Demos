# Copilot Repository Instructions

## Context

This is a multi-project Python repository managed with uv.

Subprojects:
- digital_assets
- financial_quant
- financial_quant/simulated_data_lab
- shared (common reusable utilities)

## Working rules

- Prefer minimal, focused changes.
- Keep setup and run instructions uv-first.
- Do not reintroduce requirements.txt files for uv-managed projects.
- Preserve existing Streamlit app behavior unless a change is requested.
- Put reusable logic in `shared/src/shared/` when it benefits multiple subprojects.

## Validation

- For syntax checks, use `python3 -m compileall` on touched modules.
- Prefer project-local commands executed from each subproject directory.
