# Skills workspace

Write reusable skills and playbooks here for repeated quant-data tasks.

Recommended convention:
- one folder per skill
- include `SKILL.md`
- keep examples and edge cases in same folder

Example layout:

```text
ai/skills/
  ohlcv-generator/
    SKILL.md
    examples.md
  options-surface-generator/
    SKILL.md
```

Suggested `SKILL.md` template:

```markdown
# Skill name

## Purpose
What this skill helps generate or validate.

## Inputs
Required config keys, schema assumptions, and constraints.

## Outputs
Expected files, column definitions, and quality checks.

## Steps
Deterministic implementation flow.

## Pitfalls
Common mistakes and how to avoid them.
```
