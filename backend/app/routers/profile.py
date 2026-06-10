from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter()


class ProfileCreate(BaseModel):
    user_id: str
    sensitivities: List[str]


class ProfileResponse(BaseModel):
    profile_id: str
    user_id: str
    sensitivities: List[str]


@router.post("/", response_model=ProfileResponse, status_code=201)
async def create_profile(profile: ProfileCreate):
    # TODO: persist to PostgreSQL via SQLAlchemy
    return ProfileResponse(profile_id="", user_id=profile.user_id, sensitivities=profile.sensitivities)


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: str):
    # TODO: fetch from PostgreSQL
    raise HTTPException(status_code=404, detail="Profile not found")


@router.put("/{profile_id}", response_model=ProfileResponse)
async def update_profile(profile_id: str, profile: ProfileCreate):
    # TODO: update in PostgreSQL
    return ProfileResponse(profile_id=profile_id, user_id=profile.user_id, sensitivities=profile.sensitivities)
