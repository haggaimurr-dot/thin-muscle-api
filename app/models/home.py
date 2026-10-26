from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (UniqueConstraint("follower_id", "followee_id", name="uq_follow"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    follower_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    followee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WeekStat(Base):
    """按自然周汇总的硬进度，供首页图表与排行榜。"""

    __tablename__ = "week_stats"
    __table_args__ = (UniqueConstraint("user_id", "week_id", name="uq_week_stat"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    week_id: Mapped[str] = mapped_column(String(16), index=True)  # YYYY-MM-DD 周一
    strength_done: Mapped[int] = mapped_column(Integer, default=0)  # 0–3
    strength_total: Mapped[int] = mapped_column(Integer, default=3)
    overload_count: Mapped[int] = mapped_column(Integer, default=0)
    protein_days: Mapped[int] = mapped_column(Integer, default=0)
    load_up_kg: Mapped[float] = mapped_column(Float, default=0.0)  # 同体重区间相对加重量
    gains_json: Mapped[str] = mapped_column(Text, default="[]")  # ["哑铃卧推 18→20kg", ...]
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FeedPost(Base):
    """关注流成果卡（本周涨重量/次数）。"""

    __tablename__ = "feed_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    week_id: Mapped[str] = mapped_column(String(16), index=True)
    gains_json: Mapped[str] = mapped_column(Text, default="[]")
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FeedLike(Base):
    __tablename__ = "feed_likes"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_feed_like"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("feed_posts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FeedComment(Base):
    __tablename__ = "feed_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("feed_posts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    text: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RankSnapshot(Base):
    """每小时排名快照：按 period × dim ×（小榜时 body_band）存每个用户的名次。"""

    __tablename__ = "rank_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "hour_bucket", "period", "dim", "body_band", "user_id",
            name="uq_rank_snap",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hour_bucket: Mapped[str] = mapped_column(String(16), index=True)  # YYYY-MM-DDTHH
    period: Mapped[str] = mapped_column(String(8), index=True)
    dim: Mapped[str] = mapped_column(String(32), index=True)
    body_band: Mapped[str] = mapped_column(String(32), default="")  # weight_class 用；总榜空串
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
