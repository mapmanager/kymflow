# How to Add a New Experimental Metadata Attribute

This recipe describes how to add a new editable field to `ExperimentMetadata`, which is the user-provided experimental metadata stored per kymograph file. Follow this guide to ensure all touchpoints are updated and the API/runtime flow stays intact.

---

## Overview: Architecture and Touchpoints

### Data Flow Summary

```
JSON file (metadata.json)  ←→  ExperimentMetadata dataclass  ←→  AcqImage._experiment_metadata
                                    ↑
                                    │ form_schema() drives dynamic form
                                    │
                    MetadataExperimentalView (drawer form)
                                    │
                    MetadataController (intent → file.update_experiment_metadata)
                                    │
                    KymImage.getRowDict()  →  FileTableView (table columns)
```

### Separation of Concerns

- **Core (`kymflow/core/`)**: Defines the schema, serialization, and data model. No UI logic.
- **GUI (`kymflow/gui_v2/`)**: Consumes the schema and renders forms/tables. Uses `form_schema()` and `getRowDict()` for dynamic behavior.

### Touchpoints When Adding an Attribute

| Layer | File | What It Does |
|-------|------|--------------|
| Core schema | `core/image_loaders/metadata.py` | `ExperimentMetadata` dataclass — add the field |
| Core serialization | `metadata.py` | `to_dict()` / `from_dict()` — auto via `asdict()` for most fields |
| Core row dict | `core/image_loaders/kym_image.py` | `KymImage.getRowDict()` — add key for table display |
| GUI table | `gui_v2/views/file_table_view.py` | `_default_columns()` — add column config |
| GUI form | `gui_v2/views/metadata_experimental_view.py` | Uses `form_schema()` — no change needed |
| GUI controller | `gui_v2/controllers/metadata_controller.py` | Uses `update_experiment_metadata(**fields)` — no change needed |
| Docs | `docs/file-formats.md` | Update ExperimentMetadata table |
| Tests | `tests/core/test_metadata.py` | Update `from_dict`, `to_dict`, `form_schema` tests |

---

## Section 1: Updating Core Source Code

### 1.1 Add Field to ExperimentMetadata

**File:** `kymflow/src/kymflow/core/image_loaders/metadata.py`

1. Add the field to the `ExperimentMetadata` dataclass, following existing patterns.
2. Place it logically (e.g., near related fields like `condition`, `treatment`).
3. Use `field_metadata()` for UI hints: `editable`, `label`, `widget_type`, `grid_span`.

**Example pattern:**

```python
my_new_field: Optional[str] = field(
    default="",
    metadata=field_metadata(
        editable=True,
        label="My New Field",
        widget_type="text",   # or "number", "multiline"
        grid_span=1,
    ),
)
```

4. Update the class docstring `Attributes` section to include the new field.

**Serialization:** `to_dict()` uses `asdict(self)`, so new fields are included automatically. `from_dict()` uses `payload.keys() & valid`, so new fields are loaded if present in the payload. No code changes needed for standard fields.

**Exception:** If you need non-standard serialization (e.g., key renaming like `acquisition_date` → `acq_date`), you must update both `to_dict()` and `from_dict()`.

### 1.2 Add Field to getRowDict()

**File:** `kymflow/src/kymflow/core/image_loaders/kym_image.py`

1. In `KymImage.getRowDict()`, add a key to the `result` dict that maps to the new experiment metadata field.
2. Use the same key name as the field for consistency (table columns reference this key).
3. Use `self.experiment_metadata.<field> or "-"` for display (empty becomes `"-"`).

**Note:** `AcqImage.getRowDict()` (base class) does not include experiment metadata — only `KymImage` does. If you add metadata to a different image type, update that type’s `getRowDict()` override.

### 1.3 Update Tests

**File:** `kymflow/tests/core/test_metadata.py`

1. **`test_experiment_metadata_from_dict`**: Add the new field to the payload and assert it loads correctly.
2. **`test_experiment_metadata_to_dict`**: Create metadata with the new field and assert it appears in the output.
3. **`test_experiment_metadata_form_schema`**: Add the new field name to the `field_names` assertions.

### 1.4 Update Documentation

**File:** `kymflow/docs/file-formats.md`

Add the new field to the ExperimentMetadata table (name, display_name, default_value, description).

---

## Section 2: Updating GUI Source Code

### 2.1 Add Column to File Table

**File:** `kymflow/src/kymflow/gui_v2/views/file_table_view.py`

1. In `_default_columns()`, add a `_col()` call for the new field.
2. Use the same field name as in `getRowDict()`.
3. Set `header`, `filterable`, `flex`, `min_width` as appropriate.

**Example:**

```python
_col("my_new_field", "My New Field", filterable=True, flex=1, min_width=100),
```

**Placement:** Group with other experimental metadata columns (e.g., near `condition`, `treatment`, `date`) for consistency.

### 2.2 No Changes Needed

