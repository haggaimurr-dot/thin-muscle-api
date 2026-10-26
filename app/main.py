from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, home, market
from app.core.config import settings
from app.core.db import Base, SessionLocal, engine
from app.models import entities, home as home_models  # noqa: F401
from app.services.seed import seed_demo

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(market.router, prefix="/api/v1")
app.include_router(home.router, prefix="/api/v1")


def _rank_hourly_worker():
    import threading
    import time
    from app.services import home as home_svc

    def loop():
        time.sleep(3600)  # 启动时 seed 已落首屏快照，避免抢跑写空榜
        while True:
            try:
                db = SessionLocal()
                try:
                    home_svc.write_hourly_snapshots(db)
                finally:
                    db.close()
            except Exception:
                pass
            time.sleep(3600)

    threading.Thread(target=loop, name="rank-hourly", daemon=True).start()


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()
    _rank_hourly_worker()
