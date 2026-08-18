from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import (
    Writing,
    WritingLike,
    Comment,
    CommentLike,
    Bookmark,
    Report,
    User,
    AnalyticsEvent,
)
from app.schemas import ReportIn
from app.security import (
    current_user,
    optional_current_user,
    admin_user,
)


router = APIRouter()

# =========================================================
# RECORD WRITING VIEW
# =========================================================

@router.post("/writings/{writing_id}/view")
def record_writing_view(
    writing_id: int,
    request: Request,
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    """
    Record a view for a writing.

    The visitor_key is taken from the request header.
    Logged-in users are also associated with their user_id.
    """

    writing = db.get(
        Writing,
        writing_id
    )

    if not writing:
        raise HTTPException(
            status_code=404,
            detail="Writing not found",
        )

    visitor_key = request.headers.get(
        "X-Visitor-Key"
    )

    if not visitor_key:
        raise HTTPException(
            status_code=400,
            detail="Visitor key is required",
        )

    db.add(
        AnalyticsEvent(
            visitor_key=visitor_key,
            user_id=u.id if u else None,
            writing_id=writing_id,
            event_type="VIEW",
        )
    )

    db.commit()

    return {
        "message": "View recorded"
    }
# =========================================================
# WRITING LIKE / UNLIKE
# =========================================================

@router.post("/writings/{writing_id}/like")
def like_writing(
    writing_id: int,
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    """
    Toggle like for the currently authenticated user.

    If not liked:
        -> like

    If already liked:
        -> unlike
    """

    writing = db.get(Writing, writing_id)

    if not writing:
        raise HTTPException(
            status_code=404,
            detail="Writing not found",
        )

    existing_like = db.scalar(
        select(WritingLike).where(
            WritingLike.writing_id == writing_id,
            WritingLike.user_id == u.id,
        )
    )

    if existing_like:
        db.delete(existing_like)
        action = "unliked"

    else:
        db.add(
            WritingLike(
                writing_id=writing_id,
                user_id=u.id,
                visitor_key=None,
            )
        )
        action = "liked"

    db.commit()

    likes = db.scalar(
        select(func.count())
        .select_from(WritingLike)
        .where(
            WritingLike.writing_id == writing_id
        )
    ) or 0

    return {
        "action": action,
        "likes": likes,
    }


# =========================================================
# PUBLIC WRITING LIKE COUNT
# =========================================================

@router.get("/writings/{writing_id}/like-count")
def writing_like_count(
    writing_id: int,
    db: Session = Depends(get_db),
):
    """
    Public endpoint.

    Does NOT require authentication.

    Used when a logged-out visitor opens a writing.
    """

    writing = db.get(
        Writing,
        writing_id
    )

    if not writing:
        raise HTTPException(
            status_code=404,
            detail="Writing not found",
        )

    likes = db.scalar(
        select(func.count())
        .select_from(WritingLike)
        .where(
            WritingLike.writing_id == writing_id
        )
    ) or 0

    return {
        "likes": likes
    }


# =========================================================
# WRITING LIKE STATUS
# =========================================================

@router.get("/writings/{writing_id}/like-status")
def writing_like_status(
    writing_id: int,
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    """
    Authenticated endpoint.

    Returns:
        - whether current user liked the writing
        - total like count
    """

    writing = db.get(
        Writing,
        writing_id
    )

    if not writing:
        raise HTTPException(
            status_code=404,
            detail="Writing not found",
        )

    existing_like = db.scalar(
        select(WritingLike).where(
            WritingLike.writing_id == writing_id,
            WritingLike.user_id == u.id,
        )
    )

    likes = db.scalar(
        select(func.count())
        .select_from(WritingLike)
        .where(
            WritingLike.writing_id == writing_id
        )
    ) or 0

    return {
        "liked": existing_like is not None,
        "likes": likes,
    }


# =========================================================
# ADMIN - SEE WHO LIKED A WRITING
# =========================================================

@router.get("/admin/writings/{writing_id}/likes")
def get_writing_likes(
    writing_id: int,
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    """
    Admin-only endpoint.

    Returns the authenticated users who liked a writing.
    """

    writing = db.get(
        Writing,
        writing_id
    )

    if not writing:
        raise HTTPException(
            status_code=404,
            detail="Writing not found",
        )

    rows = db.execute(
        select(
            WritingLike,
            User
        )
        .join(
            User,
            User.id == WritingLike.user_id
        )
        .where(
            WritingLike.writing_id == writing_id,
            WritingLike.user_id.is_not(None),
        )
        .order_by(
            WritingLike.created_at.desc()
        )
    ).all()

    return [
        {
            "id": like.id,
            "user_id": user.id,
            "display_name": user.display_name,
            "created_at": like.created_at,
        }
        for like, user in rows
    ]


# =========================================================
# COMMENT LIKE / UNLIKE
# =========================================================

@router.post("/comments/{comment_id}/like")
def like_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    comment = db.get(
        Comment,
        comment_id
    )

    if not comment:
        raise HTTPException(
            status_code=404,
            detail="Comment not found",
        )

    existing_like = db.scalar(
        select(CommentLike).where(
            CommentLike.comment_id == comment_id,
            CommentLike.user_id == u.id,
        )
    )

    if existing_like:
        db.delete(existing_like)
        action = "unliked"

    else:
        db.add(
            CommentLike(
                comment_id=comment_id,
                user_id=u.id,
            )
        )
        action = "liked"

    db.commit()

    likes = db.scalar(
        select(func.count())
        .select_from(CommentLike)
        .where(
            CommentLike.comment_id == comment_id
        )
    ) or 0

    return {
        "action": action,
        "likes": likes,
    }


# =========================================================
# BOOKMARK / REMOVE BOOKMARK
# =========================================================

@router.post("/writings/{writing_id}/bookmark")
def bookmark(
    writing_id: int,
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    writing = db.get(
        Writing,
        writing_id
    )

    if not writing:
        raise HTTPException(
            status_code=404,
            detail="Writing not found",
        )

    existing_bookmark = db.scalar(
        select(Bookmark).where(
            Bookmark.writing_id == writing_id,
            Bookmark.user_id == u.id,
        )
    )

    if existing_bookmark:
        db.delete(existing_bookmark)
        action = "removed"

    else:
        db.add(
            Bookmark(
                writing_id=writing_id,
                user_id=u.id,
            )
        )
        action = "saved"

    db.commit()

    return {
        "action": action
    }


# =========================================================
# GET USER BOOKMARKS
# =========================================================

@router.get("/bookmarks")
def bookmarks(
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    return list(
        db.scalars(
            select(Bookmark)
            .where(
                Bookmark.user_id == u.id
            )
            .order_by(
                Bookmark.created_at.desc()
            )
        ).all()
    )


# =========================================================
# REPORT COMMENT
# =========================================================

@router.post("/comments/{comment_id}/report")
def report(
    comment_id: int,
    d: ReportIn,
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    comment = db.get(
        Comment,
        comment_id
    )

    if not comment:
        raise HTTPException(
            status_code=404,
            detail="Comment not found",
        )

    db.add(
        Report(
            comment_id=comment_id,
            reporter_id=u.id,
            reason=d.reason,
        )
    )

    db.commit()

    return {
        "message": "Report submitted"
    }