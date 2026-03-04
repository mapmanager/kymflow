# codex_rules.md (Fail-fast, single source of truth)

## Scope / boundaries
- `sandbox/diameter-analysis/` is the working area for Codex tickets.
- **DO NOT MODIFY** anything under `kymflow/` (treat it as a vendor dependency).

## Source of truth
- Treat the files uploaded/mentioned in the ticket as the *only* current source of truth.
- If a required file is missing or ambiguous, **ask for it**. Do not guess.

## No “helpful” backward compatibility unless explicitly requested
- **Do not add** default values or fallbacks “for back-compat” (e.g. `row.get(..., default)`), **unless the ticket explicitly asks for it**.
- Prefer **fail-fast** behavior:
  - required fields: use `row["field"]` (KeyError is fine)
  - required types: validate and raise `ValueError` with a clear message
  - avoid blanket `try/except` guards that hide errors

## API contracts
- If a parameter is required at the entrypoint (e.g. `analyze(..., roi_id, roi_bounds, channel_id)`), then:
  - it must remain required throughout results/serialization/loading
  - result types must be non-optional
  - loaders must reject missing required fields

## Refactor hygiene
- Keep changes minimal and local to the ticket scope.
- Remove dead code and dead tests when the referenced module no longer exists.
- Update unit tests to match new contracts (prefer small, direct tests).

## Logging
- Preserve existing `import logging; logger = logging.getLogger(__name__)` patterns.
- Do not delete logging just to satisfy “unused import” concerns.

## GUI boundary rule (when relevant)
- Only `gui/controllers.py` may import/use `gui/diameter_kymflow_adapter.py`.
- No other `gui/*` modules should import kymflow facade APIs or the adapter.
