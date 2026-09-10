"""
Matching-engine tests (pure logic, no database, no HTTP).

Separate from test_api.py on purpose: this file pins down WHAT the matcher
believes about food, which is the part that can hurt someone if it is wrong.
test_api.py covers plumbing; this covers judgement.

Every case below is a real label form. Two failure modes are tested with
equal weight:

  FALSE NEGATIVE - we miss a real allergen. Someone gets hurt.
  FALSE POSITIVE - we flag a safe food. The user stops trusting the app,
                   ignores a later warning, and someone gets hurt.

Both matter. A matcher that flags everything is as useless as one that
flags nothing.
"""

from app.ml.matcher import (
    get_verdict,
    normalize_ingredient,
    normalize_ingredients,
    parse_ingredient_list,
    find_ambiguous,
)

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
        print(f"  [FAIL] {msg}")
    return cond


print("\n" + "=" * 78)
print("MATCHING ENGINE TESTS")
print("=" * 78)

# ── 1. Label parsing ───────────────────────────────────────────────────────────

print("\n[1] Real labels are not clean lists - parse them")

label = "MILK CHOCOLATE (SUGAR, COCOA BUTTER, MILK), PEANUTS, SALT."
parts = parse_ingredient_list(label)
check("milk chocolate" in parts, f"nested label not flattened: {parts}")
check("cocoa butter" in parts, f"parenthesised sub-ingredient lost: {parts}")
check("peanuts" in parts, f"top-level ingredient lost: {parts}")
print(f"  parsed {len(parts)} phrases from a nested label")

# ── 2. False negatives - real label forms that MUST be caught ─────────────────

print("\n[2] Real-world label forms must be detected (false-negative guard)")

must_detect = [
    ("peanut butter",             "Peanut allergy",       "most common peanut form"),
    ("roasted peanuts",           "Peanut allergy",       "adjective prefix"),
    ("groundnut oil",             "Peanut allergy",       "non-US name"),
    ("wheat flour",               "Celiac disease", "most common gluten form"),
    ("enriched flour",            "Celiac disease", "hidden gluten"),
    ("semolina",                  "Celiac disease", "shares no word with wheat"),
    ("seitan",                    "Celiac disease", "pure gluten"),
    ("whey protein concentrate",  "Milk/Dairy allergy",   "hidden dairy"),
    ("sodium caseinate",          "Milk/Dairy allergy",   "hidden dairy"),
    ("nonfat dry milk",           "Milk/Dairy allergy",   "US label term"),
    ("ghee",                      "Milk/Dairy allergy",   "clarified butter"),
    ("buttermilk",                "Milk/Dairy allergy",   "genuinely dairy"),
    ("marzipan",                  "Tree nut allergy",     "almond paste"),
    ("gianduja",                  "Tree nut allergy",     "hazelnut chocolate"),
    ("surimi",                    "Shellfish allergy",    "imitation crab"),
    ("sodium metabisulfite",      "Sulfite sensitivity",  "E-number preservative"),
]
for ing, cond, why in must_detect:
    r = get_verdict([ing], [cond])
    check(len(r["triggers"]) > 0, f"MISSED {ing!r} for {cond} ({why})")
print(f"  {len(must_detect)} label forms checked")

# ── 3. False positives - safe foods that must NOT be flagged ──────────────────

print("\n[3] Safe foods must not be flagged (false-positive guard)")

must_not_detect = [
    ("cocoa butter",    "Milk/Dairy allergy",   "vegan; word-match trap"),
    ("coconut milk",    "Milk/Dairy allergy",   "not dairy"),
    ("coconut milk",    "Lactose intolerance",  "not dairy"),
    ("almond milk",     "Milk/Dairy allergy",   "not dairy"),
    ("oat milk",        "Lactose intolerance",  "not dairy"),
    ("shea butter",     "Milk/Dairy allergy",   "not dairy"),
    ("cream of tartar", "Milk/Dairy allergy",   "not dairy"),
    ("lactic acid",     "Lactose intolerance",  "not lactose despite the name"),
    ("nutmeg",          "Tree nut allergy",     "not a nut"),
    ("water chestnut",  "Tree nut allergy",     "not a tree nut"),
    ("buckwheat",       "Celiac disease", "gluten-free despite the name"),
    ("rice flour",      "Celiac disease", "gluten-free"),
    ("almond flour",    "Celiac disease", "gluten-free"),
    ("peanut butter",   "Milk/Dairy allergy",   "contains no dairy"),
]
for ing, cond, why in must_not_detect:
    r = get_verdict([ing], [cond])
    check(
        len(r["triggers"]) == 0,
        f"FALSE POSITIVE on {ing!r} for {cond} ({why}): "
        f"{[t['ingredient'] for t in r['triggers']]}",
    )
print(f"  {len(must_not_detect)} safe foods checked")

