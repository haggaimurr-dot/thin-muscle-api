import json
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    AssembledPlan,
    MarketComment,
    MarketLike,
    MarketListing,
    Purchase,
    TrainingNode,
    User,
)
from app.schemas.market import AssembleRequest, ListingCreate, ReplicateRequest


def fee_split_fen(total_fen: int) -> tuple[int, int]:
    platform = int(round(total_fen * settings.market_fee_rate))
    creator = total_fen - platform
    return platform, creator


def _loads(s: str | None, default: Any):
    if not s:
        return default
    return json.loads(s)


def listing_payload(listing: MarketListing) -> dict:
    base = {
        "listing_id": listing.id,
        "seller_id": listing.seller_id,
        "kind": listing.kind,
        "title": listing.title,
        "level": listing.level,
        "body_range": listing.body_range,
        "price_fen": listing.price_fen,
        "cover_url": listing.cover_url,
        "media": _loads(listing.media_json, []),
        "body_text": listing.body_text,
        "likes": listing.likes_count,
        "created_at": listing.created_at.isoformat() + "Z" if listing.created_at else None,
    }
    if listing.kind == "plan":
        base.update(
            {
                "cycle": listing.cycle,
                "week_index": listing.week_index,
                "days": _loads(listing.days_json, []),
                "rhythm": listing.rhythm,
                "badge": _badge(listing),
            }
        )
    else:
        base.update(
            {
                "topic": listing.topic,
                "skill_tags": _loads(listing.skill_tags_json, []),
                "steps": _loads(listing.steps_json, []),
                "cues": _loads(listing.cues_json, []),
                "demo_media": _loads(listing.demo_media_json, []),
                "badge": "教学",
            }
        )
    return base


def _badge(listing: MarketListing) -> str:
    if listing.kind == "lesson":
        return "教学"
    label = {"week": "整周", "month": "整月", "full": "全程"}.get(listing.cycle or "", "方案")
    if listing.week_index:
        return f"{label} · 第 {listing.week_index} 周"
    return label


