from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.entities import User


def get_current_user(
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> User:
    """开发期用头鉴权；上线换成微信 code2session + JWT。"""
    if x_user_id is None:
        raise HTTPException(401, "缺少 X-User-Id（开发头）")
    user = db.get(User, x_user_id)
    if not user:
        raise HTTPException(401, "用户不存在")
    return user
