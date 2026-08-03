#!/usr/bin/env python3
"""
Appendix C-1 extractor + fuzzy trust scoring.

Canada-BC Okanagan Basin Agreement (1974), Technical Supplement V,
Appendix C-1: "Data listing of nutrient analyses for the Okanagan main valley
lakes, 1971" (parts per million).

Pipeline
--------
1. Render page at several DPIs (independent OCR realisations).
2. Erase printed rule lines -- otherwise tesseract reads them as characters and
   fuses adjacent cells into one token.
3. One full-width OCR pass per realisation (cropping to a narrow season block
   makes tesseract's layout analysis return nothing).
4. Bucket tokens into the four season blocks by x-centre, then cluster rows
   *within* a block. Rows do NOT align across blocks -- April may have 4 depths
   where June has 6 at the same station -- so cross-block row clustering would
   silently interleave different depths.
5. Score every cell with a fuzzy trust value and band it accept/review/reject.

Nothing is auto-corrected. Digit-shift repairs are *proposed* for a human.
"""
import subprocess, csv, re, math, statistics as stats
import numpy as np
from PIL import Image

PARAMS = ["NO3", "TKN", "o-PO4", "t-PO4", "SiO2"]
COLS = ["depth"] + PARAMS
PO4_TO_P = 3.066            # PO4 molar mass / P molar mass

# plausible physical envelopes, ppm (as printed, i.e. P reported as PO4)
ENVELOPE = {"NO3": (0, 1.0), "TKN": (0, 4.5), "o-PO4": (0, 1.0),
            "t-PO4": (0, 1.2), "SiO2": (0.2, 12.0)}
# max sounded depth per lake, Table 5.1
MAXDEPTH = {"WOOD": 34, "SKAHA": 57, "OKANAGAN": 242, "KALAMALKA": 142,
            "OSOYOOS": 63, "VASEUX": 27}


# ---------------------------------------------------------------- rendering
def render(pdf, page, dpi, out):
    subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(page), "-l", str(page),
                    "-png", "-singlefile", pdf, out], check=True)
    return np.array(Image.open(out + ".png").convert("L"))


def declean(a, minrun=None):
    """Erase printed rule lines (long contiguous dark runs)."""
    if minrun is None:
        minrun = max(20, a.shape[0] // 44)
    dark = a < 128
    clean = a.copy()
    H, W = a.shape
    for x in range(W):
        ys = np.where(dark[:, x])[0]
        if len(ys):
            for s in np.split(ys, np.where(np.diff(ys) != 1)[0] + 1):
                if len(s) >= minrun:
                    clean[s[0]:s[-1] + 1, max(0, x - 1):x + 2] = 255
    for y in range(H):
        xs = np.where(dark[y, :])[0]
        if len(xs):
            for s in np.split(xs, np.where(np.diff(xs) != 1)[0] + 1):
                if len(s) >= minrun:
                    clean[max(0, y - 1):y + 2, s[0]:s[-1] + 1] = 255
    return clean


def ocr(arr, tmp="/private/tmp/claude-501/-Users-nelson/80988503-8b78-49be-9225-2fe359c38c21/scratchpad/ok1974/_ocr_tmp.png"):
    Image.fromarray(arr).save(tmp)
    p = subprocess.run(["tesseract", tmp, "stdout", "--psm", "6", "tsv",
                        "-c", "tessedit_char_whitelist=0123456789.,<ND"],
                       capture_output=True)
    words = []
    for r in csv.DictReader(p.stdout.decode("utf-8", "replace").splitlines(),
                            delimiter="\t"):
        t = (r.get("text") or "").strip()
        if not t:
            continue
        words.append(dict(x=int(r["left"]), y=int(r["top"]), w=int(r["width"]),
                          h=int(r["height"]), conf=float(r.get("conf", -1)),
                          text=t))
    return words


# ------------------------------------------------------------- tokenisation
SPLIT = re.compile(r"(?<=.)(?=<)")


def normalise(tok):
    """comma->period, then split fused cells like '0.38<0.005' or '1.05<0.01'."""
    t = tok.replace(",", ".").replace("/", " ").replace(";", " ").replace("|", " ")
    out = []
    for piece in t.split():
        out.extend([p for p in SPLIT.split(piece) if p])
    return out


NUM = re.compile(r"^<?\d+(\.\d+)?$")


def parse(tok):
    """-> (value, below_detection, note)"""
    if tok.upper() in ("ND", "N0", "NO"):
        return None, False, "ND"          # not determined -> missing, not zero
    bd = tok.startswith("<")
    body = tok.lstrip("<")
    if not NUM.match(tok):
        return None, bd, "unparsed"
    return float(body), bd, ""


# ------------------------------------------------------------ fuzzy scoring
def tri(x, lo, hi):
    """falling membership: 1 below lo, 0 above hi, linear between."""
    if x <= lo:
        return 1.0
    if x >= hi:
        return 0.0
    return (hi - x) / (hi - lo)


def smoothness(v, neighbours):
    """How consistent is v with its vertical neighbours in the same profile?
    Uses log-ratio, so a misplaced decimal (0.38 -> 3.8) scores near zero."""
    ns = [n for n in neighbours if n and n > 0]
    if not ns or not v or v <= 0:
        return 1.0                       # no evidence either way
    med = stats.median(ns)
    if med <= 0:
        return 1.0
    return tri(abs(math.log10(v / med)), 0.5, 1.3)


def envelope_score(param, v):
    if v is None:
        return 1.0
    lo, hi = ENVELOPE[param]
    if lo <= v <= hi:
        return 1.0
    over = v / hi if v > hi else lo / max(v, 1e-9)
    return tri(math.log10(max(over, 1.0)), 0.0, 1.0)


def consensus_score(variants):
    """variants: list of raw strings from independent renderings."""
    variants = [v for v in variants if v is not None]
    if not variants:
        return 0.0
    top = max(set(variants), key=variants.count)
    return variants.count(top) / len(variants)


def trust(cons, conf, smooth, env, constraints_ok):
    """Weighted geometric mean, hard-gated by constraint satisfaction."""
    parts = [(cons, 3.0), (max(conf, 0.0) / 100.0, 1.0),
             (smooth, 2.0), (env, 2.0)]
    num = sum(w * math.log(max(p, 1e-3)) for p, w in parts)
    den = sum(w for _, w in parts)
    t = math.exp(num / den)
    return t * (1.0 if constraints_ok else 0.45)


def band(t):
    return "accept" if t >= 0.85 else ("review" if t >= 0.60 else "reject")


def digit_shift_hypothesis(v, neighbours):
    """If v looks like a misplaced decimal, propose the shift that fits."""
    ns = [n for n in neighbours if n and n > 0]
    if not ns or not v or v <= 0:
        return None
    med = stats.median(ns)
    best = None
    for k in (-2, -1, 1, 2):
        cand = v * (10.0 ** k)
        r = abs(math.log10(cand / med))
        if best is None or r < best[1]:
            best = (cand, r)
    if best and best[1] < 0.35 and abs(math.log10(v / med)) > 0.8:
        return best[0]
    return None
