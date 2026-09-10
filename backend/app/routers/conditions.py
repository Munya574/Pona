"""
The conditions Pona can check.

Why this endpoint exists rather than a list in the frontend:

The knowledge base is the single source of truth for what Pona can and
cannot check. If the UI carried its own copy, the two would drift — and
the failure mode of that drift is the one this project has already been
bitten by. A condition removed from the KB but still offered in the UI
would let a user select it, see "no triggers found", and believe they
were covered when nothing was ever checked.

Serving the list from the KB makes that impossible by construction.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from app.ml.matcher import SENSITIVITY_KB

router = APIRouter()


class Condition(BaseModel):
    name: str
    severity: str
    explanation: str
    # Extra context worth showing the user: that aged cheese is usually
    # tolerated with lactose intolerance, that certified gluten-free oats
    # exist. Nuance belongs in the UI, not buried in the data.
    note: Optional[str] = None
    # True when Pona holds no trigger list for this condition because
    # triggers are individual. The UI must prompt for the user's own.
    user_defined: bool = False


@router.get("/", response_model=List[Condition])
async def list_conditions():
    """Every condition Pona can check, straight from the knowledge base."""
    return [
        Condition(
            name=name,
            severity=entry.get("severity", "unknown"),
            explanation=entry.get("explanation", ""),
            note=entry.get("note"),
            user_defined=bool(entry.get("user_defined")),
        )
        for name, entry in sorted(SENSITIVITY_KB.items())
    ]
