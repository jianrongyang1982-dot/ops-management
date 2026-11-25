"""
迁移脚本：bidb.brand_summary 增加 sub_brand_id 字段（BRANDCHILD 子品牌编码）
可重复执行：先检查字段是否已存在。
运行：.venv/Scripts/python.exe sql/migrate_brand_sub_brand_id.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core import bidb_database as db

TABLE = "bidb.brand_summary"


def column_exists(name: str) -> bool:
    row = db.fetch_one(
        "SELECT COUNT(*) AS n FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA='bidb' AND TABLE_NAME='brand_summary' AND COLUMN_NAME=%s",
        (name,),
    )
    return bool(row and row["n"])


def index_exists(name: str) -> bool:
    row = db.fetch_one(
        "SELECT COUNT(*) AS n FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA='bidb' AND TABLE_NAME='brand_summary' AND INDEX_NAME=%s",
        (name,),
    )
    return bool(row and row["n"])


def main():
    if not column_exists("sub_brand_id"):
        db.execute(
            "ALTER TABLE " + TABLE + " ADD COLUMN sub_brand_id VARCHAR(64) "
            "DEFAULT NULL COMMENT 'BRANDCHILD子品牌编码' AFTER brand_name"
        )
        print("added column sub_brand_id")
    else:
        print("column sub_brand_id already exists")

    if not index_exists("idx_brand_subid"):
        db.execute(
            "ALTER TABLE " + TABLE + " ADD KEY idx_brand_subid (sub_brand_id)"
        )
        print("added index idx_brand_subid")
    else:
        print("index idx_brand_subid already exists")

    print("done")


if __name__ == "__main__":
    main()
