from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.entities import User
from app.services import home as svc

router = APIRouter(prefix="/home", tags=["home"])


class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@router.get("/stats")
def home_stats(
    period: str = Query(default="week", description="week|month"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return svc.my_stats(db, user, period=period)


@router.get("/rank")
def home_rank(
    dim: str = Query(default="strength", description="strength|overload|protein|streak|weight_class"),
    period: str = Query(default="week", description="week|month"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return svc.rank(db, user, dim=dim, period=period)


@router.post("/rank/refresh")
def refresh_rank(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """系统/运维触发：强制刷新本小时快照。定时任务每小时调一次即可。"""
    return svc.refresh_rank_snapshots(db)


@router.get("/follows")
def my_follows(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"items": svc.list_following(db, user)}


@router.get("/discover")
def discover(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"items": svc.discover_users(db, user)}


@router.post("/follows/{followee_id}")
def follow_toggle(followee_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.toggle_follow(db, user, followee_id)


@router.get("/feed")
def home_feed(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.feed(db, user)


@router.post("/feed/{post_id}/like")
def feed_like(post_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.toggle_feed_like(db, user, post_id)


@router.post("/feed/{post_id}/comments")
def feed_comment(
    post_id: int,
    body: CommentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return svc.add_feed_comment(db, user, post_id, body.text)
