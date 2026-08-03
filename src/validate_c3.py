#!/usr/bin/env python3
"""Validate Appendix C-3 (major anions) and reconcile against Table 6.4.

Table 6.4 publishes, for every lake, a per-month mean of each ion AND the
number of samples behind it. That makes it a stronger acceptance gate than the
one available for C-1: a transcription is only accepted when the recomputed
per-month means reproduce the published ones.

Units are mg/L (the source says "parts per million") for all four anions --
no conversion, unlike the PO4/P trap in C-1.
"""
import csv, math, sys, statistics as stats

IONS = ["HCO3", "SO4", "Cl", "F"]
ENVELOPE = {"HCO3": (100, 260), "SO4": (20, 70), "Cl": (0.5, 5.0), "F": (0.1, 0.6)}
MAXDEPTH = {"Wood Lake": 34, "Skaha Lake": 57, "Okanagan Lake": 242,
            "Kalamalka Lake": 142, "Osoyoos Lake": 63, "Vaseux Lake": 27}

# Table 6.4: average seasonal concentration, mg/L. (n, HCO3, SO4, Cl, F)
TABLE_6_4 = {
    ("Kalamalka Lake", "APRIL"):   (11, 179.9, 56.0, 1.4, 0.29),
    ("Kalamalka Lake", "JUNE"):    (12, 180.25, 55.7, 1.1, 0.27),
    ("Kalamalka Lake", "AUGUST"):  (12, 174.7, 55.3, 1.3, 0.33),
    ("Kalamalka Lake", "OCTOBER"): (11, 174.5, 55.6, 1.3, 0.31),
    ("Wood Lake", "APRIL"):        (13, 189.2, 30.2, 2.6, 0.33),
    ("Wood Lake", "JUNE"):         (16, 181.2, 31.2, 2.3, 0.30),
    ("Wood Lake", "AUGUST"):       (16, 162.5, 30.2, 2.6, 0.33),
    ("Wood Lake", "OCTOBER"):      (14, 176.8, 29.9, 2.6, 0.32),
    ("Skaha Lake", "APRIL"):       (18, 134.3, 28.4, 1.4, 0.18),
    ("Skaha Lake", "JUNE"):        (24, 131.6, 26.5, 1.2, 0.17),
    ("Skaha Lake", "AUGUST"):      (18, 126.1, 27.6, 1.3, 0.20),
    ("Skaha Lake", "OCTOBER"):     (18, 127.6, 27.7, 1.5, 0.19),
    ("Osoyoos Lake", "APRIL"):     (17, 149.0, 32.1, 1.5, 0.21),
    ("Osoyoos Lake", "JUNE"):      (22, 132.7, 26.5, 1.8, 0.19),
    ("Osoyoos Lake", "AUGUST"):    (20, 132.2, 27.3, 1.5, 0.20),
    ("Osoyoos Lake", "OCTOBER"):   (17, 138.5, 28.3, 1.5, 0.23),
}
# Okanagan Lake is split North/Central/South in Table 6.4 and only North/South on
# the C-3 pages, so the basins do not map 1:1 -- reconcile it on the lake average.
# Lake averages, Table 6.4
LAKE_AVG = {"Kalamalka Lake": (177.3, 55.7, 1.3, 0.30),
            "Wood Lake": (177.4, 30.4, 2.5, 0.32),
            "Skaha Lake": (129.9, 27.6, 1.4, 0.18),
            "Osoyoos Lake": (138.1, 28.5, 1.6, 0.21),
            "Okanagan Lake": (131.8, 27.2, 1.1, 0.17)}


def parse(t):
    t = (t or "").strip()
    if t.upper() == "ND":
        return None, "ND"
    try:
        return float(t.lstrip("<")), ""
    except ValueError:
        return None, "unparsed"