# ── 4. A guard must not over-block ────────────────────────────────────────────

print("\n[4] False-friend guards must be narrow, not blanket")

# "almond milk" is excused from DAIRY but is still very much a tree nut.
r = get_verdict(["almond milk"], ["Tree nut allergy"])
check(len(r["triggers"]) > 0, "almond milk wrongly cleared for TREE NUT allergy")

# "peanut butter" is excused from DAIRY but is still a peanut.
r = get_verdict(["peanut butter"], ["Peanut allergy"])
check(len(r["triggers"]) > 0, "peanut butter wrongly cleared for PEANUT allergy")
print("  guards block only the term they name")

# ── 5. Ambiguous ingredients ──────────────────────────────────────────────────

print("\n[5] Ambiguous ingredients: flagged with a reason, never silently cleared")

r = get_verdict(["sugar", "natural flavors"], ["Milk/Dairy allergy"])
# An ingredient that MIGHT hide dairy is a "possible" finding, distinct from
# a confirmed one. It must not be reported as nothing found...
check(
    r["verdict"] == "possible_triggers",
    f"ambiguous should be possible_triggers, got {r['verdict']}",
)
check(
    r["triggers"] and r["triggers"][0]["confidence"] == "possible",
    "ambiguous trigger not marked 'possible'",
)
check(bool(r["triggers"][0]["explanation"]), "ambiguous trigger has no reason given")

# ...and equally must not be reported as a confirmed presence. We are
# guessing, and dressing a guess up as certainty teaches users to
# discount the certain findings too.
check(
    r["verdict"] != "contains_trigger",
    "a possible match was reported as a confirmed one",
)

# ...and must not be raised for conditions it has nothing to do with.
r = get_verdict(["sugar", "natural flavors"], ["Peanut allergy"])
check(r["verdict"] == "no_triggers_found", "ambiguous raised against an unrelated condition")
print("  ambiguity reported as 'possible', scoped to relevant conditions")

# ── 6. A confirmed ingredient is reported as confirmed ───────────────────────

print("\n[6] A confirmed ingredient is reported as present, with its source named")

snickers = ("INGREDIENTS: MILK CHOCOLATE (SUGAR, COCOA BUTTER, CHOCOLATE, "
            "SKIM MILK, MILKFAT, SOY LECITHIN), PEANUTS, SUGAR, DEXTROSE, "
            "SALT, NATURAL AND ARTIFICIAL FLAVORS.")
r = get_verdict([snickers], ["Peanut allergy", "Lactose intolerance"])
check(
    r["verdict"] == "contains_trigger",
    f"peanuts in a peanut-allergy profile not reported as present: {r['verdict']}",
)
names = [t["ingredient"] for t in r["triggers"] if t["confidence"] == "confirmed"]
check("peanuts" in names, f"peanuts not confirmed in a peanut bar: {names}")
check("milk" in names, f"milk not confirmed in a milk chocolate bar: {names}")
print(f"  full label -> {r['verdict']}, confirmed: {names}")

# ── 6b. Language must stay descriptive, not evaluative ───────────────────────

print("\n[6b] Pona describes what it found; it does not rate the food")

BANNED = ["safe to eat", "unsafe", "healthy", "unhealthy", "bad for", "good for",
          "junk", "clean", "guilt", "cheat", "indulge", "avoid this food"]
samples = [
    get_verdict(["salt", "sugar"], ["Peanut allergy"]),
    get_verdict([snickers], ["Peanut allergy"]),
    get_verdict(["sugar", "natural flavors"], ["Milk/Dairy allergy"]),
    get_verdict(["salt"], ["Acid reflux / GERD"]),
]
for s in samples:
    text = (s["explanation"] + " " + s["verdict_label"]).lower()
    for word in BANNED:
        check(word not in text, f"evaluative language {word!r} in: {text[:90]}")
print(f"  {len(samples)} results checked for diet-culture language")

# ── 6f. Judgment calls, recorded so they are changed deliberately ────────────

print("\n[6f] Contested cases resolved deliberately, not by accident")

# OATS + CELIAC. Oats contain no gluten, but are usually grown and milled
# with wheat. Flagged as 'possible' rather than 'confirmed': saying an oat
# product "contains gluten" is factually wrong, while saying nothing is
# unsafe. The explanation carries the certified-gluten-free guidance.
for oat in ["whole grain oats", "oat fiber", "rolled oats", "oatmeal"]:
    r = get_verdict([oat], ["Celiac disease"])
    check(bool(r["triggers"]), f"oats not flagged for celiac: {oat!r}")
    check(
        all(t["confidence"] == "possible" for t in r["triggers"]),
        f"oats reported as confirmed gluten, which is factually wrong: {oat!r}",
    )
    check(
        "certified gluten-free" in r["triggers"][0]["explanation"],
        "oats flagged without telling the user certified gluten-free oats exist",
    )

