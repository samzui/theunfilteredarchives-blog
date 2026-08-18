from datetime import datetime
from sqlalchemy import String,Text,Boolean,DateTime,ForeignKey,Integer,UniqueConstraint,CheckConstraint,Table,Column
from sqlalchemy.orm import Mapped,mapped_column,relationship
from app.database import Base

writing_tags=Table("writing_tags",Base.metadata,
 Column("writing_id",ForeignKey("writings.id",ondelete="CASCADE"),primary_key=True),
 Column("tag_id",ForeignKey("tags.id",ondelete="CASCADE"),primary_key=True))

class User(Base):
 __tablename__="users"
 id:Mapped[int]=mapped_column(primary_key=True); email:Mapped[str]=mapped_column(String(255),unique=True,index=True)
 display_name:Mapped[str]=mapped_column(String(80)); password_hash:Mapped[str]=mapped_column(String(255))
 role:Mapped[str]=mapped_column(String(20),default="READER"); is_active:Mapped[bool]=mapped_column(Boolean,default=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)
 writings=relationship("Writing",back_populates="author"); comments=relationship("Comment",back_populates="author")

class Category(Base):
 __tablename__="categories"
 id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(80),unique=True); slug:Mapped[str]=mapped_column(String(100),unique=True)
 writings=relationship("Writing",back_populates="category")

class Tag(Base):
 __tablename__="tags"
 id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(50),unique=True); slug:Mapped[str]=mapped_column(String(70),unique=True)

class Writing(Base):
 __tablename__="writings"
 id:Mapped[int]=mapped_column(primary_key=True); title:Mapped[str]=mapped_column(String(220)); slug:Mapped[str]=mapped_column(String(240),unique=True,index=True)
 excerpt:Mapped[str|None]=mapped_column(Text); content:Mapped[str]=mapped_column(Text); cover_image_url:Mapped[str|None]=mapped_column(Text)
 status:Mapped[str]=mapped_column(String(20),default="DRAFT"); featured:Mapped[bool]=mapped_column(Boolean,default=False); view_count:Mapped[int]=mapped_column(Integer,default=0)
 category_id:Mapped[int|None]=mapped_column(ForeignKey("categories.id",ondelete="SET NULL")); author_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"))
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow); updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow,onupdate=datetime.utcnow); published_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 author=relationship("User",back_populates="writings"); category=relationship("Category",back_populates="writings"); tags=relationship("Tag",secondary=writing_tags); comments=relationship("Comment",back_populates="writing",cascade="all, delete-orphan")

class Comment(Base):
 __tablename__="comments"
 id:Mapped[int]=mapped_column(primary_key=True); content:Mapped[str]=mapped_column(Text); status:Mapped[str]=mapped_column(String(20),default="VISIBLE")
 author_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE")); writing_id:Mapped[int]=mapped_column(ForeignKey("writings.id",ondelete="CASCADE")); parent_id:Mapped[int|None]=mapped_column(ForeignKey("comments.id",ondelete="CASCADE"))
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow); updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow,onupdate=datetime.utcnow)
 author=relationship("User",back_populates="comments"); writing=relationship("Writing",back_populates="comments"); replies=relationship("Comment",cascade="all, delete-orphan")

class WritingLike(Base):
 __tablename__="writing_likes"
 id:Mapped[int]=mapped_column(primary_key=True); writing_id:Mapped[int]=mapped_column(ForeignKey("writings.id",ondelete="CASCADE")); user_id:Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="CASCADE")); visitor_key:Mapped[str|None]=mapped_column(String(128))
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)
 __table_args__=(UniqueConstraint("writing_id","user_id"),UniqueConstraint("writing_id","visitor_key"),CheckConstraint("(user_id IS NOT NULL) OR (visitor_key IS NOT NULL)"))

class CommentLike(Base):
 __tablename__="comment_likes"
 id:Mapped[int]=mapped_column(primary_key=True); comment_id:Mapped[int]=mapped_column(ForeignKey("comments.id",ondelete="CASCADE")); user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"))
 __table_args__=(UniqueConstraint("comment_id","user_id"),)

class Bookmark(Base):
 __tablename__="bookmarks"
 id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE")); writing_id:Mapped[int]=mapped_column(ForeignKey("writings.id",ondelete="CASCADE")); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)
 __table_args__=(UniqueConstraint("user_id","writing_id"),)

class Notification(Base):
 __tablename__="notifications"
 id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE")); actor_id:Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"))
 type:Mapped[str]=mapped_column(String(40)); message:Mapped[str]=mapped_column(String(500)); comment_id:Mapped[int|None]=mapped_column(ForeignKey("comments.id",ondelete="SET NULL")); writing_id:Mapped[int|None]=mapped_column(ForeignKey("writings.id",ondelete="SET NULL")); is_read:Mapped[bool]=mapped_column(Boolean,default=False); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)

class Report(Base):
 __tablename__="reports"
 id:Mapped[int]=mapped_column(primary_key=True); comment_id:Mapped[int]=mapped_column(ForeignKey("comments.id",ondelete="CASCADE")); reporter_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE")); reason:Mapped[str]=mapped_column(String(500)); status:Mapped[str]=mapped_column(String(20),default="OPEN"); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)

class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Anonymous visitor identifier
    visitor_key: Mapped[str] = mapped_column(
        String(128),
        index=True
    )

    # Logged-in user, if available
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Writing involved in the event, if applicable
    writing_id: Mapped[int | None] = mapped_column(
        ForeignKey("writings.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # VIEW, LIKE, COMMENT, BOOKMARK
    event_type: Mapped[str] = mapped_column(
        String(30),
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        index=True
    )

class CommunitySubmission(Base):
    __tablename__ = "community_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(120))

    email: Mapped[str] = mapped_column(
        String(255),
        index=True
    )

    title: Mapped[str] = mapped_column(
        String(220)
    )

    content: Mapped[str] = mapped_column(Text)

    consent: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        index=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )