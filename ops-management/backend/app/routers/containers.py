"""
集装箱路由：录入、查询、编辑、删除、导入
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

from app.core.auth import get_current_user
from app.core.config import settings
from app.schemas import ContainerIn, ContainerOut, ContainerUpdate, PageResult, ImportResult
from app.services import container_service, import_service

router = APIRouter(prefix=f"{settings.API_PREFIX}/containers", tags=["集装箱"])


@router.get("", response_model=PageResult)
def list_containers(
    brand: Optional[str] = None,
    wh: Optional[str] = None,
    forwarder: Optional[str] = None,
    ship_co: Optional[str] = None,
    cargotype: Optional[int] = None,
    flag: Optional[int] = None,
    bl: Optional[str] = None,
    container_no: Optional[str] = None,
    ship_name: Optional[str] = None,
    pol: Optional[str] = None,
    pod: Optional[str] = None,
    status: Optional[str] = None,
    load_date_from: Optional[str] = None,
    load_date_to: Optional[str] = None,
    eta_from: Optional[str] = None,
    eta_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    _: dict = Depends(get_current_user),
):
    filters = dict(
        brand=brand, wh=wh, forwarder=forwarder, ship_co=ship_co,
        cargotype=cargotype, flag=flag, bl=bl, container_no=container_no,
        ship_name=ship_name, pol=pol, pod=pod, status=status,
        load_date_from=load_date_from, load_date_to=load_date_to,
        eta_from=eta_from, eta_to=eta_to,
    )
    total, items = container_service.query_containers(filters, page, page_size)
    return PageResult(total=total, page=page, page_size=page_size, items=items)


@router.get("/{id}", response_model=ContainerOut)
def get_container(id: int, _: dict = Depends(get_current_user)):
    row = container_service.get_container(id)
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    return row


@router.post("", response_model=ContainerOut)
def create_container(payload: ContainerIn, current: dict = Depends(get_current_user)):
    if container_service.exists_duplicate(
        payload.brand, payload.bl, payload.container_no
    ):
        raise HTTPException(status_code=409, detail="记录已存在（品牌+提单号+集装箱号重复）")
    return container_service.create_container(payload.model_dump(), current["usercode"])


@router.put("/{id}", response_model=ContainerOut)
def update_container(id: int, payload: ContainerIn, _: dict = Depends(get_current_user)):
    if not container_service.get_container(id):
        raise HTTPException(status_code=404, detail="记录不存在")
    return container_service.update_container(payload.model_dump(), id)


@router.delete("/{id}")
def delete_container(id: int, _: dict = Depends(get_current_user)):
    if not container_service.delete_container(id):
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True}


@router.post("/{id}/reset-flag")
def reset_flag(id: int, _: dict = Depends(get_current_user)):
    """把状态从100重置为0，使记录恢复自动同步"""
    if not container_service.get_container(id):
        raise HTTPException(status_code=404, detail="记录不存在")
    changed = container_service.reset_flag(id)
    return {"ok": True, "changed": changed, "flag": 0 if changed else None}


@router.post("/import", response_model=ImportResult)
async def import_excel(
    file: UploadFile = File(...),
    current: dict = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="请上传 .xlsx 或 .xls 文件")
    content = await file.read()
    records, errors = import_service.parse_excel(content)
    result = import_service.import_records(records, current["usercode"])
    # 合并解析阶段错误
    result["errors"] = errors + result["errors"]
    result["skipped_invalid"] += len(errors)
    return result
