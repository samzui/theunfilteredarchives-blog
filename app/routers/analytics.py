from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AnalyticsEvent
from app.security import current_user


router = APIRouter()


# =========================================================
# TRACK WRITING VIEW
# =========================================================

@router.post("/view/{writing_id}")
def track_view(
    writing_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Record a writing view.

    Anonymous visitors receive a visitor_key.
    Logged-in users can also be associated with their user ID
    when the frontend sends it later.
    """

    visitor_key = (
        request.headers.get("X-Visitor-Key")
        or str(uuid4())
    )

    event = AnalyticsEvent(
        visitor_key=visitor_key,
        user_id=None,
        writing_id=writing_id,
        event_type="VIEW",
    )

    db.add(event)
    db.commit()

    return {
        "message": "View tracked",
        "visitor_key": visitor_key,
    }