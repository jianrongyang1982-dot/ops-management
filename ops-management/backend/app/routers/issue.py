"""
系统报障与需求管理路由
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.config import settings
from app.schemas import MessageOut
from app.services import issue_service as svc

router = APIRouter(prefix=f"{settings.API_PREFIX}/issue", tags=["系统报障"])


# ---------------------------------------------------------------------------
# 请求模型
# ---------------------------------------------------------------------------

class IssueCreateIn(BaseModel):
    title: str = Field(..., min_length=1, description="需求名称/标题")
    description: str = ""
    issue_type: int = Field(1, description="1=需求 2=BUG")
    module: str = ""
    priority: int = Field(3, description="1紧急 2高 3中 4低")
    requirement_json: str = Field("", description="需求结构化字段 JSON 字符串，仅需求类型使用")


class AssignIn(BaseModel):
    assignee: str = Field(..., min_length=1, description="处理人 usercode")


class ProcessIn(BaseModel):
    content: str = ""


class VerifyIn(BaseModel):
    passed: bool
    remark: str = ""


class CancelIn(BaseModel):
    remark: str = ""


class RoleCfgIn(BaseModel):
    postcode: str = Field(..., min_length=1)
    postname: str = ""
    role: str = Field(..., description="IT_ADMIN / HANDLER")


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def _ctx(current_user: dict):
    uc = (current_user.get("usercode") or "").strip()
    roles_info = svc.user_roles(uc)
    return uc, roles_info["roles"]


def _require_it(roles: list):
    if "IT_ADMIN" not in roles:
        raise HTTPException(status_code=403, detail="只有 IT 管理员可以操作")


def _handle_error(exc: Exception):
    msg = str(exc)
    if "数据表尚未创建" in msg or "需求字段尚未创建" in msg:
        raise HTTPException(status_code=503, detail=msg)
    if any(k in msg for k in ("不存在", "不能为空", "只允许", "只有", "不支持", "不能超过", "必须", "状态不允许", "已配置", "当前状态")):
        raise HTTPException(status_code=400, detail=msg)
    raise HTTPException(status_code=500, detail=msg)


# ---------------------------------------------------------------------------
# 工单列表 / 详情 / 统计
# ---------------------------------------------------------------------------

@router.get("/list")
def api_list(
    scope: str = "my",
    status: Optional[int] = None,
    issue_type: Optional[int] = None,
    priority: Optional[int] = None,
    keyword: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    if scope not in ("my", "monitor", "assigned"):
        raise HTTPException(status_code=400, detail="scope 无效")
    uc, _ = _ctx(current_user)
    try:
        return svc.list_issues(scope, uc, status, issue_type, priority, keyword, page, page_size)
    except Exception as exc:
        _handle_error(exc)


@router.get("/my-role")
def api_my_role(current_user: dict = Depends(get_current_user)):
    """当前用户角色（IT管理员 / 处理人 / 提交人）。"""
    uc = (current_user.get("usercode") or "").strip()
    try:
        return svc.my_role(uc)
    except Exception as exc:
        _handle_error(exc)


@router.get("/dashboard")
def api_dashboard(scope: str = "my", current_user: dict = Depends(get_current_user)):
    """状态统计卡片：monitor 场景统计全部，其余只统计自己。"""
    uc, roles = _ctx(current_user)
    try:
        is_all = scope == "monitor" or "IT_ADMIN" in roles
        return svc.dashboard_counts(uc, is_all)
    except Exception as exc:
        _handle_error(exc)


@router.post("/create")
def api_create(payload: IssueCreateIn, current_user: dict = Depends(get_current_user)):
    """纯文本创建（兼容旧调用）。"""
    uc, _ = _ctx(current_user)
    try:
        return svc.create_issue(uc, payload.title, payload.description,
                                payload.issue_type, payload.module, payload.priority,
                                payload.requirement_json)
    except Exception as exc:
        _handle_error(exc)


@router.post("/create-with-files")
async def api_create_with_files(
    title: str = Form(..., min_length=1),
    description: str = Form(""),
    issue_type: int = Form(1),
    module: str = Form(""),
    priority: int = Form(3),
    requirement_json: str = Form("", description="需求结构化字段 JSON 字符串"),
    files: list[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user),
):
    """新建报障并同时上传附件（一次性提交）。"""
    uc, _ = _ctx(current_user)
    try:
        payload = []
        for f in files:
            data = await f.read()
            if data:
                payload.append((f.filename or "file", data))
        return svc.create_issue_with_files(
            uc, title, description, issue_type, module, priority, payload,
            requirement_json
        )
    except Exception as exc:
        _handle_error(exc)


# ---------------------------------------------------------------------------
# 状态流转
# ---------------------------------------------------------------------------

@router.post("/{issue_id}/assign")
def api_assign(issue_id: int, payload: AssignIn, current_user: dict = Depends(get_current_user)):
    uc, roles = _ctx(current_user)
    try:
        return svc.assign_issue(issue_id, payload.assignee, uc, roles)
    except Exception as exc:
        _handle_error(exc)


@router.post("/{issue_id}/start")
def api_start(issue_id: int, current_user: dict = Depends(get_current_user)):
    uc, roles = _ctx(current_user)
    try:
        return svc.start_issue(issue_id, uc, roles)
    except Exception as exc:
        _handle_error(exc)


@router.post("/{issue_id}/process")
def api_process(issue_id: int, payload: ProcessIn, current_user: dict = Depends(get_current_user)):
    uc, roles = _ctx(current_user)
    try:
        return svc.process_issue(issue_id, uc, roles, payload.content)
    except Exception as exc:
        _handle_error(exc)


@router.post("/{issue_id}/verify")
def api_verify(issue_id: int, payload: VerifyIn, current_user: dict = Depends(get_current_user)):
    uc, roles = _ctx(current_user)
    try:
        return svc.verify_issue(issue_id, uc, roles, payload.passed, payload.remark)
    except Exception as exc:
        _handle_error(exc)


@router.post("/{issue_id}/cancel")
def api_cancel(issue_id: int, payload: CancelIn, current_user: dict = Depends(get_current_user)):
    uc, roles = _ctx(current_user)
    try:
        return svc.cancel_issue(issue_id, uc, roles, payload.remark)
    except Exception as exc:
        _handle_error(exc)


@router.post("/{issue_id}/force-close")
def api_force_close(issue_id: int, payload: CancelIn, current_user: dict = Depends(get_current_user)):
    uc, roles = _ctx(current_user)
    try:
        return svc.force_close(issue_id, uc, roles, payload.remark)
    except Exception as exc:
        _handle_error(exc)


# ---------------------------------------------------------------------------
# 附件
# ---------------------------------------------------------------------------

@router.post("/upload")
async def api_upload(
    issue_id: int = Form(..., ge=1),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    uc, roles = _ctx(current_user)
    if not svc.can_view_issue(issue_id, uc, roles):
        raise HTTPException(status_code=403, detail="无权操作该工单")
    try:
        data = await file.read()
        return svc.save_attachment(issue_id, file.filename or "file", data, uc)
    except Exception as exc:
        _handle_error(exc)


@router.get("/attachment/{attach_id}/download")
def api_download(attach_id: int, current_user: dict = Depends(get_current_user)):
    uc, roles = _ctx(current_user)
    try:
        path, name = svc.attachment_path(attach_id)
    except Exception as exc:
        _handle_error(exc)
    return FileResponse(path, filename=name)


# ---------------------------------------------------------------------------
# 角色配置
# ---------------------------------------------------------------------------

# 角色配置对所有登录用户开放：能进入该页面的用户即可配置（不再限定 IT_ADMIN）

@router.get("/roles/erp-posts")
def api_erp_posts(keyword: str = "", current_user: dict = Depends(get_current_user)):
    try:
        return {"items": svc.erp_posts(keyword)}
    except Exception as exc:
        _handle_error(exc)


@router.get("/roles")
def api_roles(current_user: dict = Depends(get_current_user)):
    try:
        return {"items": svc.role_configs()}
    except Exception as exc:
        _handle_error(exc)


@router.post("/roles", response_model=MessageOut)
def api_add_role(payload: RoleCfgIn, current_user: dict = Depends(get_current_user)):
    try:
        svc.add_role_config(payload.postcode, payload.postname, payload.role)
        return MessageOut(message="角色配置已添加")
    except Exception as exc:
        _handle_error(exc)


@router.delete("/roles/{cfg_id}", response_model=MessageOut)
def api_del_role(cfg_id: int, current_user: dict = Depends(get_current_user)):
    try:
        svc.delete_role_config(cfg_id)
        return MessageOut(message="角色配置已删除")
    except Exception as exc:
        _handle_error(exc)


@router.get("/handlers")
def api_handlers(current_user: dict = Depends(get_current_user)):
    """可选处理人列表（配置为 HANDLER 岗位的 ERP 用户）。"""
    try:
        return {"items": svc.handler_options()}
    except Exception as exc:
        _handle_error(exc)


# ---------------------------------------------------------------------------
# 站内消息
# ---------------------------------------------------------------------------

@router.get("/messages")
def api_messages(
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    uc, _ = _ctx(current_user)
    try:
        return svc.messages(uc, unread_only, page, page_size)
    except Exception as exc:
        _handle_error(exc)


@router.post("/messages/{msg_id}/read", response_model=MessageOut)
def api_msg_read(msg_id: int, current_user: dict = Depends(get_current_user)):
    uc, _ = _ctx(current_user)
    try:
        svc.mark_read(msg_id, uc)
        return MessageOut(message="已标记为已读")
    except Exception as exc:
        _handle_error(exc)


@router.post("/messages/read-all", response_model=MessageOut)
def api_msg_read_all(current_user: dict = Depends(get_current_user)):
    uc, _ = _ctx(current_user)
    try:
        svc.mark_all_read(uc)
        return MessageOut(message="全部消息已标记为已读")
    except Exception as exc:
        _handle_error(exc)


# ---------------------------------------------------------------------------
# 工单详情（放在所有静态路径之后，避免 /{issue_id} 抢先匹配 /roles、/messages）
# ---------------------------------------------------------------------------

@router.get("/{issue_id}")
def api_detail(issue_id: int, current_user: dict = Depends(get_current_user)):
    uc, roles = _ctx(current_user)
    if not svc.can_view_issue(issue_id, uc, roles):
        raise HTTPException(status_code=403, detail="无权查看该工单")
    try:
        return svc.issue_detail(issue_id)
    except Exception as exc:
        _handle_error(exc)
