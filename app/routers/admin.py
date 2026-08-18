from datetime import datetime, timedelta
import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func, cast, String

from google import genai

from app.database import get_db
from app.models import (
    User,
    Writing,
    Category,
    Comment,
    Report,
    WritingLike,
    Bookmark,
    AnalyticsEvent,
    CommunitySubmission,
)
from app.schemas import StatusIn
from app.security import admin_user
from app.config import settings
from app.services.utils import slugify


router = APIRouter()


# =========================================================
# ADMIN DASHBOARD STATS
# =========================================================

@router.get("/stats")
def stats(
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    # Treat PUBLISHED consistently even if old records contain
    # "published", "Published", or accidental surrounding spaces.
    published_status = func.upper(
        func.trim(
            cast(Writing.status, String)
        )
    ) == "PUBLISHED"

    return {
        "users": db.scalar(
            select(func.count()).select_from(User)
        ) or 0,

        "writings": db.scalar(
            select(func.count()).select_from(Writing)
        ) or 0,

        "published": db.scalar(
            select(func.count())
            .select_from(Writing)
            .where(published_status)
        ) or 0,

        "comments": db.scalar(
            select(func.count()).select_from(Comment)
        ) or 0,

        "reports_open": db.scalar(
            select(func.count())
            .select_from(Report)
            .where(Report.status == "OPEN")
        ) or 0,

        "views": db.scalar(
            select(
                func.coalesce(
                    func.sum(Writing.view_count),
                    0
                )
            ).select_from(Writing)
        ) or 0,
    }

# =========================================================
# ADMIN ANALYTICS
# =========================================================

@router.get("/analytics")
def analytics(
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    """
    Audience and engagement analytics.

    Total actions and unique users are kept separate.

    Engagement rates are based on unique people/visitors,
    rather than the total number of actions.

    This prevents values such as 600% comment rate when
    one person posts multiple comments.
    """

    # -----------------------------------------------------
    # TOTAL VIEWS
    # -----------------------------------------------------

    total_views = db.scalar(
        select(
            func.count(AnalyticsEvent.id)
        )
        .where(
            AnalyticsEvent.event_type == "VIEW"
        )
    ) or 0

    # -----------------------------------------------------
    # UNIQUE VISITORS
    # -----------------------------------------------------

    unique_visitors = db.scalar(
        select(
            func.count(
                func.distinct(
                    AnalyticsEvent.visitor_key
                )
            )
        )
        .where(
            AnalyticsEvent.event_type == "VIEW",
            AnalyticsEvent.visitor_key.is_not(None),
        )
    ) or 0

    # -----------------------------------------------------
    # RETURNING VISITORS
    # -----------------------------------------------------

    returning_visitors = db.scalar(
        select(
            func.count()
        )
        .select_from(
            select(
                AnalyticsEvent.visitor_key
            )
            .where(
                AnalyticsEvent.event_type == "VIEW",
                AnalyticsEvent.visitor_key.is_not(None),
            )
            .group_by(
                AnalyticsEvent.visitor_key
            )
            .having(
                func.count(
                    AnalyticsEvent.id
                ) > 1
            )
            .subquery()
        )
    ) or 0

    # -----------------------------------------------------
    # TOTAL LIKES
    # -----------------------------------------------------

    total_likes = db.scalar(
        select(
            func.count(WritingLike.id)
        )
    ) or 0

    # -----------------------------------------------------
    # UNIQUE LIKERS
    # -----------------------------------------------------

    unique_likers = db.scalar(
        select(
            func.count(
                func.distinct(
                    func.coalesce(
                        cast(
                            WritingLike.user_id,
                            String
                        ),
                        WritingLike.visitor_key
                    )
                )
            )
        )
        .where(
            (
                WritingLike.user_id.is_not(None)
            )
            |
            (
                WritingLike.visitor_key.is_not(None)
            )
        )
    ) or 0

    # -----------------------------------------------------
    # TOTAL COMMENTS
    # -----------------------------------------------------

    total_comments = db.scalar(
        select(
            func.count(Comment.id)
        )
    ) or 0

    # -----------------------------------------------------
    # UNIQUE COMMENTERS
    # -----------------------------------------------------

    unique_commenters = db.scalar(
        select(
            func.count(
                func.distinct(
                    Comment.author_id
                )
            )
        )
    ) or 0

    # -----------------------------------------------------
    # TOTAL BOOKMARKS
    # -----------------------------------------------------

    total_bookmarks = db.scalar(
        select(
            func.count(Bookmark.id)
        )
    ) or 0

    # -----------------------------------------------------
    # UNIQUE SAVERS
    # -----------------------------------------------------

    unique_savers = db.scalar(
        select(
            func.count(
                func.distinct(
                    Bookmark.user_id
                )
            )
        )
    ) or 0

    # =====================================================
    # ENGAGEMENT RATES
    # =====================================================

    if unique_visitors > 0:

        like_rate = (
            unique_likers /
            unique_visitors
        ) * 100

        comment_rate = (
            unique_commenters /
            unique_visitors
        ) * 100

        save_rate = (
            unique_savers /
            unique_visitors
        ) * 100

    else:
        like_rate = 0
        comment_rate = 0
        save_rate = 0

    # Keep rates between 0 and 100.

    like_rate = min(
        round(like_rate, 2),
        100
    )

    comment_rate = min(
        round(comment_rate, 2),
        100
    )

    save_rate = min(
        round(save_rate, 2),
        100
    )

    return {
        "total_views": total_views,
        "unique_visitors": unique_visitors,
        "returning_visitors": returning_visitors,

        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_bookmarks": total_bookmarks,

        "unique_likers": unique_likers,
        "unique_commenters": unique_commenters,
        "unique_savers": unique_savers,

        "like_rate": like_rate,
        "comment_rate": comment_rate,
        "save_rate": save_rate,
    }


# =========================================================
# ADVANCED AUDIENCE ANALYTICS
# =========================================================

@router.get("/audience-analytics")
def audience_analytics(
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    """
    Audience and content analytics.

    Uses real tracked view events and existing engagement tables.
    No demographic or gender information is guessed.
    """

    # =====================================================
    # AUDIENCE OVERVIEW
    # =====================================================

    total_users = db.scalar(
        select(func.count()).select_from(User)
    ) or 0

    active_users = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.is_active.is_(True))
    ) or 0

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    new_users = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.created_at >= thirty_days_ago)
    ) or 0

    # =====================================================
    # VISITOR OVERVIEW
    # =====================================================

    unique_visitors = db.scalar(
        select(
            func.count(
                func.distinct(
                    AnalyticsEvent.visitor_key
                )
            )
        )
        .where(
            AnalyticsEvent.event_type == "VIEW",
            AnalyticsEvent.visitor_key.is_not(None),
        )
    ) or 0

    returning_visitors = db.scalar(
        select(func.count())
        .select_from(
            select(
                AnalyticsEvent.visitor_key
            )
            .where(
                AnalyticsEvent.event_type == "VIEW",
                AnalyticsEvent.visitor_key.is_not(None),
            )
            .group_by(
                AnalyticsEvent.visitor_key
            )
            .having(
                func.count(AnalyticsEvent.id) > 1
            )
            .subquery()
        )
    ) or 0

    total_views = db.scalar(
        select(
            func.count(AnalyticsEvent.id)
        )
        .where(
            AnalyticsEvent.event_type == "VIEW"
        )
    ) or 0

    average_views_per_visitor = (
        round(
            total_views / unique_visitors,
            2
        )
        if unique_visitors > 0
        else 0
    )

    # =====================================================
    # MOST VIEWED WRITING
    # =====================================================

    most_viewed = db.execute(
        select(
            Writing.id,
            Writing.title,
            func.count(AnalyticsEvent.id).label("views")
        )
        .join(
            AnalyticsEvent,
            AnalyticsEvent.writing_id == Writing.id
        )
        .where(
            Writing.status == "PUBLISHED",
            AnalyticsEvent.event_type == "VIEW"
        )
        .group_by(
            Writing.id,
            Writing.title
        )
        .order_by(
            func.count(AnalyticsEvent.id).desc()
        )
        .limit(1)
    ).first()

    most_viewed_writing = (
        {
            "id": most_viewed.id,
            "title": most_viewed.title,
            "views": most_viewed.views or 0,
        }
        if most_viewed
        else None
    )

    # =====================================================
    # MOST LIKED WRITING
    # =====================================================

    most_liked = db.execute(
        select(
            Writing.id,
            Writing.title,
            func.count(WritingLike.id).label("likes")
        )
        .join(
            WritingLike,
            WritingLike.writing_id == Writing.id,
            isouter=True
        )
        .where(
            Writing.status == "PUBLISHED"
        )
        .group_by(
            Writing.id,
            Writing.title
        )
        .order_by(
            func.count(WritingLike.id).desc()
        )
        .limit(1)
    ).first()

    most_liked_writing = (
        {
            "id": most_liked.id,
            "title": most_liked.title,
            "likes": most_liked.likes or 0,
        }
        if most_liked
        else None
    )

    # =====================================================
    # MOST COMMENTED WRITING
    # =====================================================

    most_commented = db.execute(
        select(
            Writing.id,
            Writing.title,
            func.count(Comment.id).label("comments")
        )
        .join(
            Comment,
            Comment.writing_id == Writing.id,
            isouter=True
        )
        .where(
            Writing.status == "PUBLISHED"
        )
        .group_by(
            Writing.id,
            Writing.title
        )
        .order_by(
            func.count(Comment.id).desc()
        )
        .limit(1)
    ).first()

    most_commented_writing = (
        {
            "id": most_commented.id,
            "title": most_commented.title,
            "comments": most_commented.comments or 0,
        }
        if most_commented
        else None
    )

    # =====================================================
    # MOST SAVED WRITING
    # =====================================================

    most_saved = db.execute(
        select(
            Writing.id,
            Writing.title,
            func.count(Bookmark.id).label("bookmarks")
        )
        .join(
            Bookmark,
            Bookmark.writing_id == Writing.id,
            isouter=True
        )
        .where(
            Writing.status == "PUBLISHED"
        )
        .group_by(
            Writing.id,
            Writing.title
        )
        .order_by(
            func.count(Bookmark.id).desc()
        )
        .limit(1)
    ).first()

    most_saved_writing = (
        {
            "id": most_saved.id,
            "title": most_saved.title,
            "bookmarks": most_saved.bookmarks or 0,
        }
        if most_saved
        else None
    )

    # =====================================================
    # AUTOMATIC CONTENT INSIGHTS
    # =====================================================

    insights = []

    if most_viewed_writing:
        insights.append(
            f'"{most_viewed_writing["title"]}" '
            f'is currently your most viewed writing.'
        )

    if most_liked_writing:
        insights.append(
            f'"{most_liked_writing["title"]}" '
            f'has received the most likes.'
        )

    if most_commented_writing:
        insights.append(
            f'"{most_commented_writing["title"]}" '
            f'has generated the most comments.'
        )

    if most_saved_writing:
        insights.append(
            f'"{most_saved_writing["title"]}" '
            f'has been bookmarked the most.'
        )

    # =====================================================
    # FINAL RESPONSE
    # =====================================================

    return {
        "audience": {
            "total_users": total_users,
            "active_users": active_users,
            "new_users": new_users,
            "unique_visitors": unique_visitors,
            "returning_visitors": returning_visitors,
            "total_views": total_views,
            "average_views_per_visitor": average_views_per_visitor,
        },

        "top_content": {
            "most_viewed": most_viewed_writing,
            "most_liked": most_liked_writing,
            "most_commented": most_commented_writing,
            "most_saved": most_saved_writing,
        },

        "insights": insights,
    }


