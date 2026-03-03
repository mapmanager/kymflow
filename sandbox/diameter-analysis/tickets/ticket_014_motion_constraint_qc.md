
# Ticket 014 — Motion Constraint QC + Detection Reset + Serialization Planning

## Summary

Introduce biologically informed motion constraints into `GRADIENT_EDGES` detection, 
add UI reset capability for Detection Params, and prepare architecture for 
future serialization of detection parameters and results.

This ticket focuses strictly on:

1. Motion constraint QC logic (core algorithm layer)
2. UI integration (Detection Params card additions)
3. Factory reset button for detection params
4. Serialization scaffolding planning (no heavy implementation yet)

---

# Part 1 — Motion Constraint QC (Gradient Edges Only)

## Scope

Applies only to:

    DiameterMethod.GRADIENT_EDGES

Does NOT apply to:

    DiameterMethod.THRESHOLD_WIDTH

---

## New Detection Params

Add to `DiameterDetectionParams`:

```python
enable_motion_constraints: bool = True

max_edge_shift_um: float = 2.0
max_diameter_change_um: float = 2.0
max_center_shift_um: float = 2.0
```

All units in µm.

If `enable_motion_constraints == False`, skip all constraint logic.

---

## Constraint Definitions

Given:

- left_um[t]
- right_um[t]
- diameter_um[t] = right - left
- center_um[t] = (right + left) / 2

### Edge Constraint (independent)

If:

abs(left[t] - left[t-1]) > max_edge_shift_um

→ Set left[t] = NaN  
→ Flag QC

Right edge remains unchanged.

Same independently for right edge.

---

### Diameter Constraint

If:

abs(diameter[t] - diameter[t-1]) > max_diameter_change_um

→ Set BOTH edges at t to NaN  
→ Flag QC

---

### Center Constraint

If:

abs(center[t] - center[t-1]) > max_center_shift_um

→ Set BOTH edges at t to NaN  
→ Flag QC

---

## Violation Handling

For any violation:

1. Flag QC (add boolean arrays to results)
2. Set offending values to NaN
3. Do NOT auto-correct or clamp

Downstream smoothing/post-filter will handle interpolation in later tickets.

---

## Result Additions

Extend detection result structure to include:

- qc_edge_violation: np.ndarray[bool]
- qc_diameter_violation: np.ndarray[bool]
- qc_center_violation: np.ndarray[bool]

These should align with frame index.

---

# Part 2 — Detection Params UI Updates

Modify Detection Params card:

Add:

- Checkbox: Enable Motion Constraints
- Numeric inputs for:
    - Max Edge Shift (µm)
    - Max Diameter Change (µm)
    - Max Center Shift (µm)

When checkbox is disabled:
- Disable the numeric inputs visually
- Constraints not applied in backend

---

# Part 3 — Factory Reset Button

In Detection Params card:

Add button:

    "Reset to Defaults"

Behavior:

- Recreate a fresh instance of `DiameterDetectionParams()`
- Replace `state.detection_params`
- Re-render UI card
- Emit state update

This must use dataclass defaults only (single source of truth).

---

# Part 4 — Serialization Planning (Scaffold Only)

Do NOT fully implement yet.

Add TODO comments for:

- DetectionParams.to_dict()
- DetectionParams.from_dict()
- DetectionResults.to_dict()
- DetectionResults.from_dict()

Future tickets will:

- Save/load detection parameters
- Save/load detection results
- Persist QC flags

---

# Acceptance Criteria

1. Gradient detection works with constraints ON.
2. Constraint violations produce NaNs and QC flags.
3. Constraints OFF restores old behavior exactly.
4. Reset button restores factory defaults.
5. UI does not break existing layout (including Post Filter Params card).
6. No changes to file picker behavior.

---

# Out of Scope

- Subpixel refinement (future ticket)
- Temporal search window (future ticket)
- Gap interpolation logic (future ticket)
- Serialization implementation (future ticket)
