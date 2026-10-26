import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.entities import MarketListing, User
from app.models.home import FeedPost, Follow, RankSnapshot, WeekStat
from app.services.home import hour_bucket, monday_ymd, prev_hour_bucket, write_hourly_snapshots

DEMO_DAYS = [
    {
        "day_type": "push",
        "session": "both",
        "exercises": [
            {"name": "板俯卧撑", "sets": "3", "reps": "4–6", "load": "自重", "notes": ""},
            {"name": "哑铃卧推", "sets": "3", "reps": "4–6", "load": "18kg", "notes": ""},
            {"name": "哑铃肩推", "sets": "3", "reps": "4–6", "load": "12kg", "notes": ""},
        ],
    },
    {
        "day_type": "pull",
        "session": "both",
        "exercises": [
            {"name": "引体向上（可辅助）", "sets": "3", "reps": "4–6", "load": "弹力带", "notes": ""},
            {"name": "哑铃划船", "sets": "3", "reps": "4–6", "load": "16kg", "notes": ""},
        ],
    },
    {
        "day_type": "legs",
        "session": "both",
        "exercises": [
            {"name": "哑铃深蹲", "sets": "3", "reps": "4–6", "load": "20kg×2", "notes": ""},
            {"name": "哑铃罗马尼亚硬拉", "sets": "3", "reps": "4–6", "load": "18kg×2", "notes": ""},
        ],
    },
]


def _seed_market(db: Session, sellers: list[User]) -> None:
    if db.query(MarketListing).count() > 0:
        return
    demos = [
        MarketListing(
            seller_id=sellers[0].id,
            kind="plan",
            title="哑铃家用 · 推拉腿四周方案",
            level="进阶",
            body_range="70–85kg",
            price_fen=2990,
            cover_url="https://cdn.example.com/cover/akai-week.jpg",
            media_json=json.dumps(
                [
                    {"type": "image", "url": "https://cdn.example.com/a1.jpg", "title": "推日"},
                    {"type": "video", "url": "https://cdn.example.com/a1.mp4", "title": "肩推"},
                ],
                ensure_ascii=False,
            ),
            body_text="家用哑铃推拉腿，复刻后可拼装。",
            cycle="week",
            week_index=2,
            days_json=json.dumps(DEMO_DAYS, ensure_ascii=False),
            rhythm="周一推 / 周三拉 / 周五腿 · 早晚两练",
            likes_count=128,
        ),
        MarketListing(
            seller_id=sellers[1].id,
            kind="plan",
            title="女生入门 · 全身月计划",
            level="入门",
            body_range="50–65kg",
            price_fen=1990,
            cover_url="https://cdn.example.com/cover/linxia-month.jpg",
            media_json=json.dumps([{"type": "image", "url": "https://cdn.example.com/l1.jpg", "title": ""}], ensure_ascii=False),
            body_text="入门月计划，重量可控。",
            cycle="month",
            week_index=1,
            days_json=json.dumps(DEMO_DAYS, ensure_ascii=False),
            rhythm="推拉腿隔天 · 恢复日跳绳散步",
            likes_count=86,
        ),
        MarketListing(
            seller_id=sellers[2].id,
            kind="lesson",
            title="如何做俯卧撑",
            level="入门",
            body_range="不限",
            price_fen=990,
            cover_url="https://cdn.example.com/cover/pushup.jpg",
            media_json=json.dumps(
                [{"type": "video", "url": "https://cdn.example.com/pushup-demo.mp4", "title": "示范"}],
                ensure_ascii=False,
            ),
            body_text="从跪姿到标准俯卧撑的进阶教学。",
            topic="俯卧撑",
            skill_tags_json=json.dumps(["胸", "核心", "入门"], ensure_ascii=False),
            steps_json=json.dumps(["手略宽于肩", "身体一条线", "胸口接近地面再推起"], ensure_ascii=False),
            cues_json=json.dumps(["肘约 45°", "臀不塌"], ensure_ascii=False),
            demo_media_json=json.dumps(
                [{"type": "video", "url": "https://cdn.example.com/pushup-demo.mp4", "title": "标准示范"}],
                ensure_ascii=False,
            ),
            likes_count=204,
        ),
    ]
    db.add_all(demos)


