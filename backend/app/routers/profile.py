"""
Profile management endpoints.

Handles:
- Creating user accounts + sensitivity profiles
- Fetching user's sensitivities
- Updating profile

Database model: User -> SensitivityProfile -> user_sensitivities (many-to-many)
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, insert, delete
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.ml.chef_card import build_chef_card
from app.models import (
    User,
    SensitivityProfile,
    PersonalTrigger,
    user_sensitivities_table,
)

router = APIRouter()


# ── Request/Response schemas ───────────────────────────────────────────────────

class PersonalTriggerIn(BaseModel):
    """A food the user says they react to."""
    ingredient: str
    condition: Optional[str] = None


class ProfileCreate(BaseModel):
    """Create a new sensitivity profile."""
    user_email: str
    profile_name: str = "My Profile"
    sensitivities: List[str]  # ["Lactose intolerance", "Acid reflux / GERD", ...]
    # Foods this person reports reacting to. Required for conditions where
    # triggers are individual (reflux), optional for everything else.
    personal_triggers: List[PersonalTriggerIn] = []


class ProfileResponse(BaseModel):
    """Return profile details."""
    profile_id: int
    user_id: str
    profile_name: str
    sensitivities: List[str]
    personal_triggers: List[PersonalTriggerIn] = []


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/", response_model=ProfileResponse, status_code=201)
async def create_profile(body: ProfileCreate, db: Session = Depends(get_db)):
    """
    Create a new sensitivity profile.

    Steps:
    1. Create or fetch user by email
    2. Create profile linked to user
    3. Link sensitivities via many-to-many table
    """
    # Step 1: Get or create user
    user = db.query(User).filter(User.email == body.user_email).first()
    if not user:
        user = User(email=body.user_email)
        db.add(user)
        db.flush()

    # Step 2: Create profile
    profile = SensitivityProfile(
        user_id=user.id,
        profile_name=body.profile_name
    )
    db.add(profile)
    db.flush()

    # Step 3: Link sensitivities via many-to-many table
    for sensitivity in body.sensitivities:
        db.execute(
            insert(user_sensitivities_table).values(
                profile_id=profile.id,
                sensitivity_name=sensitivity
            )
        )

    # Step 4: Record the user's own trigger list
    for pt in body.personal_triggers:
        db.add(PersonalTrigger(
            profile_id=profile.id,
            ingredient=pt.ingredient,
            condition=pt.condition,
        ))

    db.commit()
    db.refresh(profile)

    return ProfileResponse(
        profile_id=profile.id,
        user_id=user.id,
        profile_name=profile.profile_name,
        sensitivities=body.sensitivities,
        personal_triggers=body.personal_triggers,
    )


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: int, db: Session = Depends(get_db)):
    """
    Get profile details including sensitivities.
    """
    profile = db.query(SensitivityProfile).get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Query sensitivities from many-to-many table
    sensitivity_query = select(user_sensitivities_table.c.sensitivity_name).where(
        user_sensitivities_table.c.profile_id == profile_id
    )
    sensitivities = db.execute(sensitivity_query).scalars().all()

    return ProfileResponse(
        profile_id=profile.id,
        user_id=profile.user_id,
        profile_name=profile.profile_name,
        sensitivities=sensitivities,
        personal_triggers=[
            PersonalTriggerIn(ingredient=t.ingredient, condition=t.condition)
            for t in profile.personal_triggers
        ],
    )


@router.put("/{profile_id}", response_model=ProfileResponse)
async def update_profile(profile_id: int, body: ProfileCreate, db: Session = Depends(get_db)):
    """
    Update profile sensitivities.
    """
    profile = db.query(SensitivityProfile).get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Delete old sensitivities
    db.execute(
        delete(user_sensitivities_table).where(
            user_sensitivities_table.c.profile_id == profile_id
        )
    )

    # Insert new sensitivities
    for sensitivity in body.sensitivities:
        db.execute(
            insert(user_sensitivities_table).values(
                profile_id=profile_id,
                sensitivity_name=sensitivity
            )
        )

    # Replace the personal trigger list too
    db.query(PersonalTrigger).filter(
        PersonalTrigger.profile_id == profile_id
    ).delete(synchronize_session=False)
    for pt in body.personal_triggers:
        db.add(PersonalTrigger(
            profile_id=profile_id,
            ingredient=pt.ingredient,
            condition=pt.condition,
        ))

    profile.profile_name = body.profile_name
    db.commit()
    db.refresh(profile)

    return ProfileResponse(
        profile_id=profile.id,
        user_id=profile.user_id,
        profile_name=profile.profile_name,
        sensitivities=body.sensitivities,
        personal_triggers=body.personal_triggers,
    )


@router.get("/{profile_id}/chef-card")
async def chef_card(profile_id: int, db: Session = Depends(get_db)):
    """
    The profile, written for a kitchen.

    Regenerated on request rather than stored, so it can never go stale
    against the profile it describes - including triggers the user adds
    later as they work out what affects them.
    """
    profile = db.query(SensitivityProfile).get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    sensitivities = db.execute(
        select(user_sensitivities_table.c.sensitivity_name).where(
            user_sensitivities_table.c.profile_id == profile_id
        )
    ).scalars().all()

    return build_chef_card(
        conditions=list(sensitivities),
        personal_triggers=[
            {"ingredient": t.ingredient, "condition": t.condition}
            for t in profile.personal_triggers
        ],
        name=profile.profile_name,
    )
