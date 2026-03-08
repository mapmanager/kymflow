
# Ticket 039 — Add sum_intensity + physical-unit columns to saved diameter CSV (and load)

## Goal
Extend the analysis outputs so the saved `.diameter.csv` includes:

1. `sum_intensity_*` per time row (sum of the binned line profile intensity)
2. physical-unit equivalents for edge/diameter (`*_um_*`) derived from metadata.

These additions must be **independent of the diameter detection algorithms**. They simply record additional measurements during analysis and persist them.

---

# Requirements

## A. Sum intensity

Compute `sum_intensity` for each analyzed line profile.

Definition of the profile to sum (authoritative):

• after binning/windowing  
• before any derivative, gradient, or edge-detection operations  

This corresponds to the **final binned/windowed line profile used as input to the diameter detection stage.**

Computation:

sum_intensity = float(np.sum(profile))

Persistence policy:

• `sum_intensity` must be saved **only in the CSV**  
• **Do NOT store it in JSON**

Rationale:

• avoids duplication between CSV and JSON  
• keeps JSON as metadata + run manifest  
• keeps CSV as the authoritative per-time-series data

Column naming:

sum_intensity_roi{roi}_ch{ch}

Example:

sum_intensity_roi1_ch1

---

# B. Physical-unit columns (µm)

Add physical-unit equivalents for each run `(roi_id, channel_id)`:

left_edge_um_roi{roi}_ch{ch}  
right_edge_um_roi{roi}_ch{ch}  
diameter_um_roi{roi}_ch{ch}

Computed as:

left_edge_um  = left_edge_px  * um_per_pixel  
right_edge_um = right_edge_px * um_per_pixel  
diameter_um   = diameter_px   * um_per_pixel  

Source of truth for units:

KymImage.header.voxels

Structure:

(seconds_per_line, um_per_pixel)

Mapping to image axes:

seconds_per_line → time axis  
um_per_pixel → spatial axis  

Use **um_per_pixel** for px → µm conversion.

---

# C. Serialization contract

Update the CSV column registry/spec so the following new base fields exist:

sum_intensity  
left_edge_um  
right_edge_um  
diameter_um

Wide format expansion:

sum_intensity_roiX_chY  
left_edge_um_roiX_chY  
right_edge_um_roiX_chY  
diameter_um_roiX_chY  

JSON schema remains unchanged and continues to store:

• schema_version  
• run metadata  
• detection params  
• run identifiers  

JSON **must not duplicate per-timepoint signals**.

---

# D. Tests

Extend round‑trip tests to verify:

1. CSV contains `sum_intensity_roiX_chY`
2. CSV contains `_um` columns
3. `_um` values equal `_px * um_per_pixel`
4. `sum_intensity` equals the sum of the final binned/windowed line profile
5. Loading JSON + CSV reproduces the same values

Existing diameter outputs must remain unchanged.

---

# Acceptance criteria

After analysis + save, CSV includes:

sum_intensity_roi{roi}_ch{ch}  
left_edge_um_roi{roi}_ch{ch}  
right_edge_um_roi{roi}_ch{ch}  
diameter_um_roi{roi}_ch{ch}

And:

• `sum_intensity` equals `sum(profile)`  
• `_um` columns equal `_px * um_per_pixel`  
• JSON does **not** store per‑timepoint arrays

---

# Files likely involved

sandbox/diameter-analysis/diameter_analysis.py  
sandbox/diameter-analysis/tests/test_multi_run_serialization.py

---

# Out of scope

• GUI visualization changes  
• Any change to the diameter detection algorithms
