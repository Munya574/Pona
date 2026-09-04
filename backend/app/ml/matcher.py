"""
Sensitivity Matching Engine

This is the heart of Pona.

Algorithm:
  1. User scans food → get list of ingredients
  2. Load user's sensitivities from database
  3. For each sensitivity, check if any ingredient matches KB
  4. Collect triggers with explanations
  5. Determine verdict (Safe / Caution / Unsafe)
  6. Return verdict + triggers + plain-English explanation

RECRUITERS CARE: This is rule-based ML. We use the sensitivity KB we built
to make decisions. This is auditable, explainable, and scales to new
conditions without retraining models.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from enum import Enum

# ── Load sensitivity KB at module import ───────────────────────────────────────
# Why load at import time?
# - KB is static (updated in notebooks, app restarts to load new version)
# - Avoids repeated file I/O on every verdict request
# - In-memory lookup is fast

# All three knowledge files are hand-curated SOURCE and live with the code
# that needs them. They were previously written out by notebooks/run_analysis.py
# into data/processed/, which was wrong twice over: they are not derived from
# the Open Food Facts data at all (the script just dumped hardcoded literals),
# and living in an ignored, "regenerated" directory meant a fresh clone had no
# knowledge base and cleared every allergen. run_analysis.py now reads these.
KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
KB_PATH = KNOWLEDGE_DIR / "sensitivity_kb.json"
SYNONYMS_PATH = KNOWLEDGE_DIR / "ingredient_synonyms.json"
RULES_PATH = KNOWLEDGE_DIR / "ingredient_rules.json"


def _load_required(path: Path, what: str) -> dict:
    """
    Load a required knowledge file, or refuse to start.

    Why raise instead of falling back to an empty dict?

    An empty KB does not degrade gracefully — it degrades DANGEROUSLY.
    With no KB, every ingredient matches nothing, so every food returns
    "safe". A user with a peanut allergy would be told peanuts are safe
    to eat, with no visible error. A crash at startup is loud, obvious,
    and fixable; a silent green checkmark on an allergen is not.

    Rule: in a safety-critical path, fail closed, never fail quiet.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise RuntimeError(
            f"Cannot start: {what} not found at {path}\n"
            f"This file is required — without it every verdict would wrongly "
            f"return 'safe'. Verify the file exists and is tracked in git "
            f"(see .gitignore: data/processed/ is ignored except the KB files)."
        ) from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Cannot start: {what} at {path} is not valid JSON — {e}") from e


def _strip_docs(d: dict) -> dict:
    """Drop the _README / _comment keys that document these files."""
    return {k: v for k, v in d.items() if not k.startswith("_")}


SENSITIVITY_KB = _strip_docs(_load_required(KB_PATH, "sensitivity KB"))
print(f"[MATCHER] Loaded sensitivity KB: {len(SENSITIVITY_KB)} conditions")

INGREDIENT_SYNONYMS = _strip_docs(_load_required(SYNONYMS_PATH, "ingredient synonyms"))
INGREDIENT_RULES = _load_required(RULES_PATH, "ingredient matching rules")

# Build reverse lookup: variant → canonical
VARIANT_TO_CANONICAL = {}
for canonical, variants in INGREDIENT_SYNONYMS.items():
    VARIANT_TO_CANONICAL[canonical.lower()] = canonical
    for variant in variants:
        VARIANT_TO_CANONICAL[variant.lower()] = canonical

# Hidden forms are label terms that ARE an allergen but share no obvious word
# with it ("semolina" is wheat). They behave exactly like synonyms.
for canonical, forms in INGREDIENT_RULES.get("hidden_forms", {}).items():
    # Skip the _note keys that document this file. Without this guard a
    # string value would be iterated character by character, mapping single
    # letters to a canonical allergen.
    if canonical.startswith("_") or not isinstance(forms, list):
        continue
    VARIANT_TO_CANONICAL.setdefault(canonical.lower(), canonical)
    for form in forms:
        VARIANT_TO_CANONICAL[form.lower()] = canonical

# Every ingredient named by the KB must itself be matchable, even if no
# synonym entry mentions it.
for _entry in SENSITIVITY_KB.values():
    for _ing in _entry.get("ingredients", []):
        VARIANT_TO_CANONICAL.setdefault(_ing.lower(), _ing)

