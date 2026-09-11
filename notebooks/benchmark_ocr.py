"""
Score OCR against real photographs of ingredient panels.

WHY

The OCR settings were tuned against images this project generated itself:
flat, black on white, perfectly focused. They scored 95% and then failed
completely on the first real wrapper, because real packaging is curved,
glossy, badly lit and photographed at an angle.

Open Food Facts fixes that. Contributors upload a photo of the ingredient
panel AND transcribe it, so `image_ingredients_url` paired with
`ingredients_text` is thousands of real photo/ground-truth pairs in
exactly this domain - about 16k English ones.

METRIC

Word recall: of the words in the human transcription, how many did OCR
find? Not exact-match, because the transcription is not literal - it fixes
typos and omits marketing text. Recall answers the question that matters:
would we have seen the allergen?

Allergen recall is reported separately and weighted higher, because
missing "wheat" matters and missing "approximately" does not.

USAGE
    python benchmark_ocr.py --n 25          # sample size
    python benchmark_ocr.py --n 25 --psm 6  # single config

Needs Tesseract. Run inside the API image if it isn't installed locally:
    docker run --rm -v "$PWD:/w" -w /w pona-api python notebooks/benchmark_ocr.py
"""

import argparse
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd
from PIL import Image, ImageOps, ImageFilter
import pytesseract
from pytesseract import Output

from off_data import find_off_csv  # noqa: E402

try:
    OFF = find_off_csv()
except FileNotFoundError:
    OFF = None
CACHE = Path(__file__).parent.parent / "data" / "raw" / "ocr_samples"

# Words whose absence is a safety failure, not a cosmetic one.
ALLERGEN_WORDS = {
    "milk", "cream", "butter", "cheese", "whey", "casein", "lactose",
    "wheat", "gluten", "barley", "rye", "oats", "peanut", "peanuts",
    "almond", "almonds", "hazelnut", "cashew", "walnut", "pecan",
    "egg", "eggs", "soy", "soya", "soybean", "sesame", "fish", "shrimp",
    "crab", "prawn", "shellfish", "sulphite", "sulfite", "mustard",
    "celery", "nuts", "nut",
}


def words(text):
    return [w for w in re.findall(r"[a-z]+", str(text).lower()) if len(w) > 2]


def fetch(url, path):
    if path.exists():
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pona-ocr-benchmark/0.1"})
        path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        return True
    except Exception:
        return False


# ── preprocessing variants ────────────────────────────────────────────────

def prep_current(img):
    """What shipped: greyscale, autocontrast, sharpen, upscale only if tiny."""
    img = ImageOps.autocontrast(img.convert("L"))
    if min(img.size) < 1000:
        s = 1000 / min(img.size)
        img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    return img.filter(ImageFilter.SHARPEN)


def prep_downscale(img):
    """Cap the long edge. Huge phone photos give Tesseract too much noise."""
    img = img.convert("L")
    img = img.copy()
    img.thumbnail((2000, 2000), Image.LANCZOS)
    return ImageOps.autocontrast(img)


def prep_binary(img):
    """Autocontrast then hard threshold - aimed at washed-out, low-contrast shots."""
    img = prep_downscale(img)
    return img.point(lambda p: 255 if p > 128 else 0)


# Multi-pass: run several configs and merge everything they found. Each
# pass fails on different things - psm6 assumes a uniform block, psm11
# hunts sparse text - so the union recovers words no single pass sees.
# Costs a few seconds per photo. Precision falls (more junk words), which
# matters less here because the matcher only reacts to terms it knows.
MULTIPASS = [(prep_downscale, 6), (prep_downscale, 11), (prep_current, 6)]

VARIANTS = {
    "current(psm3)":        (prep_current, 3),
    "current(psm6)":        (prep_current, 6),
    "downscale(psm6)":      (prep_downscale, 6),
    "downscale(psm3)":      (prep_downscale, 3),
    "downscale(psm11)":     (prep_downscale, 11),
    "binary(psm6)":         (prep_binary, 6),
}


