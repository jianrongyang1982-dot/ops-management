"""
Pydantic 数据模型（请求/响应）
"""
from datetime import datetime, date
from typing import Optional, List, Any


from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    usercode: str = Field(..., min_length=1, description="用户名")
    # 前端提交的是第一层哈希 sha256(usercode_password)，64 位十六进制；
    # 后端同时兼容明文（服务端自行计算第一层），故不限制长度与格式。
    password: str = Field(..., description="密码或其第一层 SHA-256 哈希")


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usercode: str
    accountname: str
    display_name: str


class UserOut(BaseModel):
    usercode: str
    accountname: str
    display_name: str


class ModuleOut(BaseModel):
    key: str
    name: str
    icon: Optional[str] = None
    path: str


class DictItem(BaseModel):
    value: str
    label: str


class ContainerIn(BaseModel):
    """录入/编辑集装箱"""
    sn: Optional[int] = None
    brand: str
    wh: Optional[str] = None
    forwarder: Optional[str] = None
    cargotype: Optional[int] = None
    bl: Optional[str] = None
    ship_co: Optional[str] = None
    ship_name: Optional[str] = None
    container_no: str = Field(..., min_length=1, description="集装箱号必填")
    warehousebinno: Optional[str] = None
    pol: Optional[str] = None
    pod: Optional[str] = None
    load_date: Optional[datetime] = None
    eta: Optional[datetime] = None
    remark: Optional[str] = None


class ContainerUpdate(ContainerIn):
    id: int


class ContainerOut(BaseModel):
    id: int
    sn: Optional[int] = None
    brand: Optional[str] = None
    brand_name: Optional[str] = None
    wh: Optional[str] = None
    forwarder: Optional[str] = None
    cargotype: Optional[int] = None
    bl: Optional[str] = None
    ship_co: Optional[str] = None
    ship_name: Optional[str] = None
    voyage: Optional[str] = None
    container_no: Optional[str] = None
    warehousebinno: Optional[str] = None
    pol: Optional[str] = None
    pod: Optional[str] = None
    load_date: Optional[datetime] = None
    eta: Optional[datetime] = None
    period: Optional[int] = None
    stspdate: Optional[date] = None
    loaddate: Optional[date] = None
    plandate: Optional[date] = None
    acdate: Optional[date] = None
    stcsdate: Optional[date] = None
    rcvedate: Optional[date] = None
    # 下单日期（WMS Bill_Date，物流跟踪回写）
    billdate: Optional[date] = None
    # WMS 状态标志：收货/上架是否完成（100=完成，0=未完成）
    receiveflag: Optional[int] = None
    PutawayFlag: Optional[int] = None
    # 派生天数：实际天数=提柜日期(stcsdate)-装船日期(loaddate)；计划天数=计划到达(plandate)-装船日期
    actual_days: Optional[int] = None
    plan_days: Optional[int] = None
    # 物流验收时间（库表字段为驼峰命名）
    acceptanceStartTime: Optional[datetime] = None
    acceptanceCompleteTime: Optional[datetime] = None
    orderCloseTime: Optional[datetime] = None
    earliestShelfTime: Optional[datetime] = None
    latestShelfTime: Optional[datetime] = None
    url: Optional[str] = None
    # 飞驼当前状态（JSON 字符串）及各节点计划标记（JSON 字符串）
    currentStatus: Optional[str] = None
    statusEsti: Optional[str] = None
    remark: Optional[str] = None
    ob_no: Optional[str] = None
    flag: Optional[int] = None
    creator: Optional[str] = None
    createtime: Optional[datetime] = None
    status: Optional[str] = None
    delay_days: Optional[int] = None


class MessageOut(BaseModel):
    message: str


class PageResult(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ContainerOut]


class ImportResult(BaseModel):
    total_rows: int
    imported: int
    skipped_duplicate: int
    skipped_invalid: int
    errors: List[str] = []


class SyncResult(BaseModel):
    success: bool
    message: str
    scanned: int = 0
    synced: int = 0
    skipped: int = 0
    failed: int = 0
    details: List[dict] = []