FALSE_FRIENDS = {
    k.lower(): {t.lower() for t in v}
    for k, v in INGREDIENT_RULES.get("false_friends", {}).items()
    if not k.startswith("_")
}
AMBIGUOUS = {
    k.lower(): v
    for k, v in INGREDIENT_RULES.get("ambiguous", {}).items()
    if not k.startswith("_")
}

print(
    f"[MATCHER] Loaded {len(VARIANT_TO_CANONICAL)} ingredient terms, "
    f"{len(FALSE_FRIENDS)} false-friend guards, {len(AMBIGUOUS)} ambiguous forms"
)


class VerdictEnum(str, Enum):
    """
    What Pona found — described, not judged.

    These deliberately do NOT say "safe" or "unsafe". Pona checks one thing:
    whether a food contains something on YOUR profile. It has no opinion on
    whether a food is healthy, and saying "safe to eat" would claim far more
    than we checked — we looked at your listed conditions and nothing else.

    So the states name the finding instead of rating the food.
    """
    NO_TRIGGERS = "no_triggers_found"
    POSSIBLE_TRIGGERS = "possible_triggers"
    CONTAINS_TRIGGER = "contains_trigger"


VERDICT_LABELS = {
    VerdictEnum.NO_TRIGGERS: "No triggers found",
    VerdictEnum.POSSIBLE_TRIGGERS: "Contains possible triggers",
    VerdictEnum.CONTAINS_TRIGGER: "Contains something you listed",
}


# ── Step 1: Label parsing + Ingredient Normalization ───────────────────────────

# NOTE: there is deliberately no stop-word list here.
#
# An earlier version stripped "noise" words ("fat", "free", "enriched", ...)
# from both the phrase and the KB terms. That silently corrupted the terms:
# the dairy synonym "milk fat" -> butter collapsed to the single token
# ["milk"], so ANY phrase containing the word milk matched canonical
# "butter" — which meant "coconut milk" was reported as dairy, sailing past
# the false-friend guard that only blocked "milk".
#
# Stop-words are unnecessary anyway: _contains_term looks for a contiguous
# run of tokens, so surrounding words are harmless. "roasted peanuts"
# contains ["peanut"] without any stripping. Keep it literal.

_SPLIT_RE = re.compile(r"[,;()\[\]•\n\.]+|\band\b|\bor\b")
_CLEAN_RE = re.compile(r"[^a-z0-9\s\-']")
_WS_RE = re.compile(r"\s+")


def parse_ingredient_list(raw: str) -> List[str]:
    """
    Split one raw label string into individual ingredient phrases.

    Real labels are not clean lists. They look like:
      "MILK CHOCOLATE (SUGAR, COCOA BUTTER, MILK, SOY LECITHIN), PEANUTS"

    We flatten parentheses rather than treating them as sub-structure,
    because for allergen purposes a nested ingredient is just as present
    as a top-level one.
    """
    parts = _SPLIT_RE.split(raw.lower())
    out = []
    for p in parts:
        p = _CLEAN_RE.sub(" ", p)
        p = _WS_RE.sub(" ", p).strip(" -'")
        if p:
            out.append(p)
    return out


# Precautionary allergen labelling. "May contain peanuts" is a statement
# about cross-contamination risk, not an ingredient list — the peanut may
# not be in the product at all. Reporting it as a confirmed ingredient
# overstates what the label says.
#
# It still matters, especially for a severe allergy, so it is surfaced —
# just as "possible" rather than "confirmed", which is exactly the
# distinction the label itself is drawing.
_PRECAUTIONARY_RE = re.compile(
    r"\b("
    r"may\s+(also\s+)?contain(\s+traces?\s+(of\s+)?)?"
    r"|(may\s+contain\s+)?traces?\s+of"
    r"|produced\s+in\s+a\s+facility"
    r"|manufactured\s+in\s+a\s+facility"
    r"|made\s+in\s+a\s+facility"
    r"|processed\s+in\s+a\s+facility"
    r"|packed\s+in\s+a\s+facility"
    r"|(manufactured|made|processed)\s+on\s+(shared\s+)?equipment"
    r"|shared\s+equipment"
    r")\b",
    re.IGNORECASE,
)


def split_precautionary(raw: str) -> Tuple[str, str]:
    """
    Separate the ingredient list from any "may contain" statement.

    Returns (definite_text, precautionary_text). Everything from the first
    precautionary marker onward is treated as precautionary, which matches
    how these statements are written — they come after the ingredients and
    run to the end.
    """
    m = _PRECAUTIONARY_RE.search(raw)
    if not m:
        return raw, ""
    return raw[:m.start()], raw[m.end():]


