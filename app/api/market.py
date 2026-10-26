import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.entities import MarketComment, MarketLike, Purchase, User
from app.schemas.market import AssembleRequest, CommentCreate, ListingCreate, ReplicateRequest
from app.services import market as svc

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/listings")
def get_listings(
    kind: str | None = Query(default="all", description="all|plan|lesson"),
    cycle: str | None = Query(default="all", description="all|week|month|full"),
    level: str | None = Query(default="all", description="all|入门|进阶"),
    db: Session = Depends(get_db),
):
    rows = svc.list_listings(db, kind=kind, cycle=cycle, level=level)
    items = []
    for listing, seller in rows:
        card = svc.listing_payload(listing)
        card["user"] = seller.nickname or seller.openid
        items.append(card)
    if not items and (kind not in (None, "all") or cycle not in (None, "all") or level not in (None, "all")):
        return {"items": [], "empty_hint": "该筛选下暂无方案"}
    return {"items": items}


@router.get("/listings/{listing_id}")
def get_listing_detail(
    listing_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    listing, seller = svc.get_listing(db, listing_id)
    detail = svc.listing_payload(listing)
    detail["user"] = seller.nickname or seller.openid
    comments = (
        db.query(MarketComment, User)
        .join(User, MarketComment.user_id == User.id)
        .filter(MarketComment.listing_id == listing.id)
        .order_by(MarketComment.created_at.asc())
        .all()
    )
    detail["comments"] = [
        {"id": c.id, "user": u.nickname or u.openid, "text": c.text, "created_at": c.created_at}
        for c, u in comments
    ]
    detail["liked_by_me"] = (
        db.query(MarketLike)
        .filter(MarketLike.listing_id == listing.id, MarketLike.user_id == user.id)
        .first()
        is not None
    )
    detail["bought_by_me"] = (
        db.query(Purchase)
        .filter(Purchase.buyer_id == user.id, Purchase.listing_id == listing.id, Purchase.status == "paid")
        .first()
        is not None
    )
    return detail


@router.post("/listings")
def publish_listing(
    body: ListingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    listing = svc.create_listing(db, user, body)
    return {"listing_id": listing.id, "kind": listing.kind, "badge": svc._badge(listing), "message": "已上架"}


@router.post("/listings/{listing_id}/like")
def like_listing(listing_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    listing, _ = svc.get_listing(db, listing_id)
    liked = svc.toggle_like(db, listing, user)
    return {"liked": liked, "likes": listing.likes_count}


@router.post("/listings/{listing_id}/comments")
def comment_listing(
    listing_id: int,
    body: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    listing, _ = svc.get_listing(db, listing_id)
    c = svc.add_comment(db, listing, user, body.text)
    return {"id": c.id, "user": user.nickname or user.openid, "text": c.text, "created_at": c.created_at}


@router.post("/listings/{listing_id}/replicate")
def replicate_listing(
    listing_id: int,
    body: ReplicateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    listing, _ = svc.get_listing(db, listing_id)
    order, node = svc.purchase(db, listing, user, body)
    return {
        "purchase_id": order.id,
        "node": svc.node_out(node),
        "total_paid_fen": order.total_paid_fen,
        "platform_cut_fen": order.platform_cut_fen,
        "creator_earn_fen": order.creator_earn_fen,
        "message": "已复刻，媒体已保留并写入训练节点库",
    }


@router.get("/nodes")
def my_nodes(
    kind: str | None = Query(default="all", description="all|plan|lesson"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    nodes = svc.list_nodes(db, user, kind=kind)
    return {"items": [svc.node_out(n) for n in nodes]}


@router.post("/assemble")
def assemble_plan(
    body: AssembleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plan = svc.assemble(db, user, body)
    return {
        "plan_id": plan.id,
        "title": plan.title,
        "cycle": plan.cycle,
        "days": json.loads(plan.days_json),
        "message": "已应用到训练（拼装方案生效）",
    }
