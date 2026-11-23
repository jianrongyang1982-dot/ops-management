"""
同步路由：手动触发、查看状态
"""
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.core.config import settings
from app.schemas import SyncResult
from app.services import freightower_service as ft
from app.services import logistics_service as logi

router = APIRouter(prefix=f"{settings.API_PREFIX}/sync", tags=["飞驼同步"])


@router.get("/log")
def get_freightower_log(lines: int = 200, _: dict = Depends(get_current_user)):
    """查看飞驼请求日志（末尾 N 行）"""
    from app.core.freightower_logger import read_log
    return {"lines": lines, "content": read_log(lines)}


@router.post("/run", response_model=SyncResult)
def run_sync(_: dict = Depends(get_current_user)):
    try:
        return ft.sync_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败：{e}")


@router.post("/row/{id}")
def sync_row(id: int, _: dict = Depends(get_current_user)):
    """单行调用飞驼：先按提单号，失败按柜号+船公司+起运港，命中回写 url 与六个日期"""
    try:
        res = ft.sync_single_row(id)
        if not res.get("success") and "不存在" in res.get("message", ""):
            raise HTTPException(status_code=404, detail=res.get("message"))
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调用失败：{e}")


@router.post("/logistics/{id}")
def sync_logistics_row(id: int, _: dict = Depends(get_current_user)):
    """单行物流跟踪：按柜号+品牌查询 WMS 验收数据，回写三个物流时间字段"""
    try:
        res = logi.sync_single_row(id)
        if not res.get("success") and "不存在" in res.get("message", ""):
            raise HTTPException(status_code=404, detail=res.get("message"))
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"物流查询失败：{e}")


@router.post("/bl/{bl}")
def sync_single_bl(bl: str, _: dict = Depends(get_current_user)):
    """手动跟踪单个提单号（不改库，仅返回解析结果预览）"""
    try:
        result = ft.query_tracking(bl)
        if not result:
            return {"bl": bl, "found": False}
        fields = ft.parse_tracking(result)
        return {
            "bl": bl,
            "found": True,
            "fields": {k: str(v) for k, v in fields.items()},
            "statusCategory": result.get("statusCategory"),
            "description": result.get("statusDescription"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
