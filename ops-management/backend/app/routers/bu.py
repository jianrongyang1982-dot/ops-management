"""
BU 业务单元路由：BU 定义 CRUD/导入导出 + BU-品牌关系设定
数据均在 bidb 库，需登录。
"""
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.core.config import settings
from app.services import bu_service as svc

router = APIRouter(prefix=f"{settings.API_PREFIX}/bu", tags=["BU业务单元"])


# ---------------- 请求模型 ----------------
class BuIn(BaseModel):
    bu_code: str
    bu_name: Optional[str] = None
    bu_name_en: Optional[str] = None
    status: int = 1
    sort_no: int = 0
    remark: Optional[str] = None


class BuBrandItemIn(BaseModel):
    brand_name: str
    brandid: Optional[str] = None
    brand_note: Optional[str] = None
    is_primary: int = 0
    sort_no: int = 0
    remark: Optional[str] = None


class BuBrandSaveIn(BaseModel):
    bu_code: str
    items: list[BuBrandItemIn] = []


# ---------------- BU 定义 ----------------
@router.get("/list")
def list_bu(keyword: Optional[str] = None, status: Optional[int] = None,
            page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
            _: dict = Depends(get_current_user)):
    return svc.bu_list(keyword, status, page, page_size)


@router.get("/options")
def bu_options(enabled_only: bool = True, _: dict = Depends(get_current_user)):
    return svc.bu_options(enabled_only)


@router.post("/")
def create_bu(payload: BuIn, user: dict = Depends(get_current_user)):
    try:
        return svc.bu_create(payload.model_dump(), user.get("usercode", "sys"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/export")
def export_bu(keyword: Optional[str] = None, status: Optional[int] = None,
              _: dict = Depends(get_current_user)):
    content = svc.export_excel(keyword, status)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="bu_def.xlsx"'},
    )


@router.post("/import")
async def import_bu(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="请上传 .xlsx 文件")
    try:
        content = await file.read()
        return svc.import_excel(content, user.get("usercode", "sys"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------- BU-品牌关系 ----------------
@router.get("/brand-options")
def brand_options(_: dict = Depends(get_current_user)):
    return svc.brand_options()


@router.put("/{row_id}")
def update_bu(row_id: int, payload: BuIn, user: dict = Depends(get_current_user)):
    try:
        row = svc.bu_update(row_id, payload.model_dump(), user.get("usercode", "sys"))
        if not row:
            raise HTTPException(status_code=404, detail="BU 不存在")
        return row
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{row_id}")
def delete_bu(row_id: int, _: dict = Depends(get_current_user)):
    return svc.bu_delete(row_id)


@router.get("/{bu_code}/brands")
def list_bu_brands(bu_code: str, _: dict = Depends(get_current_user)):
    return svc.bu_brand_list(bu_code)


@router.post("/{bu_code}/brands")
def save_bu_brands(bu_code: str, payload: BuBrandSaveIn,
                   user: dict = Depends(get_current_user)):
    data = payload.model_dump()
    data["bu_code"] = bu_code
    try:
        return svc.bu_brand_save(data, user.get("usercode", "sys"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/brand-rel/{row_id}")
def delete_bu_brand(row_id: int, _: dict = Depends(get_current_user)):
    return svc.bu_brand_delete(row_id)
