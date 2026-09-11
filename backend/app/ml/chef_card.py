"""
The chef card: your profile, written for a kitchen.

WHY THIS EXISTS

The survey's largest theme was not reading labels - it was other people's
food, and the cost of asking about it:

    "Asking the one who prepared the food too many questions."
    "Making sure it is within my dietary requirements without offending
     anyone."
    "I have to decide how much I trust the waiter, read their body
     language to try to tell whether they know what they're talking about."
    "Dealing with the other person's reaction and the internal feeling of
     not being included."

None of that is an information problem for the diner - they already know
what they can't eat. It is a communication problem, and it costs them
socially every single time.

A chef card is the low-tech solution the celiac community already uses,
and it works. This generates one from the profile so it is always current,
uses the words a kitchen needs, and says the things a diner is least
comfortable saying out loud.

TWO THINGS IT DOES THAT A HANDWRITTEN CARD DOESN'T

1. Lists the hidden forms. A kitchen that knows to avoid milk may not
   think of casein, whey or ghee. Those come straight from the knowledge
   base that powers the matcher, so the card and the app never disagree.

2. Separates severity honestly. An allergy and an intolerance need
   different things from a kitchen - one needs clean equipment and is an
   emergency if missed, the other needs the ingredient left out. Flattening
   them either alarms kitchens unnecessarily or gets severe cases treated
   casually. Both failures are common, and both are avoidable.
"""

from typing import Dict, List, Optional

from app.ml.matcher import SENSITIVITY_KB, INGREDIENT_RULES, VARIANT_TO_CANONICAL

# Terms too generic to help a kitchen. "Contains milk, cheese, butter,
# cream, casein, whey, lactose" is useful; adding "dairy" is noise.
_SKIP = {"dairy", "gluten"}


def _hidden_forms_for(canonical: str) -> List[str]:
    """Label names for an ingredient that a kitchen may not connect to it."""
    forms = INGREDIENT_RULES.get("hidden_forms", {})
    out = forms.get(canonical, [])
    return [f for f in out if isinstance(f, str)][:8] if isinstance(out, list) else []


def _ingredients_for(condition: str) -> List[str]:
    entry = SENSITIVITY_KB.get(condition, {})
    return [i for i in entry.get("ingredients", []) if i not in _SKIP]


def build_chef_card(
    conditions: List[str],
    personal_triggers: Optional[List[Dict]] = None,
    name: Optional[str] = None,
) -> Dict:
    """
    Build a card a diner can hand to a server or kitchen.

    Returns structured data rather than a formatted string so the client
    can render it for a screen, a printout, or a message - and so the
    severity split stays machine-readable instead of buried in prose.
    """
    personal_triggers = personal_triggers or []

    # Grouped by NATURE, not severity. What a kitchen must do differs by
    # mechanism: an IgE allergy and celiac disease both need clean
    # equipment, but calling celiac "an allergy" is wrong and is exactly
    # the conflation the knowledge base was split to avoid. An intolerance
    # needs the ingredient left out and nothing more.
    groups = {"allergy": [], "autoimmune": [], "intolerance": [], "individual": []}
    unknown = []

    for cond in conditions:
        entry = SENSITIVITY_KB.get(cond)
        if entry is None:
            unknown.append(cond)
            continue

        ingredients = _ingredients_for(cond)
        hidden = []
        for ing in ingredients:
            hidden.extend(_hidden_forms_for(ing))
        # De-duplicate, keep order.
        seen, hidden_clean = set(), []
        for h in hidden:
            if h.lower() not in seen:
                seen.add(h.lower())
                hidden_clean.append(h)

        item = {
            "condition": cond,
            "avoid": ingredients,
            "also_listed_as": hidden_clean[:12],
            "note": entry.get("note") or "",
        }
        nature = entry.get("nature") or (
            "allergy" if entry.get("severity") == "high" else "intolerance"
        )
        item["nature"] = nature
        # A condition with no assumed ingredients (reflux) has nothing to
        # print under "avoid" - it is covered by the personal list below.
        if nature == "individual" and not ingredients:
            continue
        groups.setdefault(nature, []).append(item)

    # The user's own triggers, grouped by the condition they named.
    personal = []
    for t in personal_triggers:
        ing = (t.get("ingredient") or "").strip()
        if ing:
            personal.append({"ingredient": ing, "condition": t.get("condition") or ""})

    # The part a diner finds hardest to say. Only included when something
    # on the profile actually warrants it - a cross-contact request on an
    # intolerance trains kitchens to discount the ones that matter.
    # Trace amounts matter for both IgE allergy and celiac disease, so both
    # warrant the clean-equipment request. Asking for it on an intolerance
    # would train kitchens to discount the request when it does matter.
    cross_contact = bool(groups["allergy"] or groups["autoimmune"])

    lines = []
    if groups["allergy"]:
        lines.append(
            "This is a severe allergy. Even a small amount can cause a serious "
            "reaction, so please prepare this on clean equipment with clean hands."
        )
    if groups["autoimmune"]:
        lines.append(
            "Celiac disease is an autoimmune condition, not an allergy. It will not "
            "cause an allergic reaction, but even a trace of gluten does real damage, "
            "so shared fryers, boards and utensils are a genuine problem."
        )
    if groups["intolerance"]:
        lines.append(
            "These are intolerances rather than allergies. They will not cause an "
            "emergency, but they do cause real discomfort, so please leave them out."
        )
    if personal:
        lines.append(
            "These are foods I personally react to. They may not affect other people "
            "with the same condition."
        )

    severe = groups["allergy"] + groups["autoimmune"]
    manageable = groups["intolerance"] + groups["individual"]
    questions = _questions(severe, manageable, personal)

    return {
        "name": name or "",
        "severe": severe,
        "manageable": manageable,
        "personal": personal,
        "unknown": unknown,
        "cross_contact": cross_contact,
        "statements": lines,
        "questions_to_ask": questions,
        "disclaimer": (
            "Generated from my profile. It lists what I avoid - it cannot tell "
            "you what is in your dishes."
        ),
    }


def _questions(severe, manageable, personal) -> List[str]:
    """
    The specific questions worth asking this kitchen.

    A respondent described the problem as "asking too many questions".
    The answer is not more questions - it is the two or three that
    actually change the answer, phrased so a server can act on them.
    """
    qs = []
    names = [i["condition"] for i in severe + manageable]

    fried = {"Celiac disease", "Wheat allergy"}
    if fried & set(names):
        qs.append("Is the fryer shared with battered or breaded items?")
    if any(n in {"Milk/Dairy allergy", "Lactose intolerance"} for n in names):
        qs.append("Is there butter, cream or yoghurt in the sauce or the finish?")
    if "Celiac disease" in names:
        qs.append("Does the sauce or marinade contain soy sauce, stock or flour as a thickener?")
    if any(n in {"Peanut allergy", "Tree nut allergy"} for n in names):
        qs.append("Are nuts used anywhere in this dish, including the oil or a garnish?")
    if severe:
        qs.append("Can this be prepared on clean equipment, away from the allergen?")
    for p in personal[:3]:
        qs.append(f"Does this dish contain {p['ingredient']}?")

    return qs[:6]
