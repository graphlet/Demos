# AI Instructions Index

This file is the central map for AI tooling behavior in this repository.
It documents where instructions live, how scope is resolved, and how conflicts are handled.

## Purpose

- Provide one source of truth for agent instruction discovery.
- Keep Copilot and Claude workflows aligned across subprojects.
- Make prompt and skills folders explicit as reference libraries unless invoked.

## Agent Coverage Map

| Agent | Scope | Primary instructions | Prompt/skills library | Notes |
|---|---|---|---|---|
| GitHub Copilot | Repository-wide | `.github/copilot-instructions.md` | `financial_quant/simulated_data_lab/ai/copilot/prompts/` | Prompt library is reference content unless explicitly used in a task. |
| Claude Code | Repository baseline + nearest subproject override | `CLAUDE.md` plus nearest subproject `CLAUDE.md` | `financial_quant/simulated_data_lab/ai/claude/prompts/` | Prompt library is reference content unless explicitly used in a task. |
| Shared playbooks | Simulated data lab workflows | `financial_quant/simulated_data_lab/ai/skills/` | `financial_quant/simulated_data_lab/ai/skills/README.md` | Skills directory is a reusable knowledge workspace, not an auto-registered runtime catalog. |

## Deterministic Precedence Order

Apply rules in this order:

1. Safety and platform policy.
2. Active agent baseline instructions:
   - Copilot: `.github/copilot-instructions.md`
   - Claude: `CLAUDE.md`
3. Nearest scoped subproject guidance (for example `financial_quant/simulated_data_lab/CLAUDE.md`).
4. Explicitly selected prompt templates from `ai/copilot/prompts/` or `ai/claude/prompts/`.
5. Reusable skills and playbooks under `ai/skills/`.

## Conflict Resolution Matrix

| Rule ID | Situation | Winner | Action |
|---|---|---|---|
| CR-01 | Global vs subproject guidance conflict | Narrower scope | Use the subproject file for that subtree. |
| CR-02 | Two scoped files overlap | Nearest path | Use the guidance file closest to the target files. |
| CR-03 | Instruction file vs prompt template conflict | Instruction file | Treat prompt templates as optional helpers, not policy. |
| CR-04 | Copilot guidance vs Claude guidance conflict | Active agent native instruction | Use the active agent's native instruction file(s). |
| CR-05 | Repo policy vs local optimization | Repo policy | Apply policy first, then optimize within constraints. |
| CR-06 | Older scoped guidance vs newer scoped guidance | Newer reviewed guidance | Prefer newer reviewed guidance and update this index if needed. |
| CR-07 | Ambiguous cross-subproject ownership | Shared contract | Promote reusable rule into shared guidance and reference from both scopes. |
| CR-08 | Prompt library appears stricter than policy docs | Policy docs | Migrate the validated rule into policy docs before enforcing broadly. |
| CR-09 | Missing guidance for a new subtree | Baseline instructions | Use baseline until scoped guidance is added. |
| CR-10 | Safety/compliance vs project-specific instruction | Safety/compliance | Safety and platform policy always override. |

## Tie-Break Rules

If conflicts remain after precedence and matrix resolution:

1. Prefer narrower scope over broader scope.
2. Prefer explicit constraints over stylistic preferences.
3. Prefer newer reviewed guidance over older unreviewed guidance.
4. If still tied, prefer behavior-preserving changes and document clarification in this file.

## Onboarding Flow

1. Identify the target scope (repo-wide or subproject).
2. Load baseline instruction file(s) for the active agent.
3. Load nearest scoped guide (if present).
4. Optionally select prompt templates from the relevant `ai/` prompt library.
5. Use `ai/skills/` playbooks for repeatable domain workflows.

## Maintenance Checklist

When adding new AI guidance files:

1. Add the file path to this index.
2. Declare scope and ownership.
3. Mark whether the file is policy or reference.
4. Add a last-reviewed date.
5. Confirm no conflict with `.github/copilot-instructions.md` and root `CLAUDE.md`.

## Current File Map

- Copilot baseline: `.github/copilot-instructions.md`
- Claude baseline: `CLAUDE.md`
- Simulated data lab scoped guide: `financial_quant/simulated_data_lab/CLAUDE.md`
- Copilot prompts library: `financial_quant/simulated_data_lab/ai/copilot/prompts/`
- Claude prompts library: `financial_quant/simulated_data_lab/ai/claude/prompts/`
- Shared skills library: `financial_quant/simulated_data_lab/ai/skills/`