# =========================================================
# WRITING PERFORMANCE REPORTS
# =========================================================

@router.get("/writing-reports")
def writing_reports(
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    """
    Performance report for every published writing.

    Uses the same published-status rule as the dashboard.
    Engagement rates are based on unique viewers and unique
    people performing each action.
    """

    # ---------------------------------------------------------
    # SAME PUBLISHED RULE USED BY DASHBOARD
    # ---------------------------------------------------------

    published_status = func.upper(
        func.trim(
            cast(Writing.status, String)
        )
    ) == "PUBLISHED"

    writings = db.scalars(
        select(Writing)
        .where(published_status)
        .order_by(Writing.created_at.desc())
    ).all()

    reports = []

    for writing in writings:

        # =====================================================
        # VIEWS + UNIQUE VIEWERS
        # =====================================================

        view_rows = db.execute(
            select(
                AnalyticsEvent.id,
                AnalyticsEvent.visitor_key,
                AnalyticsEvent.user_id,
            )
            .where(
                AnalyticsEvent.writing_id == writing.id,
                AnalyticsEvent.event_type == "VIEW",
            )
        ).all()

        total_views = len(view_rows)

        unique_viewers_set = set()

        for event_id, visitor_key, user_id in view_rows:

            # Logged-in user
            if user_id is not None:
                unique_viewers_set.add(
                    f"user:{user_id}"
                )

            # Anonymous visitor
            elif visitor_key:
                unique_viewers_set.add(
                    f"visitor:{visitor_key}"
                )

            # Last-resort fallback if an old event has
            # neither user_id nor visitor_key.
            else:
                unique_viewers_set.add(
                    f"view:{event_id}"
                )

        unique_viewers = len(unique_viewers_set)

        # =====================================================
        # LIKES
        # =====================================================

        like_rows = db.execute(
            select(
                WritingLike.user_id,
                WritingLike.visitor_key,
            )
            .where(
                WritingLike.writing_id == writing.id
            )
        ).all()

        total_likes = len(like_rows)

        unique_likers_set = set()

        for user_id, visitor_key in like_rows:

            if user_id is not None:
                unique_likers_set.add(
                    f"user:{user_id}"
                )

            elif visitor_key:
                unique_likers_set.add(
                    f"visitor:{visitor_key}"
                )

        unique_likers = len(unique_likers_set)

        # =====================================================
        # COMMENTS
        # =====================================================

        comment_rows = db.execute(
            select(Comment.author_id)
            .where(
                Comment.writing_id == writing.id
            )
        ).all()

        total_comments = len(comment_rows)

        unique_commenters_set = {
            f"user:{author_id}"
            for (author_id,) in comment_rows
            if author_id is not None
        }

        unique_commenters = len(
            unique_commenters_set
        )

        # =====================================================
        # BOOKMARKS / SAVES
        # =====================================================

        bookmark_rows = db.execute(
            select(Bookmark.user_id)
            .where(
                Bookmark.writing_id == writing.id
            )
        ).all()

        total_bookmarks = len(bookmark_rows)

        unique_savers_set = {
            f"user:{user_id}"
            for (user_id,) in bookmark_rows
            if user_id is not None
        }

        unique_savers = len(
            unique_savers_set
        )

        # =====================================================
        # UNIQUE ENGAGED PEOPLE
        # =====================================================

        engaged_people = (
            unique_likers_set
            | unique_commenters_set
            | unique_savers_set
        )

        unique_engaged_people = len(
            engaged_people
        )

        # =====================================================
        # ENGAGEMENT RATES
        # =====================================================

        if unique_viewers > 0:

            like_rate = round(
                (
                    unique_likers /
                    unique_viewers
                ) * 100,
                2
            )

            comment_rate = round(
                (
                    unique_commenters /
                    unique_viewers
                ) * 100,
                2
            )

            save_rate = round(
                (
                    unique_savers /
                    unique_viewers
                ) * 100,
                2
            )

            engagement_rate = round(
                (
                    unique_engaged_people /
                    unique_viewers
                ) * 100,
                2
            )

        else:

            like_rate = 0
            comment_rate = 0
            save_rate = 0
            engagement_rate = 0

        # Never allow rates above 100%.
        like_rate = min(like_rate, 100)
        comment_rate = min(comment_rate, 100)
        save_rate = min(save_rate, 100)
        engagement_rate = min(engagement_rate, 100)

        # =====================================================
        # PERFORMANCE LEVEL
        # =====================================================

        if engagement_rate >= 50:
            performance = "HIGH"

        elif engagement_rate >= 20:
            performance = "MEDIUM"

        else:
            performance = "LOW"

        # =====================================================
        # REPORT
        # =====================================================

        reports.append(
            {
                "writing_id": writing.id,
                "title": writing.title,

                "views": total_views,
                "unique_viewers": unique_viewers,

                "likes": total_likes,
                "unique_likers": unique_likers,

                "comments": total_comments,
                "unique_commenters": unique_commenters,

                "bookmarks": total_bookmarks,
                "unique_savers": unique_savers,

                "like_rate": like_rate,
                "comment_rate": comment_rate,
                "save_rate": save_rate,
                "engagement_rate": engagement_rate,

                "performance": performance,
            }
        )

    # IMPORTANT:
    # Return the actual number of published writings,
    # using the exact same query that produced the reports.
    return {
        "total_published_writings": len(reports),
        "reports": reports,
    }


# =========================================================
# AI WRITING PERFORMANCE ANALYSIS
# =========================================================

@router.post(
    "/writing-reports/{writing_id}/ai-analysis"
)
def ai_writing_analysis(
    writing_id: int,
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    """
    AI-powered writing-style and engagement analysis.

    Gemini is used when GEMINI_API_KEY is configured.

    If Gemini is unavailable, the endpoint automatically
    falls back to deterministic analytics-based analysis.

    Response source is either:

        "ai"

    or:

        "fallback"
    """

    # -----------------------------------------------------
    # FIND WRITING
    # -----------------------------------------------------

    writing = db.get(
        Writing,
        writing_id
    )

    if not writing:
        raise HTTPException(
            status_code=404,
            detail="Writing not found"
        )

    if writing.status != "PUBLISHED":
        raise HTTPException(
            status_code=400,
            detail="Only published writings can be analyzed"
        )

       # -----------------------------------------------------
    # VIEWS + UNIQUE VIEWERS
    # -----------------------------------------------------
    # -------------------------------------------------
    # VIEWS
    # -------------------------------------------------

    total_views = writing.view_count or 0

    unique_viewers = total_views

    # -----------------------------------------------------
    # LIKES
    # -----------------------------------------------------

    like_rows = db.execute(
        select(
            WritingLike.user_id,
            WritingLike.visitor_key
        )
        .where(
            WritingLike.writing_id == writing.id
        )
    ).all()

    total_likes = len(
        like_rows
    )

    unique_likers_set = set()

    for user_id, visitor_key in like_rows:

        if user_id is not None:
            unique_likers_set.add(
                f"user:{user_id}"
            )

        elif visitor_key:
            unique_likers_set.add(
                f"visitor:{visitor_key}"
            )

    unique_likers = len(
        unique_likers_set
    )

    # -----------------------------------------------------
    # COMMENTS
    # -----------------------------------------------------

    comment_rows = db.execute(
        select(Comment.author_id)
        .where(
            Comment.writing_id == writing.id
        )
    ).all()

    total_comments = len(
        comment_rows
    )

    unique_commenters_set = {
        f"user:{author_id}"
        for (author_id,) in comment_rows
        if author_id is not None
    }

    unique_commenters = len(
        unique_commenters_set
    )

    # -----------------------------------------------------
    # BOOKMARKS
    # -----------------------------------------------------

    bookmark_rows = db.execute(
        select(Bookmark.user_id)
        .where(
            Bookmark.writing_id == writing.id
        )
    ).all()

    total_bookmarks = len(
        bookmark_rows
    )

    unique_savers_set = {
        f"user:{user_id}"
        for (user_id,) in bookmark_rows
        if user_id is not None
    }

    unique_savers = len(
        unique_savers_set
    )

    # -----------------------------------------------------
    # UNIQUE ENGAGED PEOPLE
    # -----------------------------------------------------

    engaged_people = (
        unique_likers_set
        | unique_commenters_set
        | unique_savers_set
    )

    unique_engaged_people = len(
        engaged_people
    )

    # -----------------------------------------------------
    # ENGAGEMENT RATES
    #
    # Rates are based on UNIQUE PEOPLE.
    #
    # Example:
    #
    # 1 viewer
    # 6 comments
    #
    # unique commenters = 1
    # comment rate = 100%
    #
    # NOT 600%.
    # -----------------------------------------------------

    if unique_viewers > 0:

        like_rate = (
            unique_likers /
            unique_viewers
        ) * 100

        comment_rate = (
            unique_commenters /
            unique_viewers
        ) * 100

        save_rate = (
            unique_savers /
            unique_viewers
        ) * 100

        engagement_rate = (
            unique_engaged_people /
            unique_viewers
        ) * 100

    else:

        like_rate = 0
        comment_rate = 0
        save_rate = 0
        engagement_rate = 0

    like_rate = min(
        round(like_rate, 2),
        100
    )

    comment_rate = min(
        round(comment_rate, 2),
        100
    )

    save_rate = min(
        round(save_rate, 2),
        100
    )

    engagement_rate = min(
        round(engagement_rate, 2),
        100
    )

    # -----------------------------------------------------
    # PERFORMANCE
    # -----------------------------------------------------

    if engagement_rate >= 50:
        performance = "HIGH"

    elif engagement_rate >= 20:
        performance = "MEDIUM"

    else:
        performance = "LOW"

    # -----------------------------------------------------
    # METRICS
    # -----------------------------------------------------

    metrics = {
        "views": total_views,
        "unique_viewers": unique_viewers,

        "likes": total_likes,
        "unique_likers": unique_likers,

        "comments": total_comments,
        "unique_commenters": unique_commenters,

        "saves": total_bookmarks,
        "unique_savers": unique_savers,

        "like_rate": like_rate,
        "comment_rate": comment_rate,
        "save_rate": save_rate,

        "engagement_rate": engagement_rate,
        "performance": performance,
    }

    # =====================================================
    # FALLBACK ANALYSIS
    # =====================================================

    if total_comments > 0:

        strongest_signal = (
            "Comment activity is currently the strongest "
            "visible engagement signal."
        )

    elif total_likes > 0:

        strongest_signal = (
            "Like activity is currently the strongest "
            "visible engagement signal."
        )

    elif total_bookmarks > 0:

        strongest_signal = (
            "Bookmark activity is currently the strongest "
            "visible engagement signal."
        )

    elif total_views > 0:

        strongest_signal = (
            "The writing is receiving views, but there is "
            "not enough engagement yet to identify a strong "
            "interaction signal."
        )

    else:

        strongest_signal = (
            "There is currently not enough audience activity "
            "to identify a strong engagement signal."
        )

    if (
        unique_viewers > 0
        and unique_engaged_people > 0
    ):

        audience_response = (
            "This writing is receiving strong interaction "
            "relative to its current number of unique viewers."
        )

    elif unique_viewers > 0:

        audience_response = (
            "This writing has received views, but there is "
            "currently limited measurable interaction."
        )

    else:

        audience_response = (
            "There is not yet enough audience activity to "
            "evaluate the response to this writing."
        )

    fallback_analysis = {
        "writing_style": (
            "Content-based style analysis is unavailable "
            "in fallback mode."
        ),

        "audience_response": audience_response,

        "what_works": strongest_signal,

        "recommendation": (
            "Consider exploring similar themes, structures, "
            "or writing approaches in future pieces while "
            "continuing to compare them against actual "
            "audience behavior."
        ),
    }

    # =====================================================
    # GEMINI AI ANALYSIS
    # =====================================================

    try:

        # -------------------------------------------------
        # CHECK API KEY
        # -------------------------------------------------

        if not settings.GEMINI_API_KEY:

            raise RuntimeError(
                "GEMINI_API_KEY is not configured."
            )

        # -------------------------------------------------
        # CLEAN WRITING CONTENT
        # -------------------------------------------------

        clean_content = re.sub(
            r"<[^>]+>",
            " ",
            writing.content or ""
        )

        clean_content = re.sub(
            r"\s+",
            " ",
            clean_content
        ).strip()

        # Prevent unnecessarily large requests.
        clean_content = clean_content[:12000]

        # -------------------------------------------------
        # GEMINI CLIENT
        # -------------------------------------------------

        client = genai.Client(
            api_key=settings.GEMINI_API_KEY
        )

        # -------------------------------------------------
        # AI PROMPT
        # -------------------------------------------------

        prompt = f"""
You are analyzing a published writing for an admin
analytics dashboard.

Analyze BOTH:

1. The actual writing itself.
2. The real audience engagement metrics.

Do NOT invent demographic information.

Do NOT infer:
- gender
- age
- location
- ethnicity
- identity
- personal characteristics

Only analyze what can reasonably be inferred from
the writing and the supplied engagement data.

Return ONLY valid JSON with exactly these fields:

{{
  "writing_style": "...",
  "audience_response": "...",
  "what_works": "...",
  "recommendation": "..."
}}

WRITING TITLE:
{writing.title}

WRITING CONTENT:
{clean_content}

REAL PERFORMANCE METRICS:
{json.dumps(metrics, indent=2)}

Instructions for writing_style:

Describe the actual writing style, tone, structure,
language, pacing, and noticeable characteristics.

Instructions for audience_response:

Interpret the supplied engagement metrics realistically.

Remember that the dataset may be very small.

Do not call one person's interaction "viral",
"popular", or statistically significant.

Instructions for what_works:

Identify what appears to be working based on both
the writing and the measurable audience engagement.

Instructions for recommendation:

Give practical recommendations for future writings
based on the writing and the engagement data.

Do not claim causation when the dataset is too small.

Do not invent engagement that is not present.
"""

        # -------------------------------------------------
        # GENERATE CONTENT
        # -------------------------------------------------

                       # -------------------------------------------------
        # GENERATE AI ANALYSIS USING GEMINI
        # -------------------------------------------------

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
            },
        )

        # -------------------------------------------------
        # GET GEMINI RESPONSE
        # -------------------------------------------------

        raw_text = response.text

        if not raw_text:
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        # -------------------------------------------------
        # PARSE GEMINI JSON RESPONSE
        # -------------------------------------------------

        try:
            analysis = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Gemini returned invalid JSON: {e}"
            )

        # -------------------------------------------------
        # VALIDATE RESPONSE
        # -------------------------------------------------

        fields = [
            "writing_style",
            "audience_response",
            "what_works",
            "recommendation",
        ]

        for field in fields:

            if field not in analysis:

                raise RuntimeError(
                    f"Gemini response missing field: {field}"
                )

            if not isinstance(
                analysis[field],
                str
            ):

                raise RuntimeError(
                    f"Gemini response field "
                    f"'{field}' is not a string."
                )

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        return {
            "writing_id": writing.id,

            "title": writing.title,

            "metrics": metrics,

            "analysis": {
                field: analysis[field].strip()
                for field in fields
            },

            "source": "ai",
        }

    # =====================================================
    # AI FAILURE -> FALLBACK
    # =====================================================

    except Exception as e:

        print(
            "GEMINI AI ANALYSIS ERROR:",
            repr(e)
        )

        return {
            "writing_id": writing.id,

            "title": writing.title,

            "metrics": metrics,

            "analysis": fallback_analysis,

            "source": "fallback",
        }


