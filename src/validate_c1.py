#!/usr/bin/env python3
"""Validate a transcribed Appendix C-1 table and reconcile against Table 9.2.

Checks, in order of authority:
  1. structural  -- depth monotonic within a station-season profile
  2. constraint  -- o-PO4 <= t-PO4; depth <= lake sounded maximum (Table 5.1)
  3. envelope    -- per-parameter plausible range, printed PO4 units
  4. smoothness  -- log-ratio against the median of the same profile
  5. reconcile   -- spring-overturn TP mean and range vs Table 9.2

Nothing is auto-corrected. Where a value fails smoothness, the decimal shift
that would reconcile it is proposed for human adjudication.
"""
import csv, math, sys, statistics as stats

PO4_TO_P = 3.066
PARAMS = ["NO3", "TKN", "o-PO4", "t-PO4", "SiO2"]
ENVELOPE = {"NO3": (0, 1.0), "TKN": (0, 4.5), "o-PO4": (0, 1.0),
            "t-PO4": (0, 1.2), "SiO2": (0.2, 12.0)}
MAXDEPTH = {"Wood Lake": 34, "Skaha Lake": 57, "Okanagan Lake": 242,
            "Kalamalka Lake": 142, "Osoyoos Lake": 63, "Vaseux Lake": 27}
# Table 9.2: average TP at spring overturn 1971, ug P/L (average, lo, hi)
TABLE_9_2 = {"Wood Lake": (104, 83, 125), "Kalamalka Lake": (8, 4, 12),
             "Okanagan Lake": (7, 2, 12), "Skaha Lake": (24, 15, 32),
             "Osoyoos Lake": (12, 10, 15)}


def parse(tok):
    tok = (tok or "").strip()
    if tok.upper() == "ND":
        return None, False, "ND"      # not determined -> missing, never zero
    bd = tok.startswith("<")
    try:
        return float(tok.lstrip("<")), bd, ""
    except ValueError:
        return None, bd, "unparsed"


def main(path):
    rows = list(csv.DictReader(open(path)))
    recs = []
    for r in rows:
        rec = dict(lake=r["lake"], station=r["station"], season=r["season"],
                   depth=float(r["depth_m"]), vals={})
        for p in PARAMS:
            v, bd, note = parse(r[p])
            rec["vals"][p] = dict(raw=r[p], value=v, bd=bd, note=note, flags=[])
        recs.append(rec)

    def profile(rec):
        return [q for q in recs if q["lake"] == rec["lake"]
                and q["station"] == rec["station"] and q["season"] == rec["season"]]

    # 1 structural
    seen = set()
    for rec in recs:
        key = (rec["lake"], rec["station"], rec["season"])
        if key in seen:
            continue
        seen.add(key)
        ds = [q["depth"] for q in profile(rec)]
        if ds != sorted(ds):
            print(f"  STRUCT depth not monotonic: {key} {ds}")

    issues = 0
    for rec in recs:
        prof = profile(rec)
        o = rec["vals"]["o-PO4"]["value"]
        t = rec["vals"]["t-PO4"]["value"]
        if o is not None and t is not None and o > t:
            rec["vals"]["t-PO4"]["flags"].append("ortho>total")
        if rec["depth"] > MAXDEPTH.get(rec["lake"], 1e9):
            rec["vals"]["NO3"]["flags"].append("depth>lake_max")
        for p in PARAMS:
            c = rec["vals"][p]
            v = c["value"]
            if v is None:
                continue
            lo, hi = ENVELOPE[p]
            if not (lo <= v <= hi):
                c["flags"].append(f"envelope({lo}-{hi})")
            # Gradient-aware: compare against the geometric mean of the nearest
            # shallower and deeper values, NOT the profile median. In a
            # stratified eutrophic lake o-PO4 legitimately spans two orders of
            # magnitude from epilimnion to hypolimnion; a median-based check
            # flags that real internal-loading signal as error.
            above = [q for q in prof if q["depth"] < rec["depth"]
                     and q["vals"][p]["value"]]
            below = [q for q in prof if q["depth"] > rec["depth"]
                     and q["vals"][p]["value"]]
            nb = []
            if above:
                nb.append(max(above, key=lambda q: q["depth"])["vals"][p]["value"])
            if below:
                nb.append(min(below, key=lambda q: q["depth"])["vals"][p]["value"])
            sib = nb
            if sib and v > 0:
                med = math.exp(sum(math.log(x) for x in sib) / len(sib))
                ratio = abs(math.log10(v / med)) if med > 0 else 0
                if ratio > 0.8:
                    c["flags"].append(f"smooth({ratio:.2f})")
                    best = min(((v * 10 ** k, abs(math.log10(v * 10 ** k / med)))
                                for k in (-2, -1, 1, 2)), key=lambda z: z[1])
                    if best[1] < 0.35:
                        c["flags"].append(f"propose={best[0]:.3g}")
        for p in PARAMS:
            if rec["vals"][p]["flags"]:
                issues += 1
                print(f"  FLAG {rec['lake']} st{rec['station']} {rec['season']:8s} "
                      f"{rec['depth']:>5.0f}m {p:6s} raw={rec['vals'][p]['raw']:>7s} "
                      f"{rec['vals'][p]['flags']}")

    print(f"\ncells: {len(recs)*len(PARAMS)}   flagged: {issues}")

    # 5 reconcile spring overturn TP vs Table 9.2
    print("\nReconciliation -- April (spring overturn) t-PO4 -> ug P/L vs Table 9.2")
    for lake in sorted({r["lake"] for r in recs}):
        vs = [r["vals"]["t-PO4"]["value"] for r in recs
              if r["lake"] == lake and r["season"] == "APRIL"
              and r["vals"]["t-PO4"]["value"] is not None
              and not r["vals"]["t-PO4"]["flags"]]
        if not vs:
            continue
        ugP = [v * 1000 / PO4_TO_P for v in vs]
        pub = TABLE_9_2.get(lake)
        print(f"  {lake}: n={len(ugP)} mean={stats.mean(ugP):.1f} "
              f"range={min(ugP):.1f}-{max(ugP):.1f} ug P/L"
              + (f"   | Table 9.2: {pub[0]} ({pub[1]}-{pub[2]})" if pub else ""))
        # what the proposed repair would do
        rep = [r for r in recs if r["lake"] == lake and r["season"] == "APRIL"
               and any("propose" in f for f in r["vals"]["t-PO4"]["flags"])]
        for r in rep:
            prop = [f for f in r["vals"]["t-PO4"]["flags"] if "propose" in f][0]
            val = float(prop.split("=")[1]) * 1000 / PO4_TO_P
            print(f"      if {r['vals']['t-PO4']['raw']} -> {prop.split('=')[1]} "
                  f"({val:.1f} ug P/L), range becomes "
                  f"{min(min(ugP), val):.1f}-{max(max(ugP), val):.1f}")


if __name__ == "__main__":
    main(sys.argv[1])
