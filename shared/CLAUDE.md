# shared Guide

## Ownership

Hosts reusable modules that are safe to consume across multiple subprojects.

## API and contracts

- Public shared modules live in `src/shared/`.
- Keep dependencies minimal and broadly compatible.
- Avoid subproject-specific assumptions in shared code.

## Validation

```bash
python3 -m compileall src
```