def main(path):
    rows = list(csv.DictReader(open(path)))
    recs = []
    for r in rows:
        rec = dict(lake=r["lake"], station=r["station"], season=r["season"],
                   date=r["sample_date_1971"], depth=float(r["depth_m"]), vals={})
        for i in IONS:
            v, note = parse(r[i])
            rec["vals"][i] = dict(raw=r[i], value=v, note=note, flags=[])
        recs.append(rec)

    def prof(rec):
        return [q for q in recs if q["lake"] == rec["lake"]
                and q["station"] == rec["station"] and q["season"] == rec["season"]]

    seen, issues = set(), 0
    for rec in recs:
        key = (rec["lake"], rec["station"], rec["season"])
        if key not in seen:
            seen.add(key)
            ds = [q["depth"] for q in prof(rec)]
            if ds != sorted(ds):
                print(f"  STRUCT depth not monotonic {key}: {ds}")
        if rec["depth"] > MAXDEPTH.get(rec["lake"], 1e9):
            rec["vals"]["HCO3"]["flags"].append("depth>lake_max")
        for i in IONS:
            c = rec["vals"][i]
            if c["note"]:
                c["flags"].append(c["note"])
                continue
            lo, hi = ENVELOPE[i]
            if not (lo <= c["value"] <= hi):
                c["flags"].append(f"envelope({lo}-{hi})")
            above = [q for q in prof(rec) if q["depth"] < rec["depth"] and q["vals"][i]["value"]]
            below = [q for q in prof(rec) if q["depth"] > rec["depth"] and q["vals"][i]["value"]]
            nb = []
            if above:
                nb.append(max(above, key=lambda q: q["depth"])["vals"][i]["value"])
            if below:
                nb.append(min(below, key=lambda q: q["depth"])["vals"][i]["value"])
            if nb and c["value"] and c["value"] > 0:
                g = math.exp(sum(math.log(x) for x in nb) / len(nb))
                if abs(math.log10(c["value"] / g)) > 0.3:     # anions are stable
                    c["flags"].append(f"smooth({abs(math.log10(c['value']/g)):.2f})")
        for i in IONS:
            if rec["vals"][i]["flags"]:
                issues += 1
                print(f"  FLAG {rec['lake']:15s} st{rec['station']} {rec['season']:8s} "
                      f"{rec['depth']:>5.0f}m {i:5s} raw={rec['vals'][i]['raw']:>7s} "
                      f"{rec['vals'][i]['flags']}")
    print(f"\ncells: {len(recs)*len(IONS)}   flagged: {issues}")

    print("\nReconciliation -- per-month means vs Table 6.4 (n, HCO3, SO4, Cl, F)")
    for (lake, season), pub in sorted(TABLE_6_4.items()):
        sub = [r for r in recs if r["lake"] == lake and r["season"] == season]
        if not sub:
            continue
        line, ok = [], True
        for j, i in enumerate(IONS):
            vs = [r["vals"][i]["value"] for r in sub
                  if r["vals"][i]["value"] is not None and not r["vals"][i]["flags"]]
            if not vs:
                line.append(f"{i}: --"); continue
            m, p = stats.mean(vs), pub[j + 1]
            d = abs(m - p) / p * 100
            ok &= d < 3.0
            line.append(f"{i}: {m:.2f} vs {p} ({d:.1f}%)")
        print(f"  {lake:15s} {season:8s} n={len(sub):2d}/{pub[0]:2d}  "
              + "  ".join(line) + ("   OK" if ok else "   CHECK"))


if __name__ == "__main__":
    main(sys.argv[1])


def lake_average_check(path):
    """Whole-lake averages vs Table 6.4 'Lake Average' rows."""
    import csv as _csv
    rows = list(_csv.DictReader(open(path)))
    print("\nLake averages vs Table 6.4 (all seasons pooled)")
    for lake, pub in sorted(LAKE_AVG.items()):
        sub = [r for r in rows if r["lake"] == lake]
        if not sub:
            continue
        out = []
        for j, i in enumerate(IONS):
            vs = []
            for r in sub:
                v, note = parse(r[i])
                if v is not None:
                    vs.append(v)
            if not vs:
                out.append(f"{i}: --"); continue
            m = stats.mean(vs)
            out.append(f"{i}: {m:.2f} vs {pub[j]} ({abs(m-pub[j])/pub[j]*100:.1f}%)")
        print(f"  {lake:15s} n={len(sub):3d}  " + "  ".join(out))
