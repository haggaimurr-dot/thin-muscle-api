import json
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.entities import User
from app.models.home import FeedComment, FeedLike, FeedPost, Follow, RankSnapshot, WeekStat


def monday_ymd(d: datetime | None = None) -> str:
    d = d or datetime.utcnow()
    day = d.weekday()  # Mon=0
    m = d - timedelta(days=day)
    return m.strftime("%Y-%m-%d")


def body_band(kg: float | None) -> str:
    if kg is None:
        return "未知"
    if kg < 60:
        return "50–65kg"
    if kg < 70:
        return "60–75kg"
    if kg < 85:
        return "70–85kg"
    return "80–95kg"


def is_valid_week(stat: WeekStat) -> bool:
    """当周力量日 ≥2/3 才算有效周（续周）。"""
    total = max(1, stat.strength_total or 3)
    return (stat.strength_done / total) >= (2 / 3)


def strength_rate(stat: WeekStat) -> int:
    total = max(1, stat.strength_total or 3)
    return round(100 * stat.strength_done / total)


def streak_weeks(db: Session, user_id: int, up_to_week: str) -> int:
    rows = (
        db.query(WeekStat)
        .filter(WeekStat.user_id == user_id, WeekStat.week_id <= up_to_week)
        .order_by(WeekStat.week_id.desc())
        .all()
    )
    streak = 0
    expect = up_to_week
    for r in rows:
        if r.week_id != expect:
            break
        if not is_valid_week(r):
            break
        streak += 1
        # previous monday
        dt = datetime.strptime(expect, "%Y-%m-%d") - timedelta(days=7)
        expect = dt.strftime("%Y-%m-%d")
    return streak


def aggregate_period(db: Session, user: User, period: str, week_id: str) -> dict:
    if period == "month":
        # 近 4 个自然周
        weeks = []
        cur = datetime.strptime(week_id, "%Y-%m-%d")
        for _ in range(4):
            weeks.append(cur.strftime("%Y-%m-%d"))
            cur -= timedelta(days=7)
        stats = db.query(WeekStat).filter(WeekStat.user_id == user.id, WeekStat.week_id.in_(weeks)).all()
        if not stats:
            return {
                "strength_rate": 0,
                "overload_count": 0,
                "protein_days": 0,
                "streak_weeks": 0,
                "load_up_kg": 0,
                "strength_done": 0,
                "strength_total": 12,
            }
        done = sum(s.strength_done for s in stats)
        total = sum(s.strength_total or 3 for s in stats)
        return {
            "strength_rate": round(100 * done / max(1, total)),
            "overload_count": sum(s.overload_count for s in stats),
            "protein_days": sum(s.protein_days for s in stats),
            "streak_weeks": streak_weeks(db, user.id, week_id),
            "load_up_kg": round(sum(s.load_up_kg for s in stats), 1),
            "strength_done": done,
            "strength_total": total,
        }

    stat = db.query(WeekStat).filter(WeekStat.user_id == user.id, WeekStat.week_id == week_id).first()
    if not stat:
        return {
            "strength_rate": 0,
            "overload_count": 0,
            "protein_days": 0,
            "streak_weeks": 0,
            "load_up_kg": 0,
            "strength_done": 0,
            "strength_total": 3,
        }
    return {
        "strength_rate": strength_rate(stat),
        "overload_count": stat.overload_count,
        "protein_days": stat.protein_days,
        "streak_weeks": streak_weeks(db, user.id, week_id),
        "load_up_kg": stat.load_up_kg,
        "strength_done": stat.strength_done,
        "strength_total": stat.strength_total,
        "valid_week": is_valid_week(stat),
        "streak_rule": "当周力量日 ≥2/3 才续周",
    }


def my_stats(db: Session, user: User, period: str = "week") -> dict:
    week_id = monday_ymd()
    agg = aggregate_period(db, user, period, week_id)
    return {
        "period": period,
        "week_id": week_id,
        "user_id": user.id,
        "nickname": user.nickname,
        "body_kg": user.body_kg,
        "body_band": body_band(user.body_kg),
        **agg,
    }


def score_for(dim: str, agg: dict) -> float:
    return {
        "strength": float(agg["strength_rate"]),
        "overload": float(agg["overload_count"]),
        "protein": float(agg["protein_days"]),
        "streak": float(agg["streak_weeks"]),
        "weight_class": float(agg["load_up_kg"]),
    }.get(dim, 0.0)


DIMS = ("strength", "overload", "protein", "streak", "weight_class")
PERIODS = ("week", "month")


def hour_bucket(dt: datetime | None = None) -> str:
    dt = dt or datetime.utcnow()
    return dt.strftime("%Y-%m-%dT%H")


def prev_hour_bucket(bucket: str) -> str:
    dt = datetime.strptime(bucket, "%Y-%m-%dT%H") - timedelta(hours=1)
    return dt.strftime("%Y-%m-%dT%H")


