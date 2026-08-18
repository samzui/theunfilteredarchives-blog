from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import Comment, Writing, Notification, User
from app.schemas.common import CommentIn, CommentOut
from app.security import current_user, admin_user


router = APIRouter()


# =========================================================
# GET COMMENTS
# =========================================================

@router.get(
    "/writings/{writing_id}/comments",
    response_model=list[CommentOut]
)
def list_comments(
    writing_id: int,
    db: Session = Depends(get_db)
):
    rows = db.execute(
        select(Comment, User)
        .join(
            User,
            User.id == Comment.author_id
        )
        .where(
            Comment.writing_id == writing_id,
            Comment.status == "VISIBLE"
        )
        .order_by(
            Comment.created_at.asc()
        )
    ).all()

    return [
        CommentOut(
            id=comment.id,
            content=comment.content,
            status=comment.status,
            author_id=comment.author_id,
            author_name=user.display_name,
            writing_id=comment.writing_id,
            parent_id=comment.parent_id,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
        )
        for comment, user in rows
    ]


# =========================================================
# CREATE COMMENT / REPLY
# =========================================================

@router.post(
    "/writings/{writing_id}/comments",
    response_model=CommentOut
)
def create_comment(
    writing_id: int,
    d: CommentIn,
    db: Session = Depends(get_db),
    u=Depends(current_user)
):
    # Check writing
    writing = db.get(
        Writing,
        writing_id
    )

    if not writing:
        raise HTTPException(
            status_code=404,
            detail="Writing not found"
        )

    # Check parent comment when replying
    parent = None

    if d.parent_id is not None:
        parent = db.get(
            Comment,
            d.parent_id
        )

        if not parent:
            raise HTTPException(
                status_code=404,
                detail="Parent comment not found"
            )

        # Make sure the parent belongs to
        # the same writing.
        if parent.writing_id != writing_id:
            raise HTTPException(
                status_code=400,
                detail="Parent comment belongs to another writing"
            )

    # Create comment
    comment = Comment(
        content=d.content,
        author_id=u.id,
        writing_id=writing_id,
        parent_id=d.parent_id
    )

    db.add(comment)
    db.flush()

    # -----------------------------------------------------
    # REPLY NOTIFICATION
    # -----------------------------------------------------

    if parent is not None:

        # Don't notify yourself
        if parent.author_id != u.id:

            db.add(
                Notification(
                    user_id=parent.author_id,
                    actor_id=u.id,
                    type="REPLY",
                    message=(
                        f"{u.display_name} replied "
                        f"to your comment"
                    ),
                    comment_id=comment.id,
                    writing_id=writing_id
                )
            )

    db.commit()
    db.refresh(comment)

    return CommentOut(
        id=comment.id,
        content=comment.content,
        status=comment.status,
        author_id=comment.author_id,
        author_name=u.display_name,
        writing_id=comment.writing_id,
        parent_id=comment.parent_id,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


# =========================================================
# EDIT COMMENT
# =========================================================

@router.put(
    "/comments/{comment_id}",
    response_model=CommentOut
)
def edit_comment(
    comment_id: int,
    d: CommentIn,
    db: Session = Depends(get_db),
    u=Depends(current_user)
):
    comment = db.get(
        Comment,
        comment_id
    )

    if not comment:
        raise HTTPException(
            status_code=404,
            detail="Comment not found"
        )

    # Only owner or admin can edit
    if (
        comment.author_id != u.id
        and u.role != "ADMIN"
    ):
        raise HTTPException(
            status_code=403,
            detail="Not allowed"
        )

    # Update content
    comment.content = d.content

    db.commit()
    db.refresh(comment)

    # IMPORTANT:
    # Return author_name because CommentOut requires it.
    author = db.get(
        User,
        comment.author_id
    )

    return CommentOut(
        id=comment.id,
        content=comment.content,
        status=comment.status,
        author_id=comment.author_id,
        author_name=(
            author.display_name
            if author
            else "Unknown User"
        ),
        writing_id=comment.writing_id,
        parent_id=comment.parent_id,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


# =========================================================
# DELETE COMMENT
# =========================================================

@router.delete(
    "/comments/{comment_id}"
)
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    u=Depends(current_user)
):
    comment = db.get(
        Comment,
        comment_id
    )

    if not comment:
        raise HTTPException(
            status_code=404,
            detail="Comment not found"
        )

    # Only owner or admin can delete
    if (
        comment.author_id != u.id
        and u.role != "ADMIN"
    ):
        raise HTTPException(
            status_code=403,
            detail="Not allowed"
        )

    db.delete(comment)
    db.commit()

    return {
        "message": "Comment deleted"
    }