def _singular(word: str) -> str:
    """Crude de-pluralisation. 'peanuts' -> 'peanut', but leaves 'molasses'."""
    if len(word) > 3 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("es") and not word.endswith(("ses", "ses")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _tokens(phrase: str) -> List[str]:
    """Words of a phrase, de-pluralised. No words are dropped — see note above."""
    return [_singular(w) for w in phrase.split() if w]


def _contains_term(phrase_tokens: List[str], term_tokens: List[str]) -> bool:
    """True if term_tokens appear as a contiguous run inside phrase_tokens."""
    n, m = len(phrase_tokens), len(term_tokens)
    if m == 0 or m > n:
        return False
    return any(phrase_tokens[i:i + m] == term_tokens for i in range(n - m + 1))


# Pre-tokenise every known term once, longest first so that a specific term
# ("peanut butter") is preferred over a generic one ("butter").
_TERM_TOKENS = sorted(
    ((term, _tokens(term), canonical) for term, canonical in VARIANT_TO_CANONICAL.items()),
    key=lambda t: -len(t[1]),
)


def normalize_ingredient(raw_ingredient: str) -> List[str]:
    """
    Resolve one ingredient phrase to every canonical term it contains.

    Returns a LIST, because one label phrase can carry several allergens:
      "milk chocolate"     -> ["milk", "chocolate"]
      "sodium caseinate"   -> ["casein"]
      "roasted peanuts"    -> ["peanuts"]
      "cocoa butter"       -> []          (false-friend guard: not dairy)
      "xyzabc123"          -> ["xyzabc123"]  (unknown, passed through as-is)

    Strategy, in order:
      1. Exact lookup (fast path, and the most trustworthy signal)
      2. Token-containment against every known term, word-boundary aware
      3. False-friend guard removes matches we know to be wrong

    Word-boundary matching is what keeps this honest. Plain substring
    matching would flag "cocoa butter" as dairy because "butter" appears
    in it — a false positive on a vegan product. Matching whole tokens
    plus an explicit exclusion list avoids that.
    """
    phrase = _WS_RE.sub(" ", _CLEAN_RE.sub(" ", raw_ingredient.lower())).strip()
    if not phrase:
        return []

    # 1. Exact match wins outright.
    if phrase in VARIANT_TO_CANONICAL:
        return [VARIANT_TO_CANONICAL[phrase]]

    blocked = FALSE_FRIENDS.get(phrase, set())
    phrase_tokens = _tokens(phrase)

    # 2. Token containment.
    found: List[str] = []
    for _term, term_tokens, canonical in _TERM_TOKENS:
        if canonical.lower() in blocked or canonical in found:
            continue
        if _contains_term(phrase_tokens, term_tokens):
            found.append(canonical)

    # 3. Nothing recognised — surface the raw phrase so the user can see
    #    exactly what we read and judge for themselves.
    return found or [phrase]


def normalize_ingredients(raw_ingredients: List[str]) -> List[str]:
    """
    Parse and normalise a list of raw label strings.

    Each input may itself be a whole label ("SUGAR, COCOA BUTTER, MILK"),
    so this both splits and normalises, returning a flat de-duplicated list.
    """
    out: List[str] = []
    for raw in raw_ingredients:
        for phrase in parse_ingredient_list(raw):
            for canonical in normalize_ingredient(phrase):
                if canonical not in out:
                    out.append(canonical)
    return out


def find_ambiguous(raw_ingredients: List[str]) -> List[Dict]:
    """
    Detect ingredients that MAY hide an allergen without declaring it.

    "Natural flavors" can legally be dairy-derived. We cannot confirm it
    and we cannot rule it out, so we surface it rather than guessing in
    either direction.
    """
    hits = []
    seen = set()
    for raw in raw_ingredients:
        for phrase in parse_ingredient_list(raw):
            # A qualified compound overrules the generic term inside it.
            # "rice flour" is explicitly gluten-free, so the ambiguity of
            # bare "flour" must not be raised against it.
            blocked = FALSE_FRIENDS.get(phrase, set())

            entry, label = AMBIGUOUS.get(phrase), phrase
            if entry is None:
                # Also catch it inside a longer phrase, e.g. "contains natural flavors"
                p_tokens = _tokens(phrase)
                for amb_phrase, amb_entry in AMBIGUOUS.items():
                    if _contains_term(p_tokens, _tokens(amb_phrase)):
                        entry, label = amb_entry, amb_phrase
                        break
            if entry is None or label in seen:
                continue

            may_contain = [
                c for c in entry.get("may_contain", []) if c.lower() not in blocked
            ]
            if not may_contain:
                continue

            seen.add(label)
            hits.append({
                "phrase": label,
                "may_contain": may_contain,
                "note": entry.get("note", ""),
            })
    return hits


# ── Step 2: Sensitivity Matching ───────────────────────────────────────────────

class Trigger:
    """Represents one ingredient that triggers a sensitivity."""

    def __init__(
        self,
        ingredient: str,
        sensitivity: str,
        explanation: str,
        severity: str,
        confidence: str = "confirmed",
    ):
        self.ingredient = ingredient
        self.sensitivity = sensitivity
        self.explanation = explanation
        self.severity = severity
        # "confirmed" — the ingredient is definitely present.
        # "possible"  — the label uses a term that MAY hide this allergen
        #               (e.g. "natural flavors"). Never escalated to UNSAFE,
        #               because we would be guessing.
        self.confidence = confidence

    def to_dict(self) -> Dict:
        return {
            "ingredient": self.ingredient,
            "sensitivity": self.sensitivity,
            "explanation": self.explanation,
            "severity": self.severity,
            "confidence": self.confidence,
        }

    def __repr__(self):
        return f"<Trigger {self.ingredient} -> {self.sensitivity}>"


def match_personal_triggers(
    normalized_ingredients: List[str],
    raw_ingredients: List[str],
    personal_triggers: List[Dict],
) -> List[Trigger]:
    """
    Match against triggers the USER told us about.

    This is the mechanism that lets Pona cover conditions where the food
    triggers genuinely differ between people (reflux is the clearest case).
    Rather than asserting a universal trigger list — which would be
    inventing information and would push people to avoid foods that are
    fine for them — Pona watches for what each person actually reacts to.

    personal_triggers: [{"ingredient": "coffee", "condition": "Acid reflux / GERD"}]
    """
    triggers = []
    phrases = {p for raw in raw_ingredients for p in parse_ingredient_list(raw)}

    for pt in personal_triggers:
        term = (pt.get("ingredient") or "").strip().lower()
        if not term:
            continue
        condition = pt.get("condition") or "Your own list"

        canonical = normalize_ingredient(term)
        hit = any(c in normalized_ingredients for c in canonical)
        if not hit:
            term_tokens = _tokens(term)
            hit = any(_contains_term(_tokens(p), term_tokens) for p in phrases)

        if hit:
            triggers.append(Trigger(
                ingredient=term,
                sensitivity=condition,
                explanation="You added this to your own trigger list.",
                severity="personal",
                confidence="confirmed",
            ))
    return triggers


def match_ingredients_to_sensitivities(
    normalized_ingredients: List[str],
    user_sensitivities: List[str]
) -> Tuple[List[Trigger], List[str]]:
    """
    Core matching algorithm.

    Input:
      normalized_ingredients: ["dairy", "gluten", "tomato"]
      user_sensitivities: ["Lactose intolerance", "GERD"]

    Output: (triggers, unchecked)
      triggers = [
        Trigger("dairy", "Lactose intolerance", "Contains lactose...", "medium"),
        Trigger("tomato", "GERD", "Contains citric acid...", "medium"),
      ]
      unchecked = ["Some condition we have no KB entry for"]

    `unchecked` matters: a restriction we could not evaluate must never be
    reported as cleared. The caller is responsible for surfacing it.

    Algorithm:
      for each user_sensitivity in user_sensitivities:
          kb_entry = SENSITIVITY_KB[user_sensitivity]
          for each ingredient in normalized_ingredients:
              if ingredient in kb_entry['ingredients']:
                  create Trigger
                  add to results

    Why this order? (sensitivities outer loop, ingredients inner)
    - More intuitive: "For each of my restrictions, what in this food triggers it?"
    - Easier to explain: "This dairy content triggers YOUR lactose intolerance"
    """
    triggers = []
    unchecked = []

    for sensitivity in user_sensitivities:
        if sensitivity not in SENSITIVITY_KB:
            # We cannot evaluate this restriction. Record it — do NOT silently
            # skip it, or the user would be told "safe" for a condition we
            # never actually checked.
            unchecked.append(sensitivity)
            continue

        kb_entry = SENSITIVITY_KB[sensitivity]

        for ingredient in normalized_ingredients:
            # Check if this ingredient triggers this sensitivity
            if ingredient in kb_entry.get("ingredients", []):
                trigger = Trigger(
                    ingredient=ingredient,
                    sensitivity=sensitivity,
                    explanation=kb_entry.get("explanation", "Unknown trigger"),
                    severity=kb_entry.get("severity", "unknown"),
                )
                triggers.append(trigger)

    return triggers, unchecked


# ── Step 3: Verdict Determination ──────────────────────────────────────────────

def determine_verdict(
    triggers: List[Trigger],
    unchecked: Optional[List[str]] = None,
    needs_setup: Optional[List[str]] = None,
) -> VerdictEnum:
    """
    Decide which of the three findings applies.

    1. A CONFIRMED trigger present        → CONTAINS_TRIGGER
    2. Only POSSIBLE triggers             → POSSIBLE_TRIGGERS
    3. Nothing found, but something we
       could not actually check           → POSSIBLE_TRIGGERS
    4. Nothing found, everything checked  → NO_TRIGGERS

    Cases 3 is deliberate. "No triggers found" must mean "we checked
    everything on your profile and found nothing", never "we checked some
    of it". Two ways that can fail, and both downgrade the result:
      - `unchecked`   : a condition with no entry in our knowledge base.
      - `needs_setup` : a user-defined condition (reflux) where the person
                        has not yet added any triggers, so there was
                        literally nothing to look for.

    Note what this function does NOT do: it never rates the food. A
    confirmed peanut in a peanut allergy profile reports "contains
    something you listed" — the significance of that is the user's to
    judge, with the severity and explanation we hand them.
    """
    if any(t.confidence == "confirmed" for t in triggers):
        return VerdictEnum.CONTAINS_TRIGGER

    if triggers or unchecked or needs_setup:
        return VerdictEnum.POSSIBLE_TRIGGERS

    return VerdictEnum.NO_TRIGGERS


# ── Step 4: Plain English Explanation ──────────────────────────────────────────

def explain_verdict(
    triggers: List[Trigger],
    verdict: VerdictEnum,
    unchecked: Optional[List[str]] = None,
    needs_setup: Optional[List[str]] = None,
) -> str:
    """
    State the finding in plain English.

    Voice rules, in priority order:

    1. Describe, never evaluate. Say what is in the food and which of the
       user's conditions it relates to. Never call a food good, bad,
       healthy, unhealthy, or "safe to eat" — Pona checked a profile, not
       a diet, and has no basis for a verdict on the food itself.
    2. Be exact about coverage. If something could not be checked, say so
       in the same breath, so a short result is never mistaken for a
       clean bill of health.
    3. Calm and specific over urgent and vague. The user decides what to
       do; our job is to hand them the fact and the reason.
    """
    unchecked = unchecked or []
    needs_setup = needs_setup or []

    caveats = []
    if unchecked:
        caveats.append(
            f"We could not check {', '.join(unchecked)} - "
            f"it isn't in our database yet, so this result does not cover it."
        )
    if needs_setup:
        caveats.append(
            f"You haven't added any triggers for {', '.join(needs_setup)} yet, "
            f"so there was nothing to look for. Triggers for it vary a lot "
            f"between people - add the ones you react to and Pona will watch "
            f"for them."
        )
    caveat = ("\n\nNote: " + " ".join(caveats)) if caveats else ""

    if not triggers:
        if caveats:
            return "No triggers found for the conditions we could check." + caveat
        return "No triggers found for anything on your profile."

    confirmed = [t for t in triggers if t.confidence == "confirmed"]
    possible = [t for t in triggers if t.confidence == "possible"]

    if len(triggers) == 1:
        t = triggers[0]
        if t.confidence == "possible":
            lead = f"Contains {t.ingredient}, which can sometimes hide something related to your {t.sensitivity}."
        else:
            lead = f"Contains {t.ingredient}, which is on your list for {t.sensitivity}."
        return f"{lead} {t.explanation}".strip() + caveat

    lines = []
    for t in confirmed:
        lines.append(f"• {t.sensitivity}: contains {t.ingredient}. {t.explanation}")
    for t in possible:
        lines.append(f"• {t.sensitivity} (possible): '{t.ingredient}' - {t.explanation}")

    header = "Found on your profile:" if confirmed else "Possible, not certain:"
    return header + "\n" + "\n".join(lines) + caveat


# ── Main Entry Point ───────────────────────────────────────────────────────────

def get_verdict(
    raw_ingredients: List[str],
    user_sensitivities: List[str],
    personal_triggers: Optional[List[Dict]] = None,
) -> Dict:
    """
    End-to-end matching pipeline.

    Input:
      raw_ingredients:    ["milk", "sodium caseinate", "tomato"]
      user_sensitivities: ["Lactose intolerance", "Acid reflux / GERD"]
      personal_triggers:  [{"ingredient": "coffee", "condition": "Acid reflux / GERD"}]

    Output:
      {
        "verdict": "contains_trigger",
        "verdict_label": "Contains something you listed",
        "triggers": [...],
        "explanation": "...",
        "normalized_ingredients": [...],
        "unchecked_sensitivities": [],
        "conditions_needing_setup": [],
      }

    Pipeline:
      1. Parse and normalise the label
      2. Match against knowledge-base conditions
      3. Match against the user's own trigger list
      4. Flag ingredients that may hide an allergen
      5. Note anything we could not actually check
      6. Describe the finding

    This is pure logic — no I/O, no randomness, no model. Every result is
    traceable to a rule, which is what makes it auditable and explainable.
    """
    personal_triggers = personal_triggers or []

    # Step 1: Split "may contain" statements off the ingredient list, then
    # normalise each part. A precautionary allergen is reported, but as a
    # possibility rather than as an ingredient that is definitely present.
    definite_raw, precaution_raw = [], []
    for raw in raw_ingredients:
        d, p = split_precautionary(raw)
        if d.strip():
            definite_raw.append(d)
        if p.strip():
            precaution_raw.append(p)

    normalized_ingredients = normalize_ingredients(definite_raw)
    precautionary_ingredients = [
        i for i in normalize_ingredients(precaution_raw)
        if i not in normalized_ingredients
    ]

    # Step 2: Match
    triggers, unchecked = match_ingredients_to_sensitivities(
        normalized_ingredients, user_sensitivities
    )

    # Step 2a: Precautionary allergens -> possible, never confirmed.
    precaution_triggers, _ = match_ingredients_to_sensitivities(
        precautionary_ingredients, user_sensitivities
    )
    for t in precaution_triggers:
        t.confidence = "possible"
        t.explanation = (
            f"The label says this may contain {t.ingredient} through shared "
            f"equipment or facilities. It is a cross-contamination warning, "
            f"not a listed ingredient."
        )
    triggers.extend(precaution_triggers)

    # Step 2a: The user's own trigger list.
    triggers.extend(match_personal_triggers(
        normalized_ingredients, raw_ingredients, personal_triggers
    ))

    # Step 2b: Ingredients that MAY hide an allergen without declaring it.
    # Only raised for conditions the user actually has, so we don't spam
    # everyone with every caveat.
    for amb in find_ambiguous(raw_ingredients):
        for sensitivity in user_sensitivities:
            kb_entry = SENSITIVITY_KB.get(sensitivity)
            if not kb_entry:
                continue
            relevant = set(kb_entry.get("ingredients", [])) & set(amb["may_contain"])
            if not relevant:
                continue
            if any(
                t.ingredient == amb["phrase"] and t.sensitivity == sensitivity
                for t in triggers
            ):
                continue
            triggers.append(Trigger(
                ingredient=amb["phrase"],
                sensitivity=sensitivity,
                explanation=amb["note"],
                severity=kb_entry.get("severity", "unknown"),
                confidence="possible",
            ))

    # Step 2c: Conditions where triggers are personal and none are set yet.
    # Without this, someone who selected reflux and added nothing would be
    # told "no triggers found" when in fact we looked for nothing at all.
    conditions_with_personal = {
        (pt.get("condition") or "") for pt in personal_triggers if pt.get("ingredient")
    }
    needs_setup = [
        s for s in user_sensitivities
        if SENSITIVITY_KB.get(s, {}).get("user_defined")
        and s not in conditions_with_personal
    ]

    # Step 3: Verdict
    verdict = determine_verdict(triggers, unchecked, needs_setup)

    # Step 4: Explanation
    explanation = explain_verdict(triggers, verdict, unchecked, needs_setup)

    return {
        "verdict": verdict.value,
        "verdict_label": VERDICT_LABELS[verdict],
        "triggers": [t.to_dict() for t in triggers],
        "explanation": explanation,
        "normalized_ingredients": normalized_ingredients,
        "unchecked_sensitivities": unchecked,
        "conditions_needing_setup": needs_setup,
    }


# Tests live in backend/test_matcher.py (matching logic) and
# backend/test_api.py (database + HTTP integration).