# =========================================================
# ADMIN REPORTS
# =========================================================

@router.get("/reports")
def reports(
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    return list(
        db.scalars(
            select(Report)
            .order_by(
                Report.created_at.desc()
            )
        ).all()
    )


# =========================================================
# UPDATE REPORT STATUS
# =========================================================

@router.patch("/reports/{report_id}")
def report_status(
    report_id: int,
    d: StatusIn,
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    r = db.get(
        Report,
        report_id
    )

    if not r:
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    if d.status not in (
        "OPEN",
        "REVIEWED",
        "RESOLVED",
        "DISMISSED",
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid status"
        )

    r.status = d.status

    db.commit()

    return {
        "message": "Report updated"
    }


# =========================================================
# ADMIN COMMENTS
# =========================================================

@router.get("/comments")
def comments(
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    return list(
        db.scalars(
            select(Comment)
            .order_by(
                Comment.created_at.desc()
            )
        ).all()
    )


# =========================================================
# MODERATE COMMENT
# =========================================================

@router.patch("/comments/{comment_id}/moderate")
def moderate(
    comment_id: int,
    d: StatusIn,
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    c = db.get(
        Comment,
        comment_id
    )

    if not c:
        raise HTTPException(
            status_code=404,
            detail="Comment not found"
        )

    if d.status not in (
        "VISIBLE",
        "HIDDEN",
        "REMOVED",
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid status"
        )

    c.status = d.status

    db.commit()

    return {
        "message": "Comment moderated"
    }


# =========================================================
# ADMIN USERS
# =========================================================

@router.get("/users")
def users(
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    return list(
        db.scalars(
            select(User)
            .order_by(
                User.created_at.desc()
            )
        ).all()
    )


# =========================================================
# UPDATE USER STATUS
# =========================================================

@router.patch("/users/{user_id}/status")
def user_status(
    user_id: int,
    d: StatusIn,
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    x = db.get(
        User,
        user_id
    )

    if not x:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    x.is_active = (
        d.status == "ACTIVE"
    )

    db.commit()

    return {
        "message": "User status updated"
    }

def make_unique_community_slug(title: str, db: Session) -> str:
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
# COMMUNITY SUBMISSIONS
# =========================================================

@router.get("/community/submissions")
def community_submissions(
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
# UPDATE COMMUNITY SUBMISSION STATUS
# =========================================================

@router.patch("/community/submissions/{submission_id}")
def community_submission_status(
    submission_id: int,
    d: StatusIn,
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    submission = db.get(
        CommunitySubmission,
        submission_id
    )

    if not submission:
        raise HTTPException(
            status_code=404,
            detail="Community submission not found"
        )

    if d.status not in (
        "PENDING",
        "APPROVED",
        "REJECTED",
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid status"
        )

    submission.status = d.status

    if d.status in ("APPROVED", "REJECTED"):
        submission.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(submission)

    return {
        "message": "Community submission updated",
        "id": submission.id,
        "status": submission.status,
    }

# =========================================================
# DELETE COMMUNITY SUBMISSION
# =========================================================

@router.delete("/community/submissions/{submission_id}")
def delete_community_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    submission = db.get(
        CommunitySubmission,
        submission_id
    )

    if not submission:
        raise HTTPException(
            status_code=404,
            detail="Community submission not found"
        )

    db.delete(submission)
    db.commit()

    return {
        "message": "Community submission deleted",
        "id": submission_id
    }

# =========================================================
# PUBLISH COMMUNITY SUBMISSION
# =========================================================

@router.post("/community/submissions/{submission_id}/publish")
def publish_community_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    submission = db.get(
        CommunitySubmission,
        submission_id
    )

    if not submission:
        raise HTTPException(
            status_code=404,
            detail="Community submission not found."
        )

    if submission.status != "APPROVED":
        raise HTTPException(
            status_code=400,
            detail="Only approved submissions can be published."
        )

    # Get or create Community category
    category = get_or_create_community_category(db)

    # Generate unique slug
    slug = make_unique_community_slug(
        submission.title,
        db
    )

    now = datetime.utcnow()

    # Create archive writing
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

    # Mark submission as published
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