# ui.select preset + free-entry + controller + AG Grid (NiceGUI 3.7.1)

This mini-demo shows a robust pattern for editable metadata UIs:

**Pattern**
1) **View** (widgets) proposes a change  
2) **Controller** mutates the canonical in-memory model (a pandas `DataFrame`)  
3) Controller emits a **changed event**  
4) View updates:
   - other widgets (e.g. option lists)
   - **AG Grid efficiently** using a **row-level update** (`applyTransaction`) instead of full `rowData` refreshes

This maps closely to your architecture:
`view -> signal/event -> controller -> mutate -> emit -> views refresh`

---

## Files

- `demo_ui_select_controller_aggrid.py` — runnable demo
- `README_dev.md` — this file

---

## How to run

```bash
uv run python demo_ui_select_controller_aggrid.py
```

---

## What to click

### Left panel
- **Condition (preset-only)**: choose an existing condition
- **Condition (preset + type new)**: choose OR type a new value, hit Enter  
Both go through the controller and mutate the DataFrame.

### Grid (right)
- **Double-click a row** to open an edit dialog.
- Change condition/treatment/genotype and hit **Save**.
- Each changed field goes through the controller and triggers a **row-level grid update**.

### Buttons
- **Full refresh**: re-sends the entire dataset (slow / avoid for large apps)
- **Random mutate 1 row**: controller path, updates one row

---

## Key AG Grid requirement

To update a single row, AG Grid needs a stable row identity function:

```python
"getRowId": {"function": "params.data.id"}
```

Then update one row:

```python
grid.run_grid_method("applyTransaction", {"update": [updated_row_dict]})
```

---

## Why this demo uses a dialog instead of in-cell editors

In-cell editors that embed `ui.select` are possible but more JS-heavy and more version-sensitive.
A **row double-click → edit dialog** approach is typically more robust and easier to maintain.