# ...but oats certified gluten-free are produced to avoid that contamination.
for oat in ["gluten-free oats", "certified gluten free oats"]:
    r = get_verdict([oat], ["Celiac disease"])
    check(not r["triggers"], f"certified gluten-free oats wrongly flagged: {oat!r}")

# COCONUT is deliberately NOT a tree nut. The FDA classifies it as one for
# labelling, but that is a labelling convention, not a clinical finding:
# coconut allergy is uncommon and largely independent of tree nut allergy.
# Measured on 14,798 real products, following the FDA made 860 of 1,073
# tree-nut flags coconut products - noise that teaches people to dismiss
# warnings, which costs more safety than it buys.
for c in ["coconut", "coconut oil", "coconut flour", "shredded coconut",
          "coconut milk", "coconut water"]:
    r = get_verdict([c], ["Tree nut allergy"])
    check(not r["triggers"], f"coconut flagged as a tree nut: {c!r}")

# ...and coconut is still not dairy, whatever its name suggests.
for c in ["coconut milk", "coconut cream"]:
    r = get_verdict([c], ["Milk/Dairy allergy"])
    check(not r["triggers"], f"coconut wrongly flagged as dairy: {c!r}")

# A real tree nut alongside coconut must still be caught - clearing coconut
# must not clear the product.
r = get_verdict(["coconut oil, almonds, sugar"], ["Tree nut allergy"])
check(bool(r["triggers"]), "coconut cleared the whole product; almonds missed")

# The rare person who DOES react to coconut is served by their own trigger
# list, so this decision costs them nothing.
r = get_verdict(
    ["coconut oil, sugar"],
    ["Tree nut allergy"],
    personal_triggers=[{"ingredient": "coconut", "condition": "Tree nut allergy"}],
)
check(
    any(t["ingredient"] == "coconut" for t in r["triggers"]),
    "a user who listed coconut as their own trigger was not warned",
)

# CREAMER. US labelling permits "non-dairy" on a product containing sodium
# caseinate, a milk protein. Ambiguous rather than confirmed.
for c in ["creamer", "non-dairy creamer"]:
    r = get_verdict([c], ["Milk/Dairy allergy"])
    check(bool(r["triggers"]), f"creamer not flagged at all: {c!r}")
    check(
        all(t["confidence"] == "possible" for t in r["triggers"]),
        f"creamer reported as confirmed dairy: {c!r}",
    )
print("  oats, coconut and creamer resolved as recorded in ingredient_rules.json")

# ── 6g. Unspaced compounds ───────────────────────────────────────────────────

print("\n[6g] Labels that run words together")

# Found by benchmarking: "wheatflour" was missed while "wheat flour" matched.
for compound in ["wheatflour", "wholewheat", "wheatstarch"]:
    r = get_verdict([compound], ["Celiac disease"])
    check(bool(r["triggers"]), f"unspaced compound missed: {compound!r}")

# These are listed explicitly rather than by substring matching, which would
# reintroduce exactly the false positives section 3 guards against.
r = get_verdict(["cocoa butter"], ["Milk/Dairy allergy"])
check(not r["triggers"], "substring matching crept back in: cocoa butter -> dairy")
print("  unspaced forms matched without resorting to substring matching")

# ── 6e. Precautionary labelling ("may contain") ──────────────────────────────

print("\n[6e] 'May contain' is a warning, not an ingredient")

# Found by benchmarking against real products: a label reading
# ". may contain soybeans." was being reported as confirmed soy. The
# allergen may not be in the product at all - it is a cross-contamination
# statement, and reporting it as an ingredient overstates the label.
precautionary = [
    "Sugar, cocoa butter. May contain traces of peanuts.",
    "Sugar, cocoa. May also contain peanuts.",
    "Rice, salt. Traces of peanuts.",
    "Oats, salt. Produced in a facility that also processes peanuts.",
    "Oats, salt. Manufactured on shared equipment with peanuts.",
]
for label in precautionary:
    r = get_verdict([label], ["Peanut allergy"])
    confs = [t["confidence"] for t in r["triggers"]]
    check(bool(r["triggers"]), f"precautionary allergen not surfaced at all: {label!r}")
    check(
        "confirmed" not in confs,
        f"'may contain' reported as a confirmed ingredient: {label!r}",
    )
    check(
        r["verdict"] == "possible_triggers",
        f"expected possible_triggers for {label!r}, got {r['verdict']}",
    )

# ...but an allergen actually in the list is still confirmed.
r = get_verdict(["Peanuts, sugar, salt."], ["Peanut allergy"])
check(
    r["verdict"] == "contains_trigger",
    "a listed ingredient was downgraded to possible",
)

