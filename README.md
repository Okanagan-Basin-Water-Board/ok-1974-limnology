# Okanagan main valley lakes — 1971 chemical limnology (digitised)

A machine-readable transcription of **Appendix C** of:

> Canada–British Columbia Okanagan Basin Agreement (1974). *Technical Supplement V:
> The Limnology of the Major Okanagan Basin Lakes.* Office of the Study Director,
> Penticton, B.C., April 1974. Compiled by M.E. Pinsent (BC Fish & Wildlife) and
> J.G. Stockner (Pacific Environment Institute).

Source PDFs are published by the Okanagan Basin Water Board at
`obwb.ca/library/1974-okanagan-basin-study/`. The tables in every OBWB copy are
scanned images — no copy carries an OCR text layer for tabular content — so this
transcription was produced from the page images and validated against the
report's own published summary statistics.

**This is a derived transcription of a Crown publication. It is not our data.**
Attribution above; errors in transcription are ours.

## Why this exists

The provincial EMS record for these lakes begins in the 1970s. This appendix
sits *below* it: a four-cruise, depth-resolved survey of all main valley lakes in
1971, and the only pre-EMS chemistry at this resolution.

## ⚠️ Phosphorus is reported as PO₄, not P

Chapter 3 of the source states samples were analysed for "Total P (**reported as
PO4**)", and the C-1 column headers are literally `o-PO4` and `t-PO4`. Table 9.2
of the same report — the table that set the basin's loading criteria — is in
**µg P/L**. The two differ by the PO₄/P mass ratio, **3.066**.

Anything that reads `value_as_printed` for phosphorus and calls it TP will be
3.07× too high. Use `value_as_P`.

## Layout

```
data/raw_transcription/   as printed, one file per lake (C-1) + anions (C-3)
data/derived/             ok1974_appendix_c_long.csv  (canonical long format)
src/validate_c1.py        nutrient validation + Table 9.2 / 6.3 reconciliation
src/validate_c3.py        anion validation + Table 6.4 reconciliation
src/c1_extract.py         rendering, rule-line removal, fuzzy trust scoring
```

`value_as_printed` is exactly what the page says. `value_as_P` is populated only
for phosphorus. `raw_text` preserves the literal cell, including malformed ones.

## Validation

Nothing is auto-corrected. Suspect cells carry a flag and, where a misplaced
decimal would reconcile them with their profile neighbours, a *proposal*.

Checks, in order of authority: structural (depth monotonic within a profile) →
constraint (ortho ≤ total; depth ≤ the lake's sounded maximum from Table 5.1) →
envelope (per-parameter plausible range) → smoothness (log-ratio against the
geometric mean of the nearest shallower and deeper values — deliberately *not*
the profile median, because in a stratified eutrophic lake o-PO₄ spans two orders
of magnitude between epilimnion and hypolimnion and that is real signal).

The acceptance gate is reconciliation against the report's own tables:

| Appendix | Gate | Result |
|---|---|---|
| C-1 nutrients (2,225 cells) | Table 6.3 col. B — the same Calgary lab that ran these samples | Wood, Skaha, Osoyoos, Okanagan within **1–4%** |
| C-3 anions (1,768 cells) | Table 6.4 per-month means **and sample counts** | HCO₃ **0.0–0.2%** in 15 of 16 lake-months; sample counts match **exactly** for Skaha and Osoyoos (all 8 lake-months) |

Whole-lake averages against Table 6.4's "Lake Average" rows:

| Lake | n | HCO₃ | SO₄ | Cl | F |
|---|---:|---|---|---|---|
| Okanagan | 186 | 0.1% | 0.6% | 0.1% | 1.9% |
| Osoyoos | 76 | 0.5% | 0.3% | 0.6% | 2.0% |
| Skaha | 78 | 0.1% | 1.0% | 3.8% | 0.6% |
| Wood | 58 | 0.6% | 0.5% | 1.3% | 0.2% |
| Kalamalka | 44 | 0.1% | 0.1% | 4.0% | 0.5% |

**Reconciliation can exonerate a flagged cell, and did.** Osoyoos June chloride
carries three surface spikes (7.3, 3.9, 3.6 mg/L against a ~1.3 background) that
the smoothness check flagged. Including them, the recomputed mean is **1.836 over
n=22** against Table 6.4's published **1.8 over n=22** — the published mean only
reproduces *with* the spikes, so they are real measurements, not transcription
errors. Chapter 6 attributes June surface loading to runoff. Flags are a queue
for adjudication, not a verdict.

## Known source defects (transcribed verbatim, flagged, not corrected)

| Location | As printed | Note |
|---|---|---|
| Wood st4 Apr 15 m `t-PO4` | `3.8` | out of envelope; Table 9.2's published upper bound of 125 µg P/L is reproduced if this is 0.38 |
| Wood st4 Jun 5 m `t-PO4` | `0.00` | ortho (0.01) exceeds total |
| Skaha st4 Jun 15 m `o-PO4` | `3.03` | out of envelope; likely 0.03 |
| Kalamalka st4 Oct 50 m `TKN` | `9.11` | out of envelope; likely 0.11 |
| Okanagan st1 Apr 10 m `t-PO4` | `0-05` | hyphen for decimal point |
| Kalamalka st4 Aug 50 m `SiO2` | `.0.4` | malformed |
| Kalamalka st4 Apr 78 m `Cl` | `.13` | malformed; likely 1.3 |
| Wood st2 Aug | depths 1,5,10,15,25,**20** | depth sequence not monotonic |
| Okanagan st11 Jun 1 m; st4 Jun 50 m and 124 m | — | ortho exceeds total |

**A genuine inconsistency in the source:** Osoyoos April total phosphorus
transcribes to 20.3 µg P/L, matching Table 6.3 column B (20.2) — but Table 9.2
reports 12 (range 10–15) for the same lake and quantity. Our figure agrees with
the report's chemistry table and disagrees with its policy table. Cite with care.

## Sampling design (Ch. 3)

3 L Van Dorn; standard depths 1, 5, 10, 25, 50, 100 m plus 2 m off bottom; under
stratification 2 epilimnetic / 2–3 metalimnetic / 3 hypolimnetic. Samples iced to
the Water Quality Division laboratory, Calgary, analysed within 24 h. APHA
Standard Methods (1965). Cruise dates are printed in the C-3 season headers and
are carried in `sample_date_1971`.