def _build_ranked_rows(db: Session, dim: str, period: str, band_filter: str | None = None) -> list[dict]:
    """band_filter: weight_class 时按体重区间过滤；None 表示全员（总榜）。"""
    week_id = monday_ymd()
    users = db.query(User).all()
    rows = []
    for u in users:
        if dim == "weight_class":
            band = body_band(u.body_kg)
            if band_filter and band != band_filter:
                continue
        agg = aggregate_period(db, u, period, week_id)
        rows.append(
            {
                "user_id": u.id,
                "openid": u.openid,
                "name": u.nickname or u.openid,
                "body_kg": u.body_kg,
                "body_band": body_band(u.body_kg),
                "score": score_for(dim, agg),
            }
        )
    rows.sort(key=lambda x: (-x["score"], x["name"]))
    counts = Counter(r["score"] for r in rows)
    ranked = []
    prev_score = None
    prev_rank = 0
    for i, r in enumerate(rows):
        if prev_score is None or r["score"] != prev_score:
            prev_rank = i + 1
            prev_score = r["score"]
        tie = counts[r["score"]] > 1
        ranked.append(
            {
                **r,
                "rank": prev_rank,
                "tied": tie,
                "rank_label": f"并列第 {prev_rank}" if tie else f"第 {prev_rank}",
            }
        )
    return ranked


def snapshot_exists(db: Session, bucket: str) -> bool:
    return db.query(RankSnapshot).filter(RankSnapshot.hour_bucket == bucket).first() is not None


def write_hourly_snapshots(db: Session, bucket: str | None = None) -> str:
    """落本小时全维度/周期快照；已存在则跳过。返回 hour_bucket。"""
    bucket = bucket or hour_bucket()
    if snapshot_exists(db, bucket):
        return bucket

    # 总榜 dims
    for period in PERIODS:
        for dim in DIMS:
            if dim == "weight_class":
                bands = {body_band(u.body_kg) for u in db.query(User).all()}
                for band in bands:
                    for row in _build_ranked_rows(db, dim, period, band_filter=band):
                        db.add(
                            RankSnapshot(
                                hour_bucket=bucket,
                                period=period,
                                dim=dim,
                                body_band=band,
                                user_id=row["user_id"],
                                rank=row["rank"],
                                score=row["score"],
                            )
                        )
            else:
                for row in _build_ranked_rows(db, dim, period, band_filter=None):
                    db.add(
                        RankSnapshot(
                            hour_bucket=bucket,
                            period=period,
                            dim=dim,
                            body_band="",
                            user_id=row["user_id"],
                            rank=row["rank"],
                            score=row["score"],
                        )
                    )
    db.commit()
    return bucket


def ensure_hourly_snapshots(db: Session) -> str:
    """确保当前小时有快照；若无上一小时则补一版演示用「上一小时」快照（名次略扰动）。"""
    cur = hour_bucket()
    prev = prev_hour_bucket(cur)
    if not snapshot_exists(db, prev):
        # 先写上一小时（基于当前数据），再轻微打乱名次感：复制后对部分用户 rank+1/-1 不方便
        # 简化：写完当前逻辑相同的 prev，再写 cur；演示种子在 seed 里扰动
        write_hourly_snapshots(db, prev)
    write_hourly_snapshots(db, cur)
    return cur


def _prev_ranks_map(db: Session, period: str, dim: str, body_band_key: str, prev_bucket: str) -> dict[int, int]:
    rows = (
        db.query(RankSnapshot)
        .filter(
            RankSnapshot.hour_bucket == prev_bucket,
            RankSnapshot.period == period,
            RankSnapshot.dim == dim,
            RankSnapshot.body_band == body_band_key,
        )
        .all()
    )
    return {r.user_id: r.rank for r in rows}


def _attach_delta(ranked: list[dict], prev_map: dict[int, int]) -> list[dict]:
    out = []
    for r in ranked:
        prev = prev_map.get(r["user_id"])
        if prev is None:
            delta = 0
            trend = "flat"
        else:
            delta = prev - r["rank"]  # 名次变小 = 上升，delta 为正
            trend = "up" if delta > 0 else ("down" if delta < 0 else "flat")
        out.append(
            {
                **r,
                "prev_rank": prev,
                "rank_delta": delta,
                "trend": trend,  # up | down | flat
            }
        )
    return out


def rank(
    db: Session,
    me: User,
    dim: str,
    period: str = "week",
    limit: int = 50,
) -> dict:
    cur_bucket = ensure_hourly_snapshots(db)
    prev_bucket = prev_hour_bucket(cur_bucket)

    band_key = body_band(me.body_kg) if dim == "weight_class" else ""
    band_filter = body_band(me.body_kg) if dim == "weight_class" else None
    ranked = _build_ranked_rows(db, dim, period, band_filter=band_filter)
    for r in ranked:
        r["is_me"] = r["user_id"] == me.id

    prev_map = _prev_ranks_map(db, period, dim, band_key, prev_bucket)
    ranked = _attach_delta(ranked, prev_map)

    mine = next((r for r in ranked if r["is_me"]), None)
    board_kind = "小榜" if dim == "weight_class" else "总榜"
    return {
        "dim": dim,
        "period": period,
        "board_kind": board_kind,
        "body_band": body_band(me.body_kg) if dim == "weight_class" else None,
        "snapshot_hour": cur_bucket,
        "prev_snapshot_hour": prev_bucket,
        "compare_hint": "较上一小时",
        "top3": ranked[:3],
        "me": mine,
        "full": ranked[:limit],
    }


