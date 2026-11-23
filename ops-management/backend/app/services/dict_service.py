"""
字典数据服务：品牌/货代/船公司/仓库/起运港/目的港 下拉
统一返回 {value, label}，value 存库（fieldvalue / 品牌 note）
品牌 value 用 note（MMS/DZL/XB），note 为空时回退 brandname，保证保存后仍是原来的品牌简称而非数字编码
label 支持中英文：中文用 lookup（中文名），英文用 fieldvalue（code，拉丁字母标识）
"""
from typing import List, Dict
import time
import logging

from app.core.database import fetch_all
from app.schemas import DictItem

logger = logging.getLogger(__name__)

# 字典缓存（5分钟），避免频繁查库。key 带语言后缀区分中英文
_cache: Dict[str, tuple] = {}
CACHE_TTL = 300


def _is_en(lang: str) -> bool:
    return bool(lang) and lang.lower().startswith("en")


def _cached(key: str, lang: str, loader) -> List[DictItem]:
    cache_key = f"{key}:{'en' if _is_en(lang) else 'zh'}"
    now = time.time()
    if cache_key in _cache and now - _cache[cache_key][0] < CACHE_TTL:
        return _cache[cache_key][1]
    try:
        data = loader()
        _cache[cache_key] = (now, data)
        return data
    except Exception as e:
        logger.exception("加载字典 %s 失败", cache_key)
        if cache_key in _cache:
            return _cache[cache_key][1]
        raise


def _label(code, name, lang: str) -> str:
    """中文显示中文名，英文显示 code（拉丁字母标识）"""
    code_s = str(code)
    if _is_en(lang):
        return code_s
    return str(name or code_s)


def get_brands(lang: str = "zh-CN") -> List[DictItem]:
    # value 存品牌简称 note（MMS/DZL/XB），note 为空回退 brandname；
    # label 显示品牌名（MUMUSO 等英文商标，中英文一致）
    def load():
        rows = fetch_all(
            "SELECT brandid, brandname, note FROM mdmbasedb.brand "
            "WHERE dbsplitcode=1 ORDER BY brandid"
        )
        items = []
        for r in rows:
            note = str(r["note"]).strip() if r.get("note") else ""
            value = note or str(r["brandname"] or r["brandid"]).strip()
            label = str(r["brandname"] or value)
            items.append(DictItem(value=value, label=label))
        return items
    return _cached("brands", lang, load)


def get_forwarders(lang: str = "zh-CN") -> List[DictItem]:
    def load():
        rows = fetch_all(
            "SELECT fieldvalue AS code, lookup AS name FROM glsdb.lookupitem "
            "WHERE locale='zh-CN' AND lookupid='FORWARD'"
        )
        return [DictItem(value=str(r["code"]), label=_label(r["code"], r["name"], lang)) for r in rows]
    return _cached("forwarders", lang, load)


def get_ship_companies(lang: str = "zh-CN") -> List[DictItem]:
    def load():
        rows = fetch_all(
            "SELECT fieldvalue AS code, lookup AS name FROM glsdb.lookupitem "
            "WHERE locale='zh-CN' AND lookupid='FEITUOCARRIERCODE'"
        )
        return [DictItem(value=str(r["code"]), label=_label(r["code"], r["name"], lang)) for r in rows]
    return _cached("ship_co", lang, load)


def get_warehouses(lang: str = "zh-CN") -> List[DictItem]:
    def load():
        rows = fetch_all(
            "SELECT fieldvalue AS code FROM glsdb.lookupitem "
            "WHERE locale='zh-CN' AND lookupid='WH'"
        )
        # 仓库 code（YIWU/SHANGHAI）本身为英文标识，中英文一致
        return [DictItem(value=str(r["code"]), label=str(r["code"])) for r in rows]
    return _cached("warehouses", lang, load)


def get_ports(kind: str, lang: str = "zh-CN") -> List[DictItem]:
    lookupid = "FEITUOPORTCODE" if kind == "pol" else "DestPORTCODE"

    def load():
        rows = fetch_all(
            "SELECT fieldvalue AS code, lookup AS name FROM glsdb.lookupitem "
            "WHERE locale='zh-CN' AND lookupid=%s",
            (lookupid,),
        )
        return [DictItem(value=str(r["code"]), label=_label(r["code"], r["name"], lang)) for r in rows]
    return _cached(f"ports_{kind}", lang, load)


def get_cargotypes(lang: str = "zh-CN") -> List[DictItem]:
    if _is_en(lang):
        return [DictItem(value="0", label="Product"), DictItem(value="1", label="Non-product")]
    return [DictItem(value="0", label="商品"), DictItem(value="1", label="非商品")]
