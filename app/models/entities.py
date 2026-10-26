from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    openid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    avatar_url: Mapped[str] = mapped_column(String(512), default="")
    body_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    level: Mapped[str] = mapped_column(String(16), default="入门")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    listings = relationship("MarketListing", back_populates="seller")
    purchases = relationship(
        "Purchase",
        back_populates="buyer",
        foreign_keys="Purchase.buyer_id",
    )
    nodes = relationship("TrainingNode", back_populates="owner")


class MarketListing(Base):
    """市场商品：kind=plan 可执行方案 | lesson 教学模块。"""

    __tablename__ = "market_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # plan | lesson
    title: Mapped[str] = mapped_column(String(128))
    level: Mapped[str] = mapped_column(String(16), index=True)
    body_range: Mapped[str] = mapped_column(String(128), default="")
    price_fen: Mapped[int] = mapped_column(Integer)  # 分；标价=实付
    cover_url: Mapped[str] = mapped_column(String(512), default="")
    media_json: Mapped[str] = mapped_column(Text, default="[]")  # [{type,url,...}]
    body_text: Mapped[str] = mapped_column(Text, default="")
    # plan only
    cycle: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True)  # week|month|full
    week_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    days_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rhythm: Mapped[str] = mapped_column(String(256), default="")
    # lesson only
    topic: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    skill_tags_json: Mapped[str] = mapped_column(Text, default="[]")
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    cues_json: Mapped[str] = mapped_column(Text, default="[]")
    demo_media_json: Mapped[str] = mapped_column(Text, default="[]")
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="listed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    seller = relationship("User", back_populates="listings")
    comments = relationship("MarketComment", back_populates="listing", cascade="all, delete-orphan")
    likes = relationship("MarketLike", back_populates="listing", cascade="all, delete-orphan")


class MarketComment(Base):
    __tablename__ = "market_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("market_listings.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    text: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    listing = relationship("MarketListing", back_populates="comments")


class MarketLike(Base):
    __tablename__ = "market_likes"
    __table_args__ = (UniqueConstraint("listing_id", "user_id", name="uq_like"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("market_listings.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    listing = relationship("MarketListing", back_populates="likes")


class Purchase(Base):
    __tablename__ = "purchases"
    __table_args__ = (UniqueConstraint("buyer_id", "listing_id", name="uq_buy_once"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("market_listings.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    total_paid_fen: Mapped[int] = mapped_column(Integer)
    platform_cut_fen: Mapped[int] = mapped_column(Integer)
    creator_earn_fen: Mapped[int] = mapped_column(Integer)
    ack_weight: Mapped[bool] = mapped_column(Boolean, default=False)
    ack_level: Mapped[bool] = mapped_column(Boolean, default=False)
    node_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="paid")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    buyer = relationship("User", back_populates="purchases", foreign_keys="Purchase.buyer_id")


class TrainingNode(Base):
    """复刻后进入「我的 → 训练节点」库；含 media 全量拷贝。"""

    __tablename__ = "training_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_listing_id: Mapped[int] = mapped_column(ForeignKey("market_listings.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(128))
    level: Mapped[str] = mapped_column(String(16))
    body_range: Mapped[str] = mapped_column(String(128), default="")
    cover_url: Mapped[str] = mapped_column(String(512), default="")
    media_json: Mapped[str] = mapped_column(Text, default="[]")
    body_text: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text)  # plan/lesson 专属字段全量
    purchased_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="nodes")


class AssembledPlan(Base):
    """用户从节点库拼装出的生效方案。"""

    __tablename__ = "assembled_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(128), default="")
    cycle: Mapped[str] = mapped_column(String(16), default="week")
    days_json: Mapped[str] = mapped_column(Text)  # 含 exercises[].lesson_node_id 学法位
    ack_weight: Mapped[bool] = mapped_column(Boolean, default=False)
    ack_level: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
