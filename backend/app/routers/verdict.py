"""
Verdict endpoint: Main logic that produces Safe/Caution/Unsafe.

This orchestrates:
1. Load user's sensitivities from database
2. Normalize ingredients (using matcher.py)
3. Match against KB
4. Return verdict + explanation

This is where all the pieces come together.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
from typing import List

from app.database import get_db
from app.models import SensitivityProfile, user_sensitivities_table, Scan
from app.ml.matcher import get_verdict as get_verdict_from_matcher

router = APIRouter()


# ── Request/Response schemas ───────────────────────────────────────────────────

class VerdictRequest(BaseModel):
    """Request a verdict for ingredients."""
    profile_id: int
    ingredients: List[str]  # Raw ingredients (may not be normalized yet)


class Trigger(BaseModel):
    """One ingredient triggering a sensitivity."""
    ingredient: str
    sensitivity: str
    explanation: str
    severity: str
    # "confirmed" = ingredient is definitely present.
    # "possible"  = label term may hide this allergen (e.g. "natural flavors").
    confidence: str = "confirmed"


class VerdictResponse(BaseModel):
    """
    What Pona found for this profile.

    Note the vocabulary: no_triggers_found / possible_triggers /
    contains_trigger. Pona reports what a food contains relative to YOUR
    profile. It does not rate the food, and it never says "safe" — that
    would claim far more than was checked.
    """
    verdict: str
    verdict_label: str  # human-readable form of `verdict`
    triggers: List[Trigger]
    explanation: str
    normalized_ingredients: List[str]
    # Conditions on the profile that have no KB entry, so could not be
    # evaluated. Non-empty means this result does NOT cover them.
    unchecked_sensitivities: List[str] = []
    # Conditions whose triggers are personal and where the user has not
    # added any yet — so nothing was actually looked for.
    conditions_needing_setup: List[str] = []


# ── Main endpoint ──────────────────────────────────────────────────────────────

@router.post("/", response_model=VerdictResponse)
async def get_verdict(request: VerdictRequest, db: Session = Depends(get_db)):
    """
    Get a verdict for ingredients against a user's profile.

    Steps:
    1. Fetch profile + sensitivities from database
    2. Call matcher engine (pure logic, no DB)
    3. Save scan record (audit trail)
    4. Return verdict

    RECRUITERS CARE: This is where the system comes together.
    Notice the separation of concerns:
    - Database layer (get user sensitivities)
    - Logic layer (matcher.get_verdict() — pure functions)
    - Persistence layer (save scan record)
    """

    # Step 1: Fetch profile
    profile = db.query(SensitivityProfile).get(request.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Step 1b: Fetch user's sensitivities
    sensitivity_query = select(user_sensitivities_table.c.sensitivity_name).where(
        user_sensitivities_table.c.profile_id == request.profile_id
    )
    sensitivities = db.execute(sensitivity_query).scalars().all()

    if not sensitivities:
        raise HTTPException(
            status_code=400,
            detail="Profile has no sensitivities configured. Add sensitivities first."
        )

    # Step 1c: Fetch the user's own trigger list
    personal_triggers = [
        {"ingredient": t.ingredient, "condition": t.condition}
        for t in profile.personal_triggers
    ]

    # Step 2: Call matching engine (pure logic)
    result = get_verdict_from_matcher(
        raw_ingredients=request.ingredients,
        user_sensitivities=list(sensitivities),
        personal_triggers=personal_triggers,
    )

    # Step 3: Save scan record (audit trail)
    scan = Scan(
        profile_id=request.profile_id,
        input_type="manual",  # Will vary: "photo", "ocr", "url", "manual"
        raw_ingredients=request.ingredients,
        normalized_ingredients=result["normalized_ingredients"],
        verdict=result["verdict"],
        triggers=result["triggers"]
    )
    db.add(scan)
    db.commit()

    # Step 4: Return verdict
    return VerdictResponse(
        verdict=result["verdict"],
        verdict_label=result["verdict_label"],
        triggers=[Trigger(**t) for t in result["triggers"]],
        explanation=result["explanation"],
        normalized_ingredients=result["normalized_ingredients"],
        unchecked_sensitivities=result["unchecked_sensitivities"],
        conditions_needing_setup=result["conditions_needing_setup"],
    )
