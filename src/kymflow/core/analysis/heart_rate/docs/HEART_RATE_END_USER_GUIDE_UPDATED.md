
# Heart Rate Analysis Pipeline – End User Guide

---

# Physiological Assumptions and Frequency Band Design (Mouse)

## Why a Frequency Band Is Used

Heart rate estimation is constrained to a biologically plausible frequency band.  
This improves robustness by:

- Rejecting low-frequency motion drift
- Ignoring high-frequency measurement noise
- Reducing false peak detection
- Improving interpretability of SNR metrics

The default band used in this pipeline reflects typical **adult mouse physiology** under imaging conditions.

---

# Typical Mouse Heart Rate Ranges (Literature-Based)

Mouse heart rate varies strongly with physiological state.

### Awake, freely moving adult mouse
- ~450–750 bpm
- Can transiently exceed 800 bpm under stress

### Awake, restrained or head-fixed
- ~400–650 bpm (variable depending on stress level)

### Isoflurane anesthesia (light to moderate)
- ~300–500 bpm
- Deeper anesthesia → lower heart rate

### Deep anesthesia
- Can drop below 300 bpm
- Pulsatility amplitude often reduced

These ranges depend on:
- Strain
- Age
- Temperature
- Anesthetic depth
- Stress state

---

## How These Values Informed the Algorithm

The default heart rate band in this analysis typically spans approximately:

**240–600 bpm (≈ 4–10 Hz)**

This band was chosen to:

- Capture low anesthetized rates (~4 Hz ≈ 240 bpm)
- Capture most awake physiological rates (~10 Hz ≈ 600 bpm)
- Avoid contamination from:
  - Respiratory oscillations (~1–3 Hz)
  - Slow motion drift (<2 Hz)
  - High-frequency measurement noise

Restricting spectral analysis to this band:

- Increases peak detection stability
- Improves signal-to-noise ratio interpretation
- Reduces spurious detections

---

## Isoflurane-Specific Considerations

Isoflurane anesthesia:

- Reduces heart rate relative to awake state
- Reduces pulsatility amplitude
- May increase respiratory contamination (~1–3 Hz)

Practical implications:

- Lower SNR values are common under deeper anesthesia
- Agreement between Welch and Lomb becomes especially important
- Low `valid_frac` combined with low SNR may reflect physiological suppression, not purely algorithmic failure

---

# Why Two Algorithms Help Under Variable Physiology

Because heart rate can shift substantially with anesthesia depth, using two independent methods provides:

- Cross-validation when physiology changes
- Greater confidence when signal amplitude is reduced
- A safeguard against band-edge artifacts

If both methods agree within tolerance → high confidence.  
If they diverge → inspect trace and consider band adjustment.

---

# When You Should Adjust the Frequency Band

Consider modifying the bpm band if:

- Studying neonatal mice (lower HR)
- Working under deep anesthesia
- Observing persistent band-edge peaks
- Studying another species

Indicators the band may be inappropriate:

- `*_edge = True`
- Strong spectral energy just outside band
- Known physiology outside default range

---

# Key Output Fields – Interpretation Guide

## Welch Outputs
- **welch_hz**: Peak frequency (Hz)
- **welch_bpm**: Heart rate in beats per minute
- **welch_snr**: Signal-to-noise ratio around peak
- **welch_edge**: Peak lies at band boundary
- **welch_bc**: Band concentration metric (power near peak)

## Lomb–Scargle Outputs
- **lomb_hz**: Peak frequency (Hz)
- **lomb_bpm**: Heart rate in beats per minute
- **lomb_snr**: Signal-to-noise ratio
- **lomb_edge**: Peak at band boundary
- **lomb_bc**: Band concentration metric

## Cross-Method Metrics
- **agree_delta_bpm**: Absolute bpm difference between methods
- **agree_ok**: True if difference within tolerance
- **status**: High-level classification of result
- **status_note**: Human-readable explanation
- **valid_frac**: Fraction of usable data points

---

# Selected References on Mouse Heart Rate

1. Mitchell GF et al. *Hypertension* (1998).  
2. Janssen BJA et al. *Am J Physiol Heart Circ Physiol* (2004).  
3. Roth DM et al. *Am J Physiol* (2002).  
4. Hoit BD. *Physiol Genomics* (2001).  

These and related studies support typical HR ranges of ~300–750 bpm depending on physiological state.

---

# Summary

This heart rate pipeline was designed around realistic adult mouse physiology under imaging conditions.  
Frequency band selection and dual-method estimation reflect these biological assumptions.

The system aims not only to produce a heart rate estimate, but to provide sufficient quality metrics for researchers to judge reliability in context.
