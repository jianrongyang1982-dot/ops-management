"""
绩效管理路由：绩效系数（westlake_WorkPrice）查询、增删改、导入导出
"""
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.core.config import settings
from app.services import performance_service, employee_performance_service

router = APIRouter(prefix=f"{settings.API_PREFIX}/performance", tags=["绩效管理"])


class CoefficientIn(BaseModel):
    ownerid: str
    cateid: Optional[str] = None
    catename: Optional[str] = None
    price1: float = 0
    price2: float = 0
    price3: float = 0
    workmode: Optional[str] = "1"


@router.get("/coefficients")
def list_coefficients(
    ownerid: Optional[str] = None,
    cateid: Optional[str] = None,
    catename: Optional[str] = None,
    workmode: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    _: dict = Depends(get_current_user),
):
    filters = dict(ownerid=ownerid, cateid=cateid, catename=catename, workmode=workmode)
    total, items = performance_service.query(filters, page, page_size)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/coefficients/workmodes")
def workmode_options(_: dict = Depends(get_current_user)):
    return performance_service.get_workmode_options()


@router.get("/categories")
def category_options(_: dict = Depends(get_current_user)):
    return performance_service.get_category_options()


@router.get("/coefficients/export")
def export_coefficients(
    ownerid: Optional[str] = None,
    cateid: Optional[str] = None,
    catename: Optional[str] = None,
    workmode: Optional[str] = None,
    _: dict = Depends(get_current_user),
):
    filters = dict(ownerid=ownerid, cateid=cateid, catename=catename, workmode=workmode)
    content = performance_service.export_excel(filters)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="workprice.xlsx"'},
    )


@router.post("/coefficients/import")
async def import_coefficients(
    file: UploadFile = File(...),
    _: dict = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="请上传 .xlsx 文件")
    try:
        content = await file.read()
        return performance_service.import_excel(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/coefficients")
def create_coefficient(payload: CoefficientIn, _: dict = Depends(get_current_user)):
    try:
        return performance_service.create(payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/coefficients/{id}")
def update_coefficient(id: int, payload: CoefficientIn, _: dict = Depends(get_current_user)):
    try:
        row = performance_service.update(id, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    return row


@router.delete("/coefficients/{id}")
def delete_coefficient(id: int, _: dict = Depends(get_current_user)):
    if not performance_service.delete(id):
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True}


@router.get("/employees")
def list_employee_performance(
    ownerid: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    operator: Optional[str] = None,
    workmode: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    _: dict = Depends(get_current_user),
):
    if not start_date:
        raise HTTPException(status_code=400, detail="请选择开始日期后再查询")
    filters = dict(
        ownerid=ownerid, start_date=start_date, end_date=end_date,
        operator=operator, workmode=workmode,
    )
    total, items = employee_performance_service.query(filters, page, page_size)
    return {"total": total, "page": page, "page_size": page_size, "items": items}
