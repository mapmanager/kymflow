
# Ticket 042 — Remove legacy JSON-results save/load path

Goal: remove the old JSON-results serialization pathway and keep a single metadata-only JSON + CSV results system.

Summary:
- CSV = source of truth for numeric analysis results
- JSON = metadata only (schema_version, source_path, rois)

Required changes:
1. Remove legacy save/load functions that serialize per-row results in JSON.
2. Delete JSON structures containing 'runs' or 'results'.
3. Ensure GUI calls only the new serialization path.
4. Remove any JSON↔CSV integrity comparison logic.
5. Update tests to expect metadata-only JSON and CSV-based results.

Acceptance criteria:
- Only one save/load path remains.
- JSON contains only schema_version, source_path, rois.
- CSV stores all numeric results.
- GUI detect→save→reload workflow functions.
- Tests updated and passing.

Non-goals:
- No backward compatibility
- No legacy schema parsing