# An ingredient present AND repeated in a may-contain line stays confirmed.
r = get_verdict(
    ["Peanuts, sugar. May contain traces of peanuts."], ["Peanut allergy"]
)
check(
    any(t["confidence"] == "confirmed" for t in r["triggers"]),
    "listed peanuts downgraded because a may-contain line also mentioned them",
)
print(f"  {len(precautionary)} precautionary forms -> possible, not confirmed")

# ── 6c. User-defined conditions ──────────────────────────────────────────────

print("\n[6c] Conditions with individual triggers use the USER's list")

# Pona ships no trigger list for reflux, because reflux triggers differ so
# much between people that asserting one would be inventing information.

# With nothing added, we must NOT claim the food was checked for it.
r = get_verdict(["coffee", "sugar"], ["Acid reflux / GERD"])
check(
    r["verdict"] != "no_triggers_found",
    "claimed 'no triggers found' for a condition with nothing to look for",
)
check(
    "Acid reflux / GERD" in r["conditions_needing_setup"],
    f"un-set-up condition not surfaced: {r['conditions_needing_setup']}",
)

# The KB must not smuggle in a default trigger list.
from app.ml.matcher import SENSITIVITY_KB
check(
    SENSITIVITY_KB["Acid reflux / GERD"]["ingredients"] == [],
    "reflux has a built-in trigger list - triggers are individual, do not assume them",
)

# Once the user says what THEY react to, that is what gets matched.
r = get_verdict(
    ["coffee", "sugar"],
    ["Acid reflux / GERD"],
    personal_triggers=[{"ingredient": "coffee", "condition": "Acid reflux / GERD"}],
)
check(r["verdict"] == "contains_trigger", f"user's own trigger not matched: {r['verdict']}")
check(
    any(t["ingredient"] == "coffee" for t in r["triggers"]),
    "the user's own trigger was not reported",
)
check(not r["conditions_needing_setup"], "condition still flagged as needing setup")

# A food the user did NOT list stays unflagged - no assumed triggers.
r = get_verdict(
    ["tomato", "sugar"],
    ["Acid reflux / GERD"],
    personal_triggers=[{"ingredient": "coffee", "condition": "Acid reflux / GERD"}],
)
check(
    not any(t["ingredient"] == "tomato" for t in r["triggers"]),
    "flagged tomato for reflux when the user never said they react to it",
)
print("  no assumed triggers; the user's own list drives the result")

# ── 6d. Removed entries stay removed ─────────────────────────────────────────

print("\n[6d] Claims without evidence are not in the knowledge base")

for gone, why in [
    ("MSG sensitivity", "symptom cluster not reproduced in controlled trials"),
    ("Gout", "disease diet advice using broad food categories, not a sensitivity"),
]:
    check(gone not in SENSITIVITY_KB, f"{gone!r} is back in the KB ({why})")

# No entry may match on a food category rather than an ingredient.
CATEGORIES = ["red meat", "organ meat", "fried", "fatty", "processed", "junk"]
for cond, entry in SENSITIVITY_KB.items():
    for ing in entry.get("ingredients", []):
        check(
            ing.lower() not in CATEGORIES,
            f"{cond!r} matches on the food category {ing!r}, not an ingredient",
        )
print("  no unsubstantiated conditions, no food-category matching")

# ── 7. Unknown input is preserved, not swallowed ─────────────────────────────

print("\n[7] Unrecognised ingredients stay visible")

out = normalize_ingredients(["xyzabc123"])
check(out == ["xyzabc123"], f"unknown ingredient was swallowed: {out}")
check(normalize_ingredient("") == [], "empty phrase should yield nothing")
print("  unknown terms passed through so the user can see what we read")

# ── Summary ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 78)
if failures:
    print(f"{len(failures)} FAILURE(S)")
    print("=" * 78)
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)

print("ALL MATCHER TESTS PASSED")
print("=" * 78)
print("""
Covered:
  [x] Nested real-world labels parsed into ingredients
  [x] 16 hidden/compound label forms detected (false-negative guard)
  [x] 14 safe foods not flagged (false-positive guard)
  [x] Exclusion guards scoped to one term, not blanket-clearing a food
  [x] Ambiguous ingredients -> 'possible', never silently cleared,
      never dressed up as confirmed
  [x] Confirmed ingredients reported as present, with the source named
  [x] No evaluative or diet-culture language in any user-facing string
  [x] User-defined conditions match the USER's list, with no assumed
      triggers, and say so when nothing has been set up yet
  [x] Unsubstantiated conditions stay out of the KB; nothing matches on a
      food category rather than an ingredient
  [x] Unrecognised ingredients preserved for the user to see

NOT covered - the knowledge base itself is SEED DATA and has not been
reviewed by a dietitian or allergist. These tests prove the ENGINE behaves
correctly on the rules it is given; they do not prove the rules are
clinically complete.
""")