def _seed_home(db: Session, by_openid: dict[str, User]) -> None:
    if db.query(WeekStat).count() > 0:
        return

    week = monday_ymd()
    prev = (datetime.strptime(week, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    prev2 = (datetime.strptime(week, "%Y-%m-%d") - timedelta(days=14)).strftime("%Y-%m-%d")

    # strength_done / overload / protein / load_up aligned loosely with frontend RANK_USERS
    table = [
        ("demo_me", [(week, 2, 2, 4, 4.0), (prev, 2, 1, 3, 2.0)]),
        ("demo_akai", [(week, 3, 5, 6, 8.0), (prev, 3, 4, 5, 6.0), (prev2, 3, 3, 5, 5.0)]),
        ("demo_linxia", [(week, 2, 3, 5, 3.0), (prev, 2, 2, 4, 2.0)]),
        ("demo_laozhou", [(week, 3, 6, 5, 10.0), (prev, 3, 5, 5, 8.0), (prev2, 3, 4, 4, 7.0), ((datetime.strptime(week, "%Y-%m-%d") - timedelta(days=21)).strftime("%Y-%m-%d"), 3, 3, 4, 5.0)]),
        ("demo_yu", [(week, 1, 1, 3, 2.0)]),
        ("demo_kun", [(week, 2, 4, 4, 5.0), (prev, 2, 2, 3, 3.0)]),
        ("demo_ming", [(week, 3, 3, 7, 6.0), (prev, 2, 2, 5, 4.0)]),
        ("demo_lei", [(week, 1, 2, 2, 3.0)]),
    ]
    gains = {
        "demo_akai": ["哑铃卧推 18→20kg", "肩推 10→12kg"],
        "demo_linxia": ["引体辅助 减一档", "深蹲 8→10 次"],
        "demo_laozhou": ["RDL 20→22kg", "分腿蹲 双侧对称"],
        "demo_yu": ["板俯卧撑 跪姿→标准", "蛋白 5/7 天达标"],
        "demo_kun": ["哑铃划船 14→16kg"],
    }
    for openid, weeks in table:
        u = by_openid[openid]
        for i, (wid, sd, ov, pr, lu) in enumerate(weeks):
            db.add(
                WeekStat(
                    user_id=u.id,
                    week_id=wid,
                    strength_done=sd,
                    strength_total=3,
                    overload_count=ov,
                    protein_days=pr,
                    load_up_kg=lu,
                    gains_json=json.dumps(gains.get(openid, []), ensure_ascii=False) if i == 0 else "[]",
                )
            )

    me = by_openid["demo_me"]
    # 默认关注阿凯、林夏
    db.add(Follow(follower_id=me.id, followee_id=by_openid["demo_akai"].id))
    db.add(Follow(follower_id=me.id, followee_id=by_openid["demo_linxia"].id))

    for openid, like_n in [("demo_akai", 24), ("demo_linxia", 18), ("demo_laozhou", 31), ("demo_yu", 12), ("demo_kun", 9)]:
        u = by_openid[openid]
        db.add(
            FeedPost(
                user_id=u.id,
                week_id=week,
                gains_json=json.dumps(gains.get(openid, ["本周稳步推进"]), ensure_ascii=False),
                likes_count=like_n,
            )
        )

    # 小时快照：先 flush 周进度，再落快照；上一小时让「我」名次更差以便演示 ↑
    db.flush()
    cur = hour_bucket()
    prev = prev_hour_bucket(cur)
    db.query(RankSnapshot).filter(RankSnapshot.hour_bucket.in_([prev, cur])).delete()
    db.commit()
    write_hourly_snapshots(db, prev)
    me = by_openid["demo_me"]
    for snap in db.query(RankSnapshot).filter(
        RankSnapshot.hour_bucket == prev,
        RankSnapshot.user_id == me.id,
    ):
        snap.rank = min(99, snap.rank + 2)
    db.commit()
    write_hourly_snapshots(db, cur)


def seed_demo(db: Session) -> None:
    if db.query(User).count() == 0:
        users = [
            User(openid="demo_akai", nickname="阿凯", body_kg=77, level="进阶"),
            User(openid="demo_linxia", nickname="林夏", body_kg=58, level="入门"),
            User(openid="demo_laozhou", nickname="老周", body_kg=82, level="进阶"),
            User(openid="demo_me", nickname="我", body_kg=77, level="进阶"),
            User(openid="demo_yu", nickname="小鱼", body_kg=55, level="入门"),
            User(openid="demo_kun", nickname="坤", body_kg=75, level="进阶"),
            User(openid="demo_ming", nickname="阿明", body_kg=78, level="进阶"),
            User(openid="demo_lei", nickname="雷子", body_kg=80, level="入门"),
        ]
        db.add_all(users)
        db.flush()
        _seed_market(db, users[:3])
        by = {u.openid: u for u in users}
        _seed_home(db, by)
        db.commit()
        return

    # 已有用户时仍可补首页种子
    by = {u.openid: u for u in db.query(User).all()}
    needed = ["demo_yu", "demo_kun", "demo_ming", "demo_lei"]
    for oid, name, kg, lv in [
        ("demo_yu", "小鱼", 55, "入门"),
        ("demo_kun", "坤", 75, "进阶"),
        ("demo_ming", "阿明", 78, "进阶"),
        ("demo_lei", "雷子", 80, "入门"),
    ]:
        if oid not in by:
            u = User(openid=oid, nickname=name, body_kg=kg, level=lv)
            db.add(u)
            db.flush()
            by[oid] = u
    _seed_market(db, [by[x] for x in ("demo_akai", "demo_linxia", "demo_laozhou") if x in by])
    _seed_home(db, by)
    db.commit()
