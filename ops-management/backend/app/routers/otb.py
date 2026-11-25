"""
OTB 采买与商品补货 路由

所有接口都以 bidb 库表为数据源，需登录（Depends get_current_user）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.core.config import settings
from app.services import otb_service as svc

router = APIRouter(prefix=f"{settings.API_PREFIX}/otb", tags=["OTB与商品补货"])


# ---------------- 请求模型 ----------------
class HeaderIn(BaseModel):
    id: Optional[int] = None
    fiscal_year: str = "FY2027"
    bu_code: Optional[str] = None
    opening_stock_cost: float = 0
    planned_sales_cost: float = 0
    planned_sales_total_retail: float = 0
    planned_markdown_cost: float = 0
    target_closing_stock_cost: Optional[float] = 0
    good_in_transit_cost: float = 0
    stock_cover_months: int = 5
    gp_pct: float = 0.65


class MixItem(BaseModel):
    month_seq: int
    mix_pct: float


class MixIn(BaseModel):
    items: list[MixItem]
    version: str = "v1"
    fiscal_year: str = "FY2027"


class CalculateIn(BaseModel):
    header_id: int
    fiscal_year: str = "FY2027"


class FiscalYearIn(BaseModel):
    fiscal_year: str = "FY2027"


class ParamIn(BaseModel):
    config_key: str
    config_value: str
    config_desc: Optional[str] = None
    fiscal_year: Optional[str] = None


class CategoryIn(BaseModel):
    fiscal_year: str = "FY2027"
    bu_code: Optional[str] = None
    brandid: Optional[str] = None
    brand_name: Optional[str] = None
    category_code: str
    category_name: Optional[str] = None
    sales_retail: float = 0
    sale_mix_pct: float = 0
    fc_buy_plan: float = 0
    cost_rate: float = 0.3240


class CategoryGenerateIn(BaseModel):
    fiscal_year: str = "FY2027"
    bu_code: str


class BrandGenerateIn(BaseModel):
    fiscal_year: str = "FY2027"
    bu_code: str


class BrandSaleMixItem(BaseModel):
    id: int
    sale_mix_pct: float


class BrandSaleMixBatchIn(BaseModel):
    fiscal_year: str = "FY2027"
    items: list[BrandSaleMixItem] = []


class BrandIn(BaseModel):
    id: Optional[int] = None
    fiscal_year: str = "FY2027"
    category_code: Optional[str] = None
    brand_name: str
    item_count: int = 0
    total_sales_value: float = 0
    sale_mix_pct: float = 0
    total_sales_qty_ytd: int = 0
    total_sales_cost_ytd: float = 0
    gp_pct: float = 0
    business_soh_cost: float = 0
    spot_month_cover: Optional[float] = None
    fc_sales_plan: float = 0
    fc_buy_plan: float = 0
    actual_buy_ytd: float = 0


class ItemIn(BaseModel):
    brand_id: Optional[int] = None
    item_code: str
    product_name: Optional[str] = None
    sale_mix_pct: float = 0
    fc_sales_plan_retail: float = 0
    fc_buy_plan_cost: float = 0
    uae_wh: int = 0
    uae_stores: int = 0
    qtr_wh: int = 0
    qtr_stores: int = 0
    bah_wh: int = 0
    bah_stores: int = 0
    stocks_in_transit: int = 0
    forecasted_wk_cover: float = 20


class BrandCategoryItemIn(BaseModel):
    categoryid: str
    categoryname: Optional[str] = None
    category_note: Optional[str] = None
    is_primary: int = 0
    sort_no: int = 0
    remark: Optional[str] = None


class BrandCategorySaveIn(BaseModel):
    brand_name: str
    brandid: Optional[str] = None
    items: list[BrandCategoryItemIn] = []


class DecisionIn(BaseModel):
    status: str


# ---------------- OTB 主参数 / 测算 ----------------
@router.get("/headers")
def list_headers(fiscal_year: Optional[str] = None, _: dict = Depends(get_current_user)):
    return svc.header_list(fiscal_year)


@router.post("/headers")
def save_header(payload: HeaderIn, user: dict = Depends(get_current_user)):
    return svc.header_upsert(payload.model_dump(), user.get("usercode", "sys"))


@router.post("/calculate")
def calculate(payload: CalculateIn, user: dict = Depends(get_current_user)):
    try:
        return svc.calculate_and_save(payload.header_id, payload.fiscal_year, user.get("usercode", "sys"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/monthly")
def list_monthly(header_id: int, fiscal_year: str = "FY2027", _: dict = Depends(get_current_user)):
    return svc.monthly_list(header_id, fiscal_year)


@router.get("/monthly/pivot")
def list_monthly_pivot(header_id: int, fiscal_year: str = "FY2027", _: dict = Depends(get_current_user)):
    """Excel 风格转置明细：月份作列、指标作行（含 FY2027 合计）"""
    return svc.monthly_pivot(header_id, fiscal_year)


@router.get("/preview")
def preview(header_id: int, fiscal_year: str = "FY2027", _: dict = Depends(get_current_user)):
    """纯计算预览，不落库"""
    h = svc.header_get(header_id)
    if not h:
        raise HTTPException(status_code=404, detail="OTB 主参数不存在")
    mix_rows = svc.mix_list(fiscal_year)
    otb = svc.compute_otb(h)
    result = svc.compute_monthly(otb, mix_rows if mix_rows else None)
    return {"otb": otb, **result}


# ---------------- 参数 / Sales Mix ----------------
@router.get("/params")
def list_params(fiscal_year: Optional[str] = None, _: dict = Depends(get_current_user)):
    return svc.param_list(fiscal_year)


@router.post("/params")
def set_param(payload: ParamIn, user: dict = Depends(get_current_user)):
    return svc.param_set(payload.config_key, payload.config_value,
                         payload.fiscal_year, payload.config_desc,
                         user.get("usercode", "sys"))


@router.get("/sales-mix")
def get_mix(fiscal_year: str = "FY2027", version: str = "v1", _: dict = Depends(get_current_user)):
    return svc.mix_list(fiscal_year, version)


@router.put("/sales-mix")
def save_mix(payload: MixIn, user: dict = Depends(get_current_user)):
    try:
        return svc.mix_save(payload.fiscal_year, [i.model_dump() for i in payload.items],
                            payload.version, user.get("usercode", "sys"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------- 品类（品牌×品类明细） ----------------
@router.get("/categories")
def list_categories(fiscal_year: Optional[str] = None, bu_code: Optional[str] = None,
                    brand_name: Optional[str] = None, _: dict = Depends(get_current_user)):
    return svc.category_list(fiscal_year, bu_code, brand_name)


@router.post("/categories")
def save_category(payload: CategoryIn, user: dict = Depends(get_current_user)):
    return svc.category_upsert(payload.model_dump(), user.get("usercode", "sys"))


@router.post("/categories/generate")
def generate_categories(payload: CategoryGenerateIn,
                        user: dict = Depends(get_current_user)):
    """按 BU 自动生成品牌×品类明细（BU→品牌→品牌关联品类）"""
    try:
        return svc.category_generate_by_bu(
            payload.fiscal_year, payload.bu_code, user.get("usercode", "sys"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/categories/check")
def check_categories(fiscal_year: str = "FY2027", bu_code: Optional[str] = None,
                     _: dict = Depends(get_current_user)):
    return svc.category_check(fiscal_year, bu_code)


# ---------------- 品牌 ----------------
@router.get("/brands")
def list_brands(fiscal_year: Optional[str] = None, keyword: Optional[str] = None,
                bu_code: Optional[str] = None,
                page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
                _: dict = Depends(get_current_user)):
    return svc.brand_list(fiscal_year, keyword, page, page_size, bu_code)


@router.post("/brands")
def save_brand(payload: BrandIn, user: dict = Depends(get_current_user)):
    return svc.brand_upsert(payload.model_dump(), user.get("usercode", "sys"))


@router.post("/brands/batch-sale-mix")
def batch_brand_sale_mix(payload: BrandSaleMixBatchIn, user: dict = Depends(get_current_user)):
    """批量保存品牌 Sale Mix%（行内编辑），FC 计划按公式自动重算"""
    try:
        return svc.brand_batch_sale_mix(
            payload.fiscal_year,
            [i.model_dump() for i in payload.items],
            user.get("usercode", "sys"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/brands/{brand_id}/monthly")
def brand_monthly(brand_id: int, fiscal_year: str = "FY2027", _: dict = Depends(get_current_user)):
    try:
        return svc.brand_monthly_split(brand_id, fiscal_year)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/brands/{brand_id}/mix")
def brand_mix(brand_id: int, fiscal_year: str = "FY2027", _: dict = Depends(get_current_user)):
    return svc.brand_mix_list(brand_id, fiscal_year)


@router.put("/brands/{brand_id}/mix")
def save_brand_mix(brand_id: int, payload: MixIn,
                   user: dict = Depends(get_current_user)):
    try:
        return svc.brand_mix_save(brand_id, payload.fiscal_year,
                                  [i.model_dump() for i in payload.items],
                                  payload.version, user.get("usercode", "sys"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------- 系统链路：BU→品牌→品类，品牌 Sale Mix 按品类分摊 ----------------
@router.get("/brands/relations")
def brand_relations(fiscal_year: str = "FY2027", _: dict = Depends(get_current_user)):
    """所有品牌的 BU / 主品类 / 品类关系映射"""
    return svc.brand_relations(fiscal_year)


@router.get("/brands/sale-mix/preview")
def brand_sale_mix_preview(fiscal_year: str = "FY2027", _: dict = Depends(get_current_user)):
    """按品类关系预览品牌 Sale Mix 分摊（不落库）"""
    return svc.brand_sale_mix_preview(fiscal_year)


@router.post("/brands/sale-mix/recalc")
def brand_sale_mix_recalc(payload: FiscalYearIn = FiscalYearIn(),
                          user: dict = Depends(get_current_user)):
    """按 BU→品牌→品类 关系重算并回写品牌 Sale Mix 与 FC 计划"""
    return svc.brand_sale_mix_recalc(payload.fiscal_year, user.get("usercode", "sys"))


# ---------------- 按 BRANDCHILD 字典生成品牌汇总 ----------------
@router.get("/brandchild-options")
def brandchild_options(_: dict = Depends(get_current_user)):
    """BRANDCHILD 全部子品牌（Sub_Brand_ID / Sub_Brand_Name）"""
    return svc.brandchild_options()


@router.get("/brands/generate/preview")
def brand_generate_preview(fiscal_year: str = "FY2027", bu_code: Optional[str] = None,
                           _: dict = Depends(get_current_user)):
    """预览按 BRANDCHILD 生成的品牌数据（含 Sale Mix 沿用值，不落库）"""
    try:
        return svc.brand_generate_preview(fiscal_year, bu_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/brands/generate")
def brand_generate(payload: BrandGenerateIn, user: dict = Depends(get_current_user)):
    """按所选 BU + 财年，从 BRANDCHILD 全部子品牌生成品牌数据并关联 BU"""
    try:
        return svc.brand_generate(payload.fiscal_year, payload.bu_code,
                                  user.get("usercode", "sys"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------- 品牌-品类关系（品类实时读 mdmbasedb.category） ----------------
@router.get("/category-options")
def category_options(_: dict = Depends(get_current_user)):
    """品类下拉：mdmbasedb.category 的 3 位业务品类"""
    return svc.category_options()


@router.get("/brand-options")
def brand_options(fiscal_year: Optional[str] = None, main_only: bool = True,
                  _: dict = Depends(get_current_user)):
    """品牌下拉：默认仅主数据主品牌（品牌-品类关系设定用）；main_only=false 时合并 OTB 品牌汇总"""
    return svc.brand_options(fiscal_year, main_only)


@router.get("/brand-categories")
def list_brand_categories(brand_name: Optional[str] = None,
                          _: dict = Depends(get_current_user)):
    return svc.brand_category_list(brand_name)


@router.post("/brand-categories")
def save_brand_categories(payload: BrandCategorySaveIn, user: dict = Depends(get_current_user)):
    try:
        return svc.brand_category_save(payload.model_dump(), user.get("usercode", "sys"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/brand-categories/{row_id}")
def delete_brand_category(row_id: int, _: dict = Depends(get_current_user)):
    return svc.brand_category_delete(row_id)


# ---------------- 商品 / 补货 ----------------
@router.get("/items")
def list_items(brand_id: Optional[int] = None, keyword: Optional[str] = None,
               page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=1000),
               _: dict = Depends(get_current_user)):
    return svc.item_list(brand_id, keyword, page, page_size)


@router.post("/items")
def save_item(payload: ItemIn, user: dict = Depends(get_current_user)):
    return svc.item_upsert(payload.model_dump(), user.get("usercode", "sys"))


@router.get("/items/{item_code}/weekly")
def item_weekly(item_code: str, _: dict = Depends(get_current_user)):
    return svc.item_weekly(item_code)


@router.post("/items/{item_code}/recalculate")
def item_recalc(item_code: str, user: dict = Depends(get_current_user)):
    try:
        return svc.item_recalc(item_code, user.get("usercode", "sys"))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/replenishment")
def list_replenishment(status: Optional[str] = None,
                       page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=1000),
                       _: dict = Depends(get_current_user)):
    return svc.replenishment_list(status, page, page_size)


@router.post("/replenishment/generate")
def generate_replenishment(payload: FiscalYearIn = FiscalYearIn(),
                           user: dict = Depends(get_current_user)):
    return svc.replenishment_generate(payload.fiscal_year, user.get("usercode", "sys"))


@router.post("/replenishment/{row_id}/decision")
def decide_replenishment(row_id: int, payload: DecisionIn,
                         user: dict = Depends(get_current_user)):
    try:
        return svc.replenishment_decision(row_id, payload.status, user.get("usercode", "sys"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------- 导入 / 看板 / 校验 ----------------
@router.post("/import")
async def import_excel(file: UploadFile = File(...), fiscal_year: str = Form("FY2027"),
                       user: dict = Depends(get_current_user)):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="请上传 .xlsx 文件")
    content = await file.read()
    try:
        return svc.import_excel(content, fiscal_year, user.get("usercode", "sys"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"导入失败：{e}")


@router.get("/dashboard")
def dashboard(fiscal_year: str = "FY2027", _: dict = Depends(get_current_user)):
    return svc.dashboard(fiscal_year)


@router.get("/validate")
def validate(fiscal_year: str = "FY2027", _: dict = Depends(get_current_user)):
    return svc.validate(fiscal_year)