def refresh_rank_snapshots(db: Session) -> dict:
    """强制写入当前小时快照（若已有则先删再写）。"""
    bucket = hour_bucket()
    db.query(RankSnapshot).filter(RankSnapshot.hour_bucket == bucket).delete()
    db.commit()
    write_hourly_snapshots(db, bucket)
    return {"snapshot_hour": bucket, "message": "本小时排名快照已更新"}


def list_following(db: Session, me: User) -> list[dict]:
    rows = (
        db.query(Follow, User)
        .join(User, Follow.followee_id == User.id)
        .filter(Follow.follower_id == me.id)
        .all()
    )
    return [
        {"user_id": u.id, "openid": u.openid, "name": u.nickname, "body_kg": u.body_kg, "body_band": body_band(u.body_kg)}
        for _, u in rows
    ]


def discover_users(db: Session, me: User) -> list[dict]:
    following_ids = {f.followee_id for f in db.query(Follow).filter(Follow.follower_id == me.id)}
    users = db.query(User).filter(User.id != me.id).all()
    return [
        {
            "user_id": u.id,
            "openid": u.openid,
            "name": u.nickname,
            "body_kg": u.body_kg,
            "body_band": body_band(u.body_kg),
            "following": u.id in following_ids,
        }
        for u in users
    ]


def toggle_follow(db: Session, me: User, followee_id: int) -> dict:
    if followee_id == me.id:
        raise HTTPException(400, "不能关注自己")
    target = db.get(User, followee_id)
    if not target:
        raise HTTPException(404, "用户不存在")
    row = (
        db.query(Follow)
        .filter(Follow.follower_id == me.id, Follow.followee_id == followee_id)
        .first()
    )
    if row:
        db.delete(row)
        db.commit()
        return {"following": False, "user_id": followee_id}
    db.add(Follow(follower_id=me.id, followee_id=followee_id))
    db.commit()
    return {"following": True, "user_id": followee_id}


def feed(db: Session, me: User) -> dict:
    following_ids = [f.followee_id for f in db.query(Follow).filter(Follow.follower_id == me.id)]
    if not following_ids:
        return {"items": [], "live_rail": [], "empty": True, "empty_hint": "去发现"}

    posts = (
        db.query(FeedPost, User)
        .join(User, FeedPost.user_id == User.id)
        .filter(FeedPost.user_id.in_(following_ids))
        .order_by(FeedPost.created_at.desc())
        .limit(50)
        .all()
    )
    items = []
    live = []
    for post, u in posts:
        liked = (
            db.query(FeedLike)
            .filter(FeedLike.post_id == post.id, FeedLike.user_id == me.id)
            .first()
            is not None
        )
        comments = (
            db.query(FeedComment, User)
            .join(User, FeedComment.user_id == User.id)
            .filter(FeedComment.post_id == post.id)
            .order_by(FeedComment.created_at.asc())
            .all()
        )
        c_out = [{"id": c.id, "user": cu.nickname, "text": c.text, "created_at": c.created_at} for c, cu in comments]
        for c in c_out[-3:]:
            live.append({"user": c["user"], "text": c["text"], "post_id": post.id})
        items.append(
            {
                "post_id": post.id,
                "user_id": u.id,
                "user": u.nickname,
                "openid": u.openid,
                "gains": json.loads(post.gains_json or "[]"),
                "likes": post.likes_count,
                "liked_by_me": liked,
                "comments": c_out,
            }
        )
    return {"items": items, "live_rail": live[:40], "empty": False}


def toggle_feed_like(db: Session, me: User, post_id: int) -> dict:
    post = db.get(FeedPost, post_id)
    if not post:
        raise HTTPException(404, "动态不存在")
    row = db.query(FeedLike).filter(FeedLike.post_id == post_id, FeedLike.user_id == me.id).first()
    if row:
        db.delete(row)
        post.likes_count = max(0, post.likes_count - 1)
        liked = False
    else:
        db.add(FeedLike(post_id=post_id, user_id=me.id))
        post.likes_count += 1
        liked = True
    db.commit()
    return {"liked": liked, "likes": post.likes_count}


def add_feed_comment(db: Session, me: User, post_id: int, text: str) -> dict:
    post = db.get(FeedPost, post_id)
    if not post:
        raise HTTPException(404, "动态不存在")
    c = FeedComment(post_id=post_id, user_id=me.id, text=text.strip())
    db.add(c)
    db.commit()
    db.refresh(c)
    return {
        "id": c.id,
        "user": me.nickname or me.openid,
        "text": c.text,
        "created_at": c.created_at,
        "post_id": post_id,
        "live": {"user": me.nickname or me.openid, "text": c.text},
    }
