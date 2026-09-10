"""
Pona Data Exploration Pipeline
Runs the full analysis: FoodData Central + Open Food Facts sampling
Outputs: sensitivity KB, ingredient mappings, allergen insights
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from collections import Counter, defaultdict
import sys

# -- Setup ----------------------------------------------------------------------
print("=" * 80)
print("PONA DATA EXPLORATION & SENSITIVITY KB BUILDING")
print("=" * 80)

FDC_DIR = Path("../data/raw/FoodData_Central_foundation_food_csv_2026-04-30")
OFF_PATH = Path("../data/raw/en.openfoodfacts.org.products.csv")
OUTPUT_DIR = Path("../data/processed")
OUTPUT_DIR.mkdir(exist_ok=True)

print(f"\n[OK] FDC directory: {FDC_DIR.exists()}")
print(f"[OK] OFF file: {OFF_PATH.exists()}")

# -- Phase 1: Load FoodData Central ---------------------------------------------
print("\n" + "=" * 80)
print("PHASE 1: FOODDATA CENTRAL EXPLORATION")
print("=" * 80)

fdc_food = pd.read_csv(FDC_DIR / "food.csv", dtype={"fdc_id": str})
fdc_nutrient = pd.read_csv(FDC_DIR / "nutrient.csv")
fdc_food_nutrient = pd.read_csv(FDC_DIR / "food_nutrient.csv", dtype={"fdc_id": str})
fdc_food_attribute = pd.read_csv(FDC_DIR / "food_attribute.csv", dtype={"fdc_id": str})

print(f"\n  Foods: {len(fdc_food):,} items")
print(f"  Nutrients: {len(fdc_nutrient):,} unique nutrient types")
print(f"  Food-Nutrient mappings: {len(fdc_food_nutrient):,} records")
print(f"  Food attributes: {len(fdc_food_attribute):,} records\n")

# Extract allergen-related nutrients
ALLERGEN_KEYWORDS = [
    "allergen", "dairy", "milk", "gluten", "peanut", "tree nut", "nut",
    "shellfish", "fish", "soy", "sesame", "egg", "wheat",
    "lactose", "histamine", "purine", "sulfite", "salicylate",
    "caffeine", "acid", "sodium", "msg", "tyramine"
]

allergen_nutrients = fdc_nutrient[
    fdc_nutrient["name"].str.lower().str.contains(
        "|".join(ALLERGEN_KEYWORDS), na=False
    )
]

print(f"\n  Allergen-related nutrients found: {len(allergen_nutrients)}")

# -- Phase 2: Load Open Food Facts Sample ----------------------------------------
print("\n" + "=" * 80)
print("PHASE 2: OPEN FOOD FACTS SAMPLING & ANALYSIS")
print("=" * 80)

OFF_COLS = [
    "code", "product_name", "ingredients_text", "ingredients_tags",
    "allergens", "allergens_en", "categories_en", "manufacturing_places",
]

print(f"\n  Reading 50k products from OFF (13GB dataset)...")
off_sample = pd.read_csv(OFF_PATH, usecols=OFF_COLS, nrows=50000, low_memory=False, sep='\t')
print(f"  [OK] Loaded {len(off_sample):,} products")

# Clean & analyze
off_clean = off_sample.dropna(subset=["ingredients_tags"])
print(f"  [OK] Products with ingredient tags: {len(off_clean):,}")

# Extract ingredients
all_ingredients = []
for tags in off_clean["ingredients_tags"]:
    if pd.notna(tags):
        ingredients = [ing.strip() for ing in str(tags).split(",")]
        all_ingredients.extend(ingredients)

ingredient_freq = Counter(all_ingredients)
print(f"  [OK] Total ingredient occurrences: {len(all_ingredients):,}")
print(f"  [OK] Unique ingredients: {len(set(all_ingredients)):,}")

print(f"\n  TOP 20 MOST COMMON INGREDIENTS:")
for ingredient, count in ingredient_freq.most_common(20):
    pct = (count / len(all_ingredients)) * 100
    print(f"    {ingredient}: {count:,} ({pct:.1f}%)")

# Extract allergens
#
# NOTE: read `allergens`, not `allergens_en`. In this export allergens_en is
# empty in every row, so the previous version of this script silently
# produced an empty allergen analysis (allergen_frequency.json was "{}").
# The populated column is `allergens`, holding EU-14 taxonomy tags like
# "en:milk,en:gluten,en:soybeans".
ALLERGEN_COL = "allergens"
if off_clean[ALLERGEN_COL].notna().sum() == 0:
    raise RuntimeError(
        f"Column {ALLERGEN_COL!r} is empty for every row. Check the export's "
        f"schema before trusting any allergen numbers below."
    )

off_with_allergens = off_clean.dropna(subset=[ALLERGEN_COL])
all_allergens = []
for tags in off_with_allergens[ALLERGEN_COL]:
    if pd.notna(tags):
        allergens = [al.strip() for al in str(tags).split(",") if al.strip()]
        all_allergens.extend(allergens)

allergen_freq = Counter(all_allergens)
print(f"\n  Products with allergen warnings: {len(off_with_allergens):,}")
print(f"  Unique allergen types: {len(allergen_freq)}")

print(f"\n  TOP 15 ALLERGENS IN REAL PRODUCTS:")
for allergen, count in allergen_freq.most_common(15):
    pct = (count / len(off_with_allergens)) * 100
    print(f"    {allergen}: {count:,} products ({pct:.1f}%)")

# -- INSIGHT: Which sensitivities are most common in real data? ------------------
print("\n" + "-" * 80)
print("  [INSIGHT] INSIGHT: Real-world allergen prevalence")
print("-" * 80)
top_allergens = dict(allergen_freq.most_common(5))
print(f"  Most common allergens in real products:")
for allergen, count in top_allergens.items():
    pct = (count / len(off_with_allergens)) * 100
    print(f"    • {allergen}: {pct:.1f}% of products")

# -- Phase 3: Build Ingredient Synonyms ------------------------------------------
print("\n" + "=" * 80)
print("PHASE 3: INGREDIENT SYNONYM MAPPING")
print("=" * 80)

KNOWLEDGE_DIR = Path("../backend/app/ml/knowledge")


def load_knowledge(name):
    """
    Read a hand-curated knowledge file.

    These files are SOURCE, not output. This script used to define them as
    hardcoded literals and write them into data/processed/, which was wrong
    twice over: nothing here is actually derived from the Open Food Facts
    data, and data/processed/ is gitignored, so a fresh clone had no
    knowledge base and the app silently cleared every allergen. The app owns
    them now; this script reads them.
    """
    with open(KNOWLEDGE_DIR / name, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


INGREDIENT_SYNONYMS = load_knowledge("ingredient_synonyms.json")

variant_to_canonical = {}
for canonical, variants in INGREDIENT_SYNONYMS.items():
    variant_to_canonical[canonical] = canonical
    for variant in variants:
        variant_to_canonical[variant] = canonical

print(f"\n  Built synonym dictionary:")
print(f"    • Canonical ingredients: {len(INGREDIENT_SYNONYMS)}")
print(f"    • Total mappings: {len(variant_to_canonical)}")
print(f"\n  Example: 'peanut' variants")
for variant in INGREDIENT_SYNONYMS["peanuts"]:
    print(f"    '{variant}' -> 'peanuts'")

# -- Phase 4: Build Sensitivity Knowledge Base ----------------------------------
print("\n" + "=" * 80)
print("PHASE 4: SENSITIVITY KNOWLEDGE BASE")
print("=" * 80)

# SCOPE RULE (deliberate, do not widen without a reason):
#
# Pona answers exactly one question: "does this food contain something
# I personally react to?" It does NOT rate food as healthy or unhealthy,
# and it does not give dietary advice for managing a disease.
#
# An entry qualifies only if ALL of the following hold:
#   1. It is a reaction to a specific IDENTIFIABLE INGREDIENT, not to a
#      food category ("red meat", "fried food", "processed food").
#   2. The mechanism is supported by scientific evidence and reflected in
#      food-regulator guidance (FDA major allergens, FDA sulfite labelling
#      rule, FDA gluten-free labelling rule).
#   3. Stating it does not require judging the food itself.
#
# Removed under this rule, and why:
#   - MSG sensitivity: the reported symptom cluster originates in a 1968
#     anecdote and has not been reproduced in controlled double-blind
#     trials. FDA classifies MSG as generally recognized as safe. Asserting
#     the effect would spread a claim the evidence does not support, and
#     the original framing carries a well-documented racist history.
#   - Gout: this is dietary management of a diagnosed disease, not an
#     ingredient sensitivity, and it worked by flagging broad categories
#     ("red meat", "organ meat"). Genetics drive urate far more than diet.
#     Out of scope.
#   - GERD's default trigger list: reflux triggers are highly individual
#     and current guidance favours the triggers a person identifies for
#     themselves over blanket elimination. GERD stays, but as a condition
#     the user fills in from their own experience (see custom triggers).

SENSITIVITY_KB = load_knowledge("sensitivity_kb.json")

print(f"\n  Built sensitivity knowledge base:")
print(f"    • Conditions covered: {len(SENSITIVITY_KB)}")
print(f"    • Total trigger ingredients defined: {sum(len(v.get('ingredients', [])) for v in SENSITIVITY_KB.values())}")

print(f"\n  CONDITIONS BY PREVALENCE:")
for condition, data in sorted(SENSITIVITY_KB.items(), key=lambda x: x[1].get("prevalence", "N/A")):
    prevalence = data.get("prevalence", "N/A")
    severity = data.get("severity", "N/A")
    print(f"    • {condition}: {prevalence} | Severity: {severity}")

# -- INSIGHT: Health Equity & Underserved Populations -----------------------------
print("\n" + "-" * 80)
print("  [INSIGHT] INSIGHT: Health equity in food sensitivities")
print("-" * 80)
print("  Conditions commonly MISSED by Western-centric apps:")
print("    • Lactose intolerance: 65% of global population, especially:")
print("      - East Asian populations (~90%)")
print("      - West African populations (~90%)")
print("      - Most non-European ancestry")
print("    • Celiac disease: ~1% globally, frequently undiagnosed")
print("    • GERD: Major burden in Asia (20-30% in Western, higher in industrializing)")
print("\n  Regional ingredient terminology:")
print("    • 'Groundnuts' (Africa/Asia) = 'Peanuts' (North America)")
print("    • Pona's advantage: Explicitly handles regional variants")

# -- Phase 5: Validate Against Real Data ----------------------------------------
print("\n" + "=" * 80)
print("PHASE 5: VALIDATION AGAINST REAL PRODUCTS")
print("=" * 80)

# Test 1: Dairy products
dairy_products = off_clean[
    off_clean["ingredients_tags"].str.contains("milk", case=False, na=False)
]
print(f"\n  Test 1: Dairy allergen detection")
print(f"    • Products containing 'milk': {len(dairy_products):,}")
print(f"    • % of dataset: {len(dairy_products) / len(off_clean) * 100:.1f}%")

# multi_allergen_products = off_with_allergens[
#     off_with_allergens["allergens_en"].str.count(",") > 0
# ]
# print(f"\n  Test 2: Cross-allergen contamination risk")
# print(f"    • Products with multiple allergens: {len(multi_allergen_products):,}")
# print(f"    • % of allergen-containing products: {len(multi_allergen_products) / len(off_with_allergens) * 100:.1f}%")
# 
# -- INSIGHT: Hidden Complexity in Food Labels ----------------------------------
# print("\n" + "-" * 80)
# print("  [INSIGHT] INSIGHT: Complexity in real ingredient labels")
# print("-" * 80)
# sample_complex = off_clean[off_clean["ingredients_tags"].str.len() > 200].head(1)
# if len(sample_complex) > 0:
#     ingredients = sample_complex.iloc[0]["ingredients_tags"]
#     num_ingredients = len(ingredients.split(","))
#     print(f"  Example complex product:")
#     print(f"    • Number of ingredients: {num_ingredients}")
#     print(f"    • Sample ingredients: {ingredients[:150]}...")
#     print(f"\n  Challenge: Users need to parse ~{num_ingredients} ingredients")
#     print(f"  Solution: Pona's CV + NLP automates this")
# 
# -- Phase 6: Export Artifacts --------------------------------------------------
# print("\n" + "=" * 80)
print("PHASE 6: EXPORTING ARTIFACTS FOR ML PIPELINE")
print("=" * 80)

# NOTE: the synonym map and the sensitivity KB are deliberately NOT written
# here. They are hand-curated source owned by the app
# (backend/app/ml/knowledge/), and this script only reads them. Writing them
# back out is what previously destroyed hand-edits on every run.
print(f"\n  [--] ingredient_synonyms.json - source, read-only "
      f"({len(INGREDIENT_SYNONYMS)} canonical forms)")
print(f"  [--] sensitivity_kb.json - source, read-only "
      f"({len(SENSITIVITY_KB)} conditions)")

# 1. Ingredient frequency
ingredient_freq_sorted = dict(sorted(ingredient_freq.items(), key=lambda x: x[1], reverse=True))
with open(OUTPUT_DIR / "ingredient_frequency.json", "w") as f:
    json.dump(ingredient_freq_sorted, f, indent=2)
print(f"  [OK] ingredient_frequency.json ({len(ingredient_freq_sorted)} unique ingredients)")

# 4. Allergen frequency
allergen_freq_sorted = dict(sorted(allergen_freq.items(), key=lambda x: x[1], reverse=True))
with open(OUTPUT_DIR / "allergen_frequency.json", "w") as f:
    json.dump(allergen_freq_sorted, f, indent=2)
print(f"  [OK] allergen_frequency.json ({len(allergen_freq_sorted)} allergen types)")

# 5. Summary statistics
summary = {
    "timestamp": pd.Timestamp.now().isoformat(),
    "data_sources": {
        "fooddata_central": {
            "foods": len(fdc_food),
            "nutrients": len(fdc_nutrient),
            "allergen_related_nutrients": len(allergen_nutrients),
        },
        "open_food_facts_sample": {
            "total_products": len(off_sample),
            "with_ingredients": len(off_clean),
            "with_allergens": len(off_with_allergens),
        }
    },
    "analysis": {
        "unique_ingredients": len(set(all_ingredients)),
        "ingredient_occurrences": len(all_ingredients),
        "unique_allergens": len(allergen_freq),
        "sensitivity_conditions": len(SENSITIVITY_KB),
        "ingredient_synonyms": sum(len(v) for v in INGREDIENT_SYNONYMS.values()),
    },
    "top_allergens": dict(allergen_freq.most_common(10)),
    "top_ingredients": dict(ingredient_freq.most_common(20)),
}

with open(OUTPUT_DIR / "summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(f"  [OK] summary.json (analysis metadata)")

# -- Final Summary --------------------------------------------------------------
print("\n" + "=" * 80)
print("[SUCCESS] ANALYSIS COMPLETE")
print("=" * 80)
print(f"\nAll artifacts exported to: {OUTPUT_DIR.resolve()}")
print("\nNext steps:")
print("  1. NLP training: Fine-tune DistilBERT on ingredient normalization")
print("  2. CV training: Train YOLOv8 on Food-101 + Allergen30")
print("  3. Backend: Load KB + models into FastAPI")
print("  4. Frontend: Connect React app to API endpoints")