def run(img, prep, psm):
    try:
        d = pytesseract.image_to_data(prep(img), output_type=Output.DICT, config=f"--psm {psm}")
    except Exception:
        return "", 0.0
    ws, cs = [], []
    for w, c in zip(d["text"], d["conf"]):
        w = w.strip()
        try:
            c = float(c)
        except (TypeError, ValueError):
            continue
        if w and c >= 0:
            ws.append(w)
            cs.append(c)
    return " ".join(ws), (sum(cs) / len(cs) if cs else 0.0)


def main(n, only_psm):
    if OFF is None or not OFF.exists():
        print(f"ERROR: Open Food Facts export not found at {OFF}")
        return 1
    CACHE.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("OCR BENCHMARK vs real photographs of ingredient panels")
    print("=" * 78)
    print(f"\nSampling {n} English panels from Open Food Facts...")

    df = pd.read_csv(OFF, usecols=["code", "image_ingredients_url", "ingredients_text"],
                     nrows=200000, sep="\t", low_memory=False)
    d = df.dropna(subset=["image_ingredients_url", "ingredients_text"])
    d = d[~d["image_ingredients_url"].str.contains("/invalid/", na=False)]
    d = d[d["image_ingredients_url"].str.contains("ingredients_en", na=False)]
    d = d[d["ingredients_text"].str.len() > 40]
    d = d.sample(n=min(n, len(d)), random_state=42)

    variants = ({k: v for k, v in VARIANTS.items() if v[1] == only_psm}
                if only_psm else VARIANTS)

    tot = {k: [0, 0, 0, 0, 0] for k in variants}
    tot["MULTIPASS"] = [0, 0, 0, 0, 0]  # gt, found, gt_alg, found_alg, conf_sum
    used = 0

    for _, row in d.iterrows():
        url = row["image_ingredients_url"].replace(".400.jpg", ".full.jpg")
        path = CACHE / f"{row['code']}.jpg"
        if not fetch(url, path):
            continue
        try:
            img = Image.open(path)
        except Exception:
            continue

        gt = set(words(row["ingredients_text"]))
        if not gt:
            continue
        gt_alg = gt & ALLERGEN_WORDS
        used += 1
        print(f"  [{used}] {row['code']}  ({len(gt)} words, {len(gt_alg)} allergen)")

        if not only_psm:
            merged = set()
            mconf = []
            for prep, psm in MULTIPASS:
                t_, c_ = run(img, prep, psm)
                merged |= set(words(t_))
                mconf.append(c_)
            t = tot["MULTIPASS"]
            t[0] += len(gt); t[1] += len(gt & merged)
            t[2] += len(gt_alg); t[3] += len(gt_alg & merged)
            t[4] += max(mconf) if mconf else 0

        for name, (prep, psm) in variants.items():
            text, conf = run(img, prep, psm)
            got = set(words(text))
            t = tot[name]
            t[0] += len(gt)
            t[1] += len(gt & got)
            t[2] += len(gt_alg)
            t[3] += len(gt_alg & got)
            t[4] += conf

    if not used:
        print("\nNo images could be downloaded.")
        return 1

    print("\n" + "=" * 78)
    print(f"RESULTS over {used} real photographs")
    print("=" * 78)
    print(f"\n  {'config':<20}{'word recall':>14}{'ALLERGEN recall':>18}{'mean conf':>12}")
    print("  " + "-" * 62)
    names = list(variants) + ([] if only_psm else ["MULTIPASS"])
    for name in names:
        gtw, fw, gta, fa, cs = tot[name]
        wr = fw / gtw if gtw else 0
        ar = fa / gta if gta else 0
        print(f"  {name:<20}{wr:>13.1%}{ar:>17.1%}{cs / used:>11.1f}%")

    print("\n  Allergen recall is the one that matters: a missed 'wheat' is a")
    print("  safety failure, a missed 'approximately' is not.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--psm", type=int, default=None)
    a = ap.parse_args()
    sys.exit(main(a.n, a.psm))
