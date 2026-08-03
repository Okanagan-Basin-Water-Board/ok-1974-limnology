#!/usr/bin/env python3
"""Emit the canonical long-format table from the raw transcriptions.

Both unit conventions are carried explicitly:
  value_as_printed  -- exactly what the page says, in the page's own units
  value_as_P        -- phosphorus converted from PO4 to P (/3.066); NULL otherwise

The conversion exists because Ch.3 of the source states "Total P (reported as
PO4)" and the Appendix C-1 column headers are literally o-PO4 / t-PO4, while
Table 9.2 -- the table that became policy -- is in ug P/L. Anything that reads
value_as_printed for phosphorus and calls it TP will be 3.066x too high.
"""
import csv, os, sys

PO4_TO_P = 3.066
SRC = os.path.join(os.path.dirname(__file__), "..", "data", "raw_transcription")
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "derived")
C1_PARAMS = {"NO3": "mg/L", "TKN": "mg/L", "o-PO4": "mg/L as PO4",
             "t-PO4": "mg/L as PO4", "SiO2": "mg/L"}
C3_PARAMS = {"HCO3": "mg/L", "SO4": "mg/L", "Cl": "mg/L", "F": "mg/L"}
# Cruise dates recovered from the Appendix C-3 season headers, which print them.
DATES = {("Wood Lake", "APRIL"): "1971-04-13", ("Wood Lake", "JUNE"): "1971-06-16",
         ("Wood Lake", "AUGUST"): "1971-08-16", ("Wood Lake", "OCTOBER"): "1971-10-14",
         ("Kalamalka Lake", "APRIL"): "1971-04-18", ("Kalamalka Lake", "JUNE"): "1971-06-19",
         ("Kalamalka Lake", "AUGUST"): "1971-08-19", ("Kalamalka Lake", "OCTOBER"): "1971-10-19"}


def emit(rows, params, appendix, w, datecol=None):
    n = 0
    for r in rows:
        for p, unit in params.items():
            raw = (r[p] or "").strip()
            if raw == "":
                continue
            bd = raw.startswith("<")
            nd = raw.upper() == "ND"
            try:
                v = None if nd else float(raw.lstrip("<"))
            except ValueError:
                v = None
            as_p = round(v / PO4_TO_P, 5) if (v is not None and "PO4" in p) else ""
            date = r.get(datecol) if datecol else DATES.get((r["lake"], r["season"]), "")
            w.writerow({
                "source": "CA-BC Okanagan Basin Agreement 1974, Tech. Supplement V",
                "appendix": appendix,
                "lake": r["lake"], "station": r["station"],
                "season": r["season"], "sample_date_1971": date or "",
                "depth_m": r["depth_m"], "characteristic": p,
                "value_as_printed": "" if v is None else v,
                "unit_as_printed": unit,
                "value_as_P": as_p,
                "below_detection": "TRUE" if bd else "FALSE",
                "not_determined": "TRUE" if nd else "FALSE",
                "raw_text": raw,
            })
            n += 1
    return n


def main():
    os.makedirs(OUT, exist_ok=True)
    cols = ["source", "appendix", "lake", "station", "season", "sample_date_1971",
            "depth_m", "characteristic", "value_as_printed", "unit_as_printed",
            "value_as_P", "below_detection", "not_determined", "raw_text"]
    with open(os.path.join(OUT, "ok1974_appendix_c_long.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        n1 = emit(list(csv.DictReader(open(os.path.join(SRC, "appendix_c1_all.csv")))),
                  C1_PARAMS, "C-1", w)
        n3 = emit(list(csv.DictReader(open(os.path.join(SRC, "appendix_c3_all.csv")))),
                  C3_PARAMS, "C-3", w, datecol="sample_date_1971")
    print(f"C-1 observations: {n1}")
    print(f"C-3 observations: {n3}")
    print(f"total: {n1 + n3}  ->  data/derived/ok1974_appendix_c_long.csv")


if __name__ == "__main__":
    main()