- **MetadataExperimentalView**: Builds the drawer form from `ExperimentMetadata.form_schema()`. New fields appear automatically.
- **MetadataController**: Calls `file.update_experiment_metadata(**e.fields)`. Works for any attribute that exists on `ExperimentMetadata`.
- **AcqImage.update_experiment_metadata()**: Uses `hasattr`/`setattr` on the schema; new fields are supported automatically.

---

## Red Flags: What Can Break

### API / Runtime

1. **`to_dict` / `from_dict` asymmetry**
   - `to_dict()` renames `acquisition_date` → `acq_date` and `acquisition_time` → `acq_time`.
   - `from_dict()` expects field names (`acquisition_date`, `acquisition_time`), not `acq_date`/`acq_time`.
   - JSON saved with `to_dict` will not round-trip `acquisition_date`/`acquisition_time` correctly unless `from_dict` is updated to accept `acq_date`/`acq_time`.
   - **Rule:** If you add custom key renaming in `to_dict()`, you must add matching handling in `from_dict()`.

2. **Field name mismatches**
   - `getRowDict()` keys must match `_default_columns()` `field` values exactly.
   - Typos or renames in one place will show empty or broken columns.

3. **Base vs subclass `getRowDict()`**
   - `AcqImage.getRowDict()` does not include experiment metadata.
   - `KymImage.getRowDict()` does. If you add a new image type with experiment metadata, override `getRowDict()` there.

4. **Tests depend on schema**
   - `test_experiment_metadata_form_schema` checks for specific field names. Add new fields to the assertion list.

### Future Devs / LLMs

- Do not add fields to `AcqImgHeader` when you mean experimental metadata. `AcqImgHeader` is technical image metadata (shape, voxels, labels). Use `ExperimentMetadata` for experimental/biological metadata.
- Do not assume all `getRowDict()` consumers use the same keys. Some code may filter or transform; verify any downstream uses.
- When removing a field: remove from dataclass, `getRowDict()`, `_default_columns()`, tests, and docs. Old JSON files may still contain the key; `from_dict` will ignore it.

---

## Critique: Core Architecture

### Strengths

- Clear separation: `ExperimentMetadata` is a dataclass with schema-driven behavior.
- `form_schema()` enables form generation without hardcoding fields in the GUI.
- `from_dict` ignores unknown keys, which helps with forward compatibility.

### Pain Points and Refactor Ideas

1. **`getRowDict()` duplication**
   - `AcqImage` and `KymImage` each define `getRowDict()` with different shapes. Experimental metadata is only in `KymImage`.
   - **Refactor idea:** Introduce a mixin or helper that builds the experiment-metadata portion from `ExperimentMetadata` fields, so adding a field doesn’t require editing `getRowDict()`.

2. **Manual wiring in `getRowDict()`**
   - Each new metadata field requires a manual line in `KymImage.getRowDict()`.
   - **Refactor idea:** Iterate over `ExperimentMetadata.form_schema()` or field names and build the dict from `getattr(meta, name)`. Keeps schema as single source of truth.

3. **`to_dict` key renaming**
   - Special cases (`acq_date`, `acq_time`) live inside `to_dict()` but `from_dict()` doesn’t reverse them.
   - **Refactor idea:** Add a mapping layer (e.g., `_SERIALIZE_KEY_MAP`) used by both `to_dict` and `from_dict`, or document and fix the asymmetry.

4. **No schema versioning**
   - JSON has `"version": "1.0"` at the top level, but schema migrations are not defined.
   - **Refactor idea:** Add version handling for `ExperimentMetadata` to support renames or structural changes over time.

---

## Critique: GUI Architecture

### Strengths

- Event-driven flow: intent → controller → file → state → views.
- `form_schema()` avoids hardcoding form fields in the view.
- `MetadataController` stays generic; no field-specific logic.

### Pain Points and Refactor Ideas

1. **Table columns decoupled from schema**
   - `_default_columns()` is a separate list that must stay in sync with `getRowDict()` keys.
   - **Refactor idea:** Derive column configs from a schema (e.g., a subset of `form_schema()` or a dedicated “table schema”) so new fields don’t require edits in multiple places.

2. **No single source of truth for “which fields go in the table”**
   - Today: add to `getRowDict()` and `_default_columns()` independently.
   - **Refactor idea:** Define “table fields” in one place (e.g., list of field names) and generate both the row dict slice and the column configs from it.

3. **`MetadataExperimentalView` and `MetadataHeaderView` share patterns**
   - Both use `form_schema()`, `set_selected_file()`, `_on_field_blur`, etc.
   - **Refactor idea:** Extract a generic “metadata form view” that takes a schema supplier and callbacks, then specialize for experimental vs header metadata.

4. **Blinding and display logic in `getRowDict()`**
   - Blinding, path-derived fields, and metadata are mixed in one method.
   - **Refactor idea:** Split into smaller helpers (e.g., `_blinded_path_info()`, `_metadata_row_slice()`) to clarify responsibilities and simplify changes.
