"""
Score the matcher against real products that a human tagged with allergens.

WHY THIS EXISTS

Pona's knowledge base is hand-curated and not clinically reviewed. That is a
real limitation, and the honest response to it is measurement: rather than
asking anyone to trust the rules, run them over tens of thousands of real
products where a person independently recorded which allergens are present,
and report how often we agree.

Open Food Facts carries an `allergens` column with EU-14 taxonomy tags
("en:milk,en:gluten"). Pairing that with `ingredients_text` gives a labelled
set for free: ingredients in, known allergens out.

HOW TO READ THE RESULTS

Recall and precision are NOT equally trustworthy here, because the labels
are crowd-sourced and incomplete:

  RECALL (did we find what the human tagged?)
    Trustworthy. Someone had a reason to tag that allergen, so a miss is
    almost certainly our miss. This is the number that matters for safety.

  PRECISION (was everything we flagged really there?)
    A floor, not a true value. When we flag milk and the product isn't
    tagged for milk, that is either our false positive OR the tagger simply
    not filling the field in. Both look identical from here, so real
    precision is somewhere at or above what we print.

So: treat recall as the safety metric, and read precision as "no worse
than this". Where precision looks low, inspect the samples printed at the
end before assuming the matcher is wrong.

USAGE
    python benchmark_matcher.py [--rows N]

Requires the Open Food Facts export in data/raw/ (13GB, not in the repo).
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from app.ml.matcher import SENSITIVITY_KB, get_verdict  # noqa: E402

from off_data import find_off_csv  # noqa: E402

try:
    OFF_PATH = find_off_csv()
except FileNotFoundError:
    OFF_PATH = None

# Open Food Facts uses the EU-14 allergen taxonomy. Pona's knowledge base is
# built to the FDA major allergens, so the two overlap but do not coincide.
# Only tags in this map are scored; everything else is reported separately as
# out of scope rather than silently counted as a miss.
OFF_TAG_TO_CONDITION = {
    "en:milk": "Milk/Dairy allergy",
    "en:gluten": "Celiac disease",
    "en:soybeans": "Soy allergy",
    "en:eggs": "Egg allergy",
    "en:nuts": "Tree nut allergy",
    "en:peanuts": "Peanut allergy",
    "en:sesame-seeds": "Sesame allergy",
    "en:fish": "Fish allergy",
    "en:crustaceans": "Shellfish allergy",
    "en:sulphur-dioxide-and-sulphites": "Sulfite sensitivity",
}

# Present in the EU-14 but deliberately not in our knowledge base. Tracked so
# the gap is visible and quantified instead of just absent.
KNOWN_OUT_OF_SCOPE = {
    "en:celery": "EU-14 allergen, not an FDA major allergen",
    "en:mustard": "EU-14 allergen, not an FDA major allergen",
    "en:molluscs": "EU-14 allergen; FDA covers crustacean shellfish only",
    "en:lupin": "EU-14 allergen, not an FDA major allergen",
}


# The export is the English *site*, not English-only products: it carries
# labels worldwide in their local language. Our knowledge base is English,
# so mixing the two would understate real performance and hide the actual
# problem, which is a translation gap rather than a matching gap.
#
# This is a cheap heuristic, not language detection. It only needs to be
# right often enough to separate the two populations for reporting.
_NON_EN_MARKERS = {
    "fr": ["farine", "sucre", "lait", "oeuf", "œuf", "huile", "blé", "ble",
           "arôme", "arome", "épaississant", "colorant", "amidon", "eau"],
    "es": ["azúcar", "azucar", "leche", "harina", "aceite", "agua", "trigo"],
    "de": ["zucker", "milch", "mehl", "salz", "wasser", "weizen"],
    "it": ["zucchero", "latte", "olio", "acqua", "grano"],
    "pt": ["açúcar", "acucar", "leite", "farinha", "óleo"],
    "nl": ["suiker", "melk", "bloem", "zout", "tarwe"],
}
_EN_MARKERS = ["sugar", "salt", "water", "flour", "milk", "wheat", "oil",
               "contains", "ingredients", "corn", "soybean", "natural"]


def looks_english(text: str) -> bool:
    """Rough language split for reporting. Not language detection."""
    t = text.lower()
    en = sum(1 for m in _EN_MARKERS if m in t)
    other = sum(1 for words in _NON_EN_MARKERS.values() for m in words if m in t)
    return en >= other


ALL_CONDITIONS = sorted(set(OFF_TAG_TO_CONDITION.values()))


def detected_conditions(ingredients_text: str):
    """
    What does the matcher report for this label?

    Returns (confirmed, any_flag).

    Both are needed, because Pona has two levels of finding and they answer
    different questions:

      confirmed  - the ingredient is listed on the label
      any_flag   - confirmed, PLUS possible findings: precautionary
                   "may contain" statements, ambiguous terms like natural
                   flavors, and cross-contamination cases like oats

    Scoring only `confirmed` understates recall, because a user does see
    the possible flags. Scoring only `any_flag` overstates precision,
    because a possible flag is explicitly not a claim of presence. Report
    both and the difference is visible instead of hidden by whichever one
    happens to flatter the result.
    """
    result = get_verdict([ingredients_text], ALL_CONDITIONS)
    confirmed, any_flag = set(), set()
    for t in result["triggers"]:
        any_flag.add(t["sensitivity"])
        if t["confidence"] == "confirmed":
            confirmed.add(t["sensitivity"])
    return confirmed, any_flag


def main(rows: int) -> int:
    if OFF_PATH is None or not OFF_PATH.exists():
        print(f"ERROR: Open Food Facts export not found at {OFF_PATH}")
        print("This benchmark needs the 13GB raw dataset, which is not in the repo.")
        return 1

    print("=" * 78)
    print("MATCHER BENCHMARK vs human-tagged Open Food Facts products")
    print("=" * 78)
    print(f"\nReading {rows:,} rows...")

    df = pd.read_csv(
        OFF_PATH,
        usecols=["product_name", "ingredients_text", "allergens"],
        nrows=rows,
        sep="\t",
        low_memory=False,
    )
    labelled = df.dropna(subset=["ingredients_text", "allergens"])
    labelled = labelled[labelled["allergens"].str.strip().astype(bool)]
    print(f"  products with BOTH ingredients and allergen tags: {len(labelled):,}")

    if labelled.empty:
        print("\nNo labelled products in this slice. Try a larger --rows.")
        return 1

    # Scored separately per language group; "all" is the union.
    tp = {g: defaultdict(int) for g in ("en", "other", "all")}
    fn = {g: defaultdict(int) for g in ("en", "other", "all")}
    fp = {g: defaultdict(int) for g in ("en", "other", "all")}
    soft = {g: defaultdict(int) for g in ("en", "other", "all")}
    soft_tot = {g: defaultdict(int) for g in ("en", "other", "all")}
    counts = defaultdict(int)
    out_of_scope = defaultdict(int)
    fn_samples = defaultdict(list)
    fp_samples = defaultdict(list)

    for _, row in labelled.iterrows():
        text = str(row["ingredients_text"])
        tags = {t.strip() for t in str(row["allergens"]).split(",") if t.strip()}
        group = "en" if looks_english(text) else "other"
        counts[group] += 1

        for t in tags:
            if t in KNOWN_OUT_OF_SCOPE:
                out_of_scope[t] += 1

        expected = {OFF_TAG_TO_CONDITION[t] for t in tags if t in OFF_TAG_TO_CONDITION}
        actual, actual_any = detected_conditions(text)
        scorable = set(OFF_TAG_TO_CONDITION.values())
        for cond in scorable:
            if cond in expected:
                soft[group][cond] += 1 if cond in actual_any else 0
                soft_tot[group][cond] += 1

        for cond in scorable:
            in_expected, in_actual = cond in expected, cond in actual
            if in_expected and in_actual:
                tp[group][cond] += 1
                tp["all"][cond] += 1
            elif in_expected and not in_actual:
                fn[group][cond] += 1
                fn["all"][cond] += 1
                if group == "en" and len(fn_samples[cond]) < 3:
                    fn_samples[cond].append(text[:150])
            elif in_actual and not in_expected:
                fp[group][cond] += 1
                fp["all"][cond] += 1
                if group == "en" and len(fp_samples[cond]) < 3:
                    fp_samples[cond].append(text[:150])

    # ── Per-condition results ────────────────────────────────────────────
    def totals(group):
        return (
            sum(tp[group].values()),
            sum(fn[group].values()),
            sum(fp[group].values()),
        )

    print("\n" + "=" * 78)
    print("ENGLISH LABELS  (what Pona actually supports today)")
    print("=" * 78)
    print(f"\n  {len(labelled):,} labelled products, of which {counts['en']:,} "
          f"look English and {counts['other']:,} do not.")
    print(f"\n  {'condition':<24}{'tagged':>8}{'recall':>9}{'+poss':>9}{'prec*':>9}")
    print("  " + "-" * 74)

    for cond in sorted(set(OFF_TAG_TO_CONDITION.values())):
        t, f, p = tp["en"][cond], fn["en"][cond], fp["en"][cond]
        tagged = t + f
        if tagged == 0 and p == 0:
            continue
        r_s = f"{t / tagged:8.1%}" if tagged else "       -"
        st, stt = soft["en"][cond], soft_tot["en"][cond]
        s_s = f"{st / stt:8.1%}" if stt else "       -"
        p_s = f"{t / (t + p):8.1%}" if (t + p) else "       -"
        print(f"  {cond:<24}{tagged:>8}{r_s}{s_s}{p_s}")

    en_tp, en_fn, en_fp = totals("en")
    en_recall = en_tp / (en_tp + en_fn) if (en_tp + en_fn) else 0.0
    en_prec = en_tp / (en_tp + en_fp) if (en_tp + en_fp) else 0.0
    en_soft = sum(soft["en"].values())
    en_soft_tot = sum(soft_tot["en"].values())
    en_soft_r = en_soft / en_soft_tot if en_soft_tot else 0.0
    print("  " + "-" * 74)
    print(f"  {'ENGLISH':<24}{en_tp + en_fn:>8}{en_recall:8.1%}{en_soft_r:8.1%}{en_prec:8.1%}")
    print("\n  recall = the ingredient was listed and we confirmed it.")
    print("  +poss  = recall counting possible flags too ('may contain', oats,")
    print("           natural flavors). This is what the user actually sees.")
    print("  prec*  = a FLOOR: an untagged product may genuinely contain the")
    print("           allergen and simply not have the field filled in.")

    # ── The translation gap, quantified ──────────────────────────────────
    ot_tp, ot_fn, ot_fp = totals("other")
    al_tp, al_fn, al_fp = totals("all")
    ot_recall = ot_tp / (ot_tp + ot_fn) if (ot_tp + ot_fn) else 0.0
    al_recall = al_tp / (al_tp + al_fn) if (al_tp + al_fn) else 0.0

    print("\n" + "=" * 78)
    print("NON-ENGLISH LABELS  (a known gap, not a matching failure)")
    print("=" * 78)
    print(f"\n  English labels      recall {en_recall:6.1%}  ({en_tp + en_fn} allergen tags)")
    print(f"  Non-English labels  recall {ot_recall:6.1%}  ({ot_tp + ot_fn} allergen tags)")
    print(f"  Combined            recall {al_recall:6.1%}  ({al_tp + al_fn} allergen tags)")
    print("\n  The knowledge base is English-only, so 'farine de ble' and 'lait'")
    print("  are invisible to it. Fixing that is a translation problem: either")
    print("  ship multilingual synonyms or restrict the product to English")
    print("  labels and say so. Do not report the combined number as if it")
    print("  measured matching quality.")

    # ── Coverage gaps ────────────────────────────────────────────────────
    if out_of_scope:
        print("\n" + "=" * 78)
        print("TAGGED BUT OUT OF SCOPE (not in our knowledge base)")
        print("=" * 78)
        for tag, n in sorted(out_of_scope.items(), key=lambda x: -x[1]):
            print(f"  {n:>6} products  {tag:<38} {KNOWN_OUT_OF_SCOPE[tag]}")

    # ── Misses are the actionable output ─────────────────────────────────
    worst = sorted(
        ((c, fn["en"][c], tp["en"][c] + fn["en"][c]) for c in fn["en"] if fn["en"][c]),
        key=lambda x: -x[1],
    )[:5]
    if worst:
        print("\n" + "=" * 78)
        print("BIGGEST MISSES ON ENGLISH LABELS - the actionable failures")
        print("=" * 78)
        for cond, misses, tagged in worst:
            print(f"\n  {cond}: missed {misses} of {tagged}")
            for s in fn_samples[cond]:
                print(f"    - {s}")

    print("\n" + "=" * 78)
    print(f"Recall {en_recall:.1%} on {counts['en']:,} English human-tagged products.")
    print("Recall is the safety metric: a tagged allergen we missed is our miss.")
    print("Precision is a floor, because an untagged product may still contain it.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=200000,
                    help="rows to read from the OFF export (default 200000)")
    sys.exit(main(ap.parse_args().rows))
