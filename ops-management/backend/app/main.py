"""
运营管理系统 - FastAPI 主程序
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.routers import auth, dict, containers, sync, dashboard, performance
from app.services import freightower_service, logistics_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def scheduled_sync():
    """定时同步任务：飞驼(未完成数据) + 物流(仅商品且未完成)"""
    logger.info("定时同步任务开始")
    try:
        result = freightower_service.sync_all()
        logger.info(
            "定时[飞驼]完成：扫描%s 回写%s 失败%s",
            result.get("scanned"), result.get("synced"), result.get("failed"),
        )
    except Exception as e:
        logger.exception("定时[飞驼]同步异常：%s", e)
    try:
        result = logistics_service.sync_all_for_product()
        logger.info(
            "定时[物流]完成：扫描%s 同步%s 失败%s",
            result.get("scanned"), result.get("synced"), result.get("failed"),
        )
    except Exception as e:
        logger.exception("定时[物流]同步异常：%s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时注册定时任务
    scheduler.add_job(
        scheduled_sync,
        "interval",
        minutes=settings.SYNC_INTERVAL_MINUTES,
        id="freightower_sync",
        replace_existing=True,
        next_run_time=None,  # 不立即执行，等一个周期
    )
    scheduler.start()
    logger.info("定时任务已启动，每 %s 分钟同步一次", settings.SYNC_INTERVAL_MINUTES)
    yield
    scheduler.shutdown(wait=False)
    logger.info("定时任务已关闭")


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dict.router)
app.include_router(containers.router)
app.include_router(sync.router)
app.include_router(dashboard.router)
app.include_router(performance.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/container-template.xlsx", include_in_schema=False)
def download_template():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "container-template.xlsx")
    if os.path.exists(path):
        return FileResponse(
            path,
            filename="container_template.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return {"detail": "模板文件不存在"}


# 静态文件托管（前端构建产物）
import os
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
ASSETS_DIR = os.path.join(STATIC_DIR, "assets")
if os.path.isdir(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

if os.path.isfile(os.path.join(STATIC_DIR, "index.html")):
    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