def create_listing(db: Session, seller: User, body: ListingCreate) -> MarketListing:
    listing = MarketListing(
        seller_id=seller.id,
        kind=body.kind,
        title=body.title,
        level=body.level,
        body_range=body.body_range,
        price_fen=body.price_fen,
        cover_url=body.cover_url,
        media_json=json.dumps([m.model_dump() for m in body.media], ensure_ascii=False),
        body_text=body.body_text,
        cycle=body.cycle if body.kind == "plan" else None,
        week_index=body.week_index if body.kind == "plan" else None,
        days_json=json.dumps([d.model_dump() for d in (body.days or [])], ensure_ascii=False)
        if body.kind == "plan"
        else None,
        rhythm=body.rhythm if body.kind == "plan" else "",
        topic=body.topic if body.kind == "lesson" else None,
        skill_tags_json=json.dumps(body.skill_tags, ensure_ascii=False),
        steps_json=json.dumps(body.steps, ensure_ascii=False),
        cues_json=json.dumps(body.cues, ensure_ascii=False),
        demo_media_json=json.dumps([m.model_dump() for m in body.demo_media], ensure_ascii=False),
        status="listed",
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def list_listings(
    db: Session,
    kind: Optional[str] = None,
    cycle: Optional[str] = None,
    level: Optional[str] = None,
) -> list[tuple[MarketListing, User]]:
    q = (
        db.query(MarketListing, User)
        .join(User, MarketListing.seller_id == User.id)
        .filter(MarketListing.status == "listed")
    )
    if kind and kind != "all":
        q = q.filter(MarketListing.kind == kind)
    if cycle and cycle != "all":
        q = q.filter(MarketListing.cycle == cycle)
    if level and level != "all":
        q = q.filter(MarketListing.level == level)
    return q.order_by(MarketListing.created_at.desc()).all()


def get_listing(db: Session, listing_id: int) -> tuple[MarketListing, User]:
    row = (
        db.query(MarketListing, User)
        .join(User, MarketListing.seller_id == User.id)
        .filter(MarketListing.id == listing_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "商品不存在")
    return row


def toggle_like(db: Session, listing: MarketListing, user: User) -> bool:
    existing = (
        db.query(MarketLike)
        .filter(MarketLike.listing_id == listing.id, MarketLike.user_id == user.id)
        .first()
    )
    if existing:
        db.delete(existing)
        listing.likes_count = max(0, listing.likes_count - 1)
        liked = False
    else:
        db.add(MarketLike(listing_id=listing.id, user_id=user.id))
        listing.likes_count += 1
        liked = True
    db.commit()
    return liked


def add_comment(db: Session, listing: MarketListing, user: User, text: str) -> MarketComment:
    c = MarketComment(listing_id=listing.id, user_id=user.id, text=text.strip())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _node_payload_from_listing(listing: MarketListing) -> dict:
    """复刻全量拷贝（含 media）；写入节点库。"""
    data = listing_payload(listing)
    # strip market-only display fields that still belong in node
    data.pop("likes", None)
    data.pop("created_at", None)
    data.pop("badge", None)
    data.pop("listing_id", None)
    data.pop("seller_id", None)
    data.pop("price_fen", None)
    return data


def purchase(
    db: Session,
    listing: MarketListing,
    buyer: User,
    req: ReplicateRequest,
) -> tuple[Purchase, TrainingNode]:
    if not req.ack_weight or not req.ack_level:
        raise HTTPException(400, "复刻前须勾选体重区间与训练水平确认")
    if listing.seller_id == buyer.id:
        raise HTTPException(400, "不能复刻自己的商品")
    if listing.status != "listed":
        raise HTTPException(400, "已下架")

    exists = (
        db.query(Purchase)
        .filter(Purchase.buyer_id == buyer.id, Purchase.listing_id == listing.id, Purchase.status == "paid")
        .first()
    )
    if exists:
        raise HTTPException(409, "你已复刻过该商品")

    platform, creator = fee_split_fen(listing.price_fen)
    payload = _node_payload_from_listing(listing)
    node = TrainingNode(
        owner_id=buyer.id,
        source_listing_id=listing.id,
        kind=listing.kind,
        title=listing.title,
        level=listing.level,
        body_range=listing.body_range,
        cover_url=listing.cover_url,
        media_json=listing.media_json,  # 保留
        body_text=listing.body_text,
        payload_json=json.dumps(payload, ensure_ascii=False),
    )
    db.add(node)
    db.flush()

    order = Purchase(
        buyer_id=buyer.id,
        listing_id=listing.id,
        seller_id=listing.seller_id,
        total_paid_fen=listing.price_fen,
        platform_cut_fen=platform,
        creator_earn_fen=creator,
        ack_weight=True,
        ack_level=True,
        node_id=node.id,
        status="paid",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    db.refresh(node)
    return order, node


def list_nodes(db: Session, user: User, kind: Optional[str] = None) -> list[TrainingNode]:
    q = db.query(TrainingNode).filter(TrainingNode.owner_id == user.id)
    if kind and kind != "all":
        q = q.filter(TrainingNode.kind == kind)
    return q.order_by(TrainingNode.purchased_at.desc()).all()


def node_out(node: TrainingNode) -> dict:
    payload = _loads(node.payload_json, {})
    return {
        "node_id": node.id,
        "source_listing_id": node.source_listing_id,
        "kind": node.kind,
        "title": node.title,
        "level": node.level,
        "body_range": node.body_range,
        "cover_url": node.cover_url,
        "media": _loads(node.media_json, []),
        "body_text": node.body_text,
        "purchased_at": node.purchased_at.isoformat() + "Z" if node.purchased_at else None,
        **payload,
    }


def assemble(db: Session, user: User, req: AssembleRequest) -> AssembledPlan:
    if not req.ack_weight or not req.ack_level:
        raise HTTPException(400, "应用到训练前须勾选体重区间与训练水平确认")

    # 校验节点归属 + lesson 只能挂学法位
    for day in req.days:
        for ex in day.exercises:
            if ex.from_plan_node_id:
                n = db.get(TrainingNode, ex.from_plan_node_id)
                if not n or n.owner_id != user.id:
                    raise HTTPException(400, f"plan 节点 {ex.from_plan_node_id} 不存在或不属于你")
                if n.kind != "plan":
                    raise HTTPException(400, "from_plan_node_id 必须是 plan 节点")
            if ex.lesson_node_id:
                n = db.get(TrainingNode, ex.lesson_node_id)
                if not n or n.owner_id != user.id:
                    raise HTTPException(400, f"lesson 节点 {ex.lesson_node_id} 不存在或不属于你")
                if n.kind != "lesson":
                    raise HTTPException(400, "学法位只能挂 lesson 节点")

    db.query(AssembledPlan).filter(AssembledPlan.user_id == user.id, AssembledPlan.active.is_(True)).update(
        {"active": False}
    )
    plan = AssembledPlan(
        user_id=user.id,
        title=req.title,
        cycle=req.cycle,
        days_json=json.dumps([d.model_dump() for d in req.days], ensure_ascii=False),
        ack_weight=True,
        ack_level=True,
        active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan
