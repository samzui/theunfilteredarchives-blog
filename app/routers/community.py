from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    CommunitySubmission,
    Writing,
    Category,
)
from app.security import admin_user
from app.services.utils import slugify


router = APIRouter()


# =========================================================
# REQUEST SCHEMAS
# =========================================================

class CommunityStatusUpdate(BaseModel):
    status: str


# =========================================================
# HELPERS
# =========================================================

def make_unique_slug(title: str, db: Session) -> str:
    base = slugify(title) or "community-writing"
    slug = base
    number = 2

    while db.scalar(
        select(Writing).where(Writing.slug == slug)
    ):
        slug = f"{base}-{number}"
        number += 1

    return slug


def get_or_create_community_category(db: Session):
    category = db.scalar(
        select(Category).where(
            Category.slug == "community"
        )
    )

    if category:
        return category

    category = Category(
        name="Community",
        slug="community",
    )

    db.add(category)
    db.flush()

    return category


# =========================================================
# PUBLIC — SUBMIT COMMUNITY WRITING
# =========================================================

@router.post("/submissions")
def submit_community_writing(
    name: str,
    email: str,
    title: str,
    content: str,
    consent: bool,
    db: Session = Depends(get_db),
):
    if not consent:
        raise HTTPException(
            status_code=400,
            detail="Consent is required to submit your writing.",
        )

    if not name.strip():
        raise HTTPException(
            status_code=400,
            detail="Name is required.",
        )

    if not email.strip():
        raise HTTPException(
            status_code=400,
            detail="Email is required.",
        )

    if not title.strip():
        raise HTTPException(
            status_code=400,
            detail="Title is required.",
        )

    if not content.strip():
        raise HTTPException(
            status_code=400,
            detail="Content is required.",
        )

    now = datetime.now(timezone.utc)

    submission = CommunitySubmission(
        name=name.strip(),
        email=email.strip(),
        title=title.strip(),
        content=content.strip(),
        consent=True,
        status="PENDING",
        created_at=now,
        updated_at=now,
    )

    db.add(submission)
    db.commit()
    db.refresh(submission)

    return {
        "message": "Your piece has been submitted successfully.",
        "id": submission.id,
        "status": submission.status,
    }


# =========================================================
# ADMIN — GET ALL SUBMISSIONS
# =========================================================

@router.get("/admin/submissions")
def get_admin_submissions(
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    return list(
        db.scalars(
            select(CommunitySubmission)
            .order_by(
                CommunitySubmission.created_at.desc()
            )
        ).all()
    )


# =========================================================
# ADMIN — UPDATE APPROVE / REJECT
# =========================================================

@router.patch("/admin/submissions/{submission_id}")
def update_submission_status(
    submission_id: int,
    data: CommunityStatusUpdate,
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    submission = db.get(
        CommunitySubmission,
        submission_id,
    )

    if not submission:
        raise HTTPException(
            status_code=404,
            detail="Community submission not found.",
        )

    if data.status not in (
        "APPROVED",
        "REJECTED",
    ):
        raise HTTPException(
            status_code=400,
            detail="Status must be APPROVED or REJECTED.",
        )

    submission.status = data.status
    submission.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(submission)

    return {
        "message": f"Submission {data.status.lower()}.",
        "id": submission.id,
        "status": submission.status,
    }


# =========================================================
# ADMIN — PUBLISH TO ARCHIVE
# =========================================================

@router.post("/admin/submissions/{submission_id}/publish")
def publish_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    submission = db.get(
        CommunitySubmission,
        submission_id,
    )

    if not submission:
        raise HTTPException(
            status_code=404,
            detail="Community submission not found.",
        )

    if submission.status != "APPROVED":
        raise HTTPException(
            status_code=400,
            detail="Only approved submissions can be published.",
        )

    category = get_or_create_community_category(db)

    slug = make_unique_slug(
        submission.title,
        db,
    )

    now = datetime.now(timezone.utc)

    writing = Writing(
        title=submission.title,
        slug=slug,
        excerpt=submission.content[:300],
        content=submission.content,
        cover_image_url=None,
        status="PUBLISHED",
        featured=False,
        view_count=0,
        category_id=category.id,
        author_id=u.id,
        created_at=now,
        updated_at=now,
        published_at=now,
    )

    db.add(writing)

    submission.status = "PUBLISHED"
    submission.updated_at = now
    submission.reviewed_at = now

    db.commit()
    db.refresh(writing)
    db.refresh(submission)

    return {
        "message": "Submission published successfully.",
        "submission_id": submission.id,
        "writing_id": writing.id,
        "status": submission.status,
    }


# =========================================================
# ADMIN — DELETE SUBMISSION
# =========================================================

@router.delete("/admin/submissions/{submission_id}")
def delete_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    submission = db.get(
        CommunitySubmission,
        submission_id,
    )

    if not submission:
        raise HTTPException(
            status_code=404,
            detail="Community submission not found.",
        )

    db.delete(submission)
    db.commit()

    return {
        "message": "Community submission deleted.",
        "id": submission_id,
    }