"""
What to use instead.

The other half of the product. Telling someone a food contains milk is
only useful if they were choosing what to buy; if they are standing in a
kitchen cooking for someone, the question is "what do I use instead".

WHY THIS IS CURATED RATHER THAN LEARNED

The original design called for FAISS over FoodBERT/Food2Vec embeddings.
Embeddings encode which ingredients are SIMILAR, and in recipe text cream
is extremely similar to milk - they appear in the same dishes, the same
sentences, the same positions. A nearest-neighbour lookup would rank
cream as a top substitute for milk, which for a dairy allergy is the most
dangerous answer possible.

Substitution needs functional equivalence AND allergen difference. Only
the first is expressible as similarity. So the knowledge is curated, and
the safety half is enforced in code below.

THE SAFETY PROPERTY

Every candidate is re-checked against the user's own profile before it is
returned. Oat milk is an excellent substitute for dairy and completely
wrong for someone with celiac disease. A substitution engine that ignores
the rest of the profile just moves the problem.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from app.ml.matcher import _load_required, get_verdict

SUBS_PATH = Path(__file__).parent / "knowledge" / "substitutions.json"

_RAW = _load_required(SUBS_PATH, "substitution knowledge")
SUBSTITUTIONS: Dict[str, List[dict]] = {
    k: v for k, v in _RAW.items() if not k.startswith("_") and isinstance(v, list)
}
print(f"[SUBS] Loaded substitutes for {len(SUBSTITUTIONS)} ingredients")

VALID_CONTEXTS = ("baking", "cooking", "raw")


def get_substitutions(
    ingredient: str,
    context: Optional[str] = None,
    user_sensitivities: Optional[List[str]] = None,
    personal_triggers: Optional[List[Dict]] = None,
) -> List[dict]:
    """
    Safe alternatives for one ingredient, filtered to this user.

    Returns each candidate annotated with whether it is safe for THIS
    person. Unsafe ones are not silently dropped - they are returned
    marked, with the reason, because "oat milk, but not for you because of
    celiac" is more useful than an unexplained absence, and it stops the
    user finding the same suggestion elsewhere and assuming it is fine.
    """
    key = (ingredient or "").strip().lower()
    candidates = SUBSTITUTIONS.get(key, [])
    if not candidates:
        return []

    if context and context in VALID_CONTEXTS:
        candidates = [c for c in candidates if context in c.get("context", [])]

    user_sensitivities = user_sensitivities or []
    out = []
    for c in candidates:
        conflicts = []
        # Run each thing the substitute contains through the same matcher
        # the rest of the app uses, so the check cannot drift from it.
        for item in c.get("contains", []):
            result = get_verdict([item], user_sensitivities, personal_triggers)
            for t in result["triggers"]:
                conflicts.append({
                    "ingredient": item,
                    "sensitivity": t["sensitivity"],
                    "confidence": t["confidence"],
                })
        out.append({
            "name": c["name"],
            "notes": c.get("notes", ""),
            "context": c.get("context", []),
            "contains": c.get("contains", []),
            "safe_for_you": not conflicts,
            "conflicts": conflicts,
        })

    # Safe ones first; otherwise keep the curated order, which runs best
    # substitute first.
    out.sort(key=lambda s: not s["safe_for_you"])
    return out


def substitutions_for_verdict(
    verdict: dict,
    context: Optional[str] = None,
    user_sensitivities: Optional[List[str]] = None,
    personal_triggers: Optional[List[Dict]] = None,
) -> Dict[str, List[dict]]:
    """
    Given a verdict, offer alternatives for whatever triggered it.

    Keyed by the triggering ingredient. Ingredients with nothing curated
    are omitted rather than returned empty - an empty list reads as "there
    is no substitute", which is a stronger claim than "we don't have one".
    """
    out = {}
    for t in verdict.get("triggers", []):
        ing = t["ingredient"]
        if ing in out:
            continue
        subs = get_substitutions(ing, context, user_sensitivities, personal_triggers)
        if subs:
            out[ing] = subs
    return out
