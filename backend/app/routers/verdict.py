from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Literal

router = APIRouter()


class VerdictRequest(BaseModel):
    ingredients: List[str]
    profile_id: str


class Trigger(BaseModel):
    ingredient: str
    sensitivity: str
    explanation: str


class VerdictResponse(BaseModel):
    verdict: Literal["safe", "caution", "unsafe"]
    triggers: List[Trigger]
    explanation: str


@router.post("/", response_model=VerdictResponse)
async def get_verdict(request: VerdictRequest):
    # TODO: run sensitivity matching engine (matcher.py)
    return VerdictResponse(
        verdict="safe",
        triggers=[],
        explanation="No known triggers found for your profile.",
    )
