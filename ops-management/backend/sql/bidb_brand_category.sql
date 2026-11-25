-- ============================================================
-- 品牌-品类关系表结构 (bidb 库)
-- 用途：构造品牌与品类的多对多关系，提供页面快捷设定
--
-- 品类数据源（实时直读，不建快照表）：
--   SELECT categoryid, categoryname, note FROM mdmbasedb.category
--   WHERE dbsplitcode='1' AND LENGTH(categoryid)=3 ORDER BY categoryid
-- 品牌数据源（OTB 品牌）：bidb.brand_summary (brand_name)
-- 主数据品牌（可选回写）：mdmbasedb.brand (brandid, brandname, note)
--
-- 设计要点：
--   * 一个品牌可归属多个品类（多对多），如 MEDICUBE 跨护肤/彩妆/美容仪等
--   * is_primary 标记主品类：一个品牌最多一个主品类，用于预算归口
--   * 关系为全局主数据，不绑定财务年（无 fiscal_year 字段）
--   * 品类不落地快照——页面品类下拉每次从 mdmbasedb.category 实时读取
--   * 所有表统一含 6 个公共审计字段
-- 执行方式：CREATE TABLE IF NOT EXISTS，可重复执行
-- ============================================================


-- ------------------------------------------------------------
-- 品牌-品类关系表 bidb.brand_category_rel
--    多对多：一个品牌可跨多个品类；is_primary 标记主品类
--    全局关系，不按财年区分；品牌以 brand_name 关联，兼容 brandid
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.brand_category_rel (
  id            BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  brand_name    VARCHAR(128) NOT NULL COMMENT 'OTB 品牌名（bidb.brand_summary.brand_name）',
  brandid       VARCHAR(64)  DEFAULT NULL COMMENT '主数据品牌ID（mdmbasedb.brand.brandid，可为空）',
  categoryid    VARCHAR(10)  NOT NULL COMMENT '品类ID（3位，mdmbasedb.category.categoryid）',
  categoryname  VARCHAR(128) DEFAULT NULL COMMENT '品类英文名（冗余，便于展示）',
  category_note VARCHAR(128) DEFAULT NULL COMMENT '品类中文名（冗余，便于展示）',
  is_primary    TINYINT      DEFAULT 0 COMMENT '是否主品类：1=主品类，0=副品类（每品牌最多一个主品类）',
  sort_no       INT          DEFAULT 0 COMMENT '展示顺序',
  remark        VARCHAR(255) DEFAULT NULL COMMENT '备注',
  entid         VARCHAR(20)  DEFAULT NULL COMMENT '租户 ID',
  dbsplitcode   VARCHAR(20)  DEFAULT NULL COMMENT '分库分表编码',
  creator       VARCHAR(20)  DEFAULT NULL COMMENT '创建人',
  createtime    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  modifier      VARCHAR(20)  DEFAULT NULL COMMENT '修改人',
  modifytime    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_brand_cat (brand_name, categoryid),
  KEY idx_bcr_brand (brand_name),
  KEY idx_bcr_cat (categoryid),
  KEY idx_bcr_primary (brand_name, is_primary)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='品牌-品类关系表(多对多+主品类,全局)';


-- ------------------------------------------------------------
-- 品牌主品类回写字段（在 brand_summary 上冗余主品类，便于预算归口）
-- 若 brand_summary 已存在 primary_categoryid 字段则可跳过本 ALTER
-- ------------------------------------------------------------
-- ALTER TABLE bidb.brand_summary
--   ADD COLUMN primary_categoryid VARCHAR(10) DEFAULT NULL COMMENT '主品类ID（冗余自关系表）' AFTER category_code;


-- ============================================================
-- 已实现接口（见 app/routers/otb.py、app/services/otb_service.py）：
--   GET    /api/otb/category-options                品类下拉（实时读 mdmbasedb.category）
--   GET    /api/otb/brand-categories                 查询关系（按品牌过滤，全局不分页）
--   POST   /api/otb/brand-categories                 按品牌批量保存（含主品类唯一校验）
--   DELETE /api/otb/brand-categories/{id}            删除单条关系
--
-- 校验规则：一个品牌最多一个 is_primary=1；主品类用于预算归口
-- 迁移提示：已建表若含 fiscal_year，执行：
--   ALTER TABLE bidb.brand_category_rel DROP INDEX uk_brand_cat;
--   ALTER TABLE bidb.brand_category_rel DROP INDEX idx_bcr_brand;
--   ALTER TABLE bidb.brand_category_rel DROP INDEX idx_bcr_primary;
--   ALTER TABLE bidb.brand_category_rel DROP COLUMN fiscal_year;
--   ALTER TABLE bidb.brand_category_rel ADD UNIQUE KEY uk_brand_cat (brand_name, categoryid);
--   ALTER TABLE bidb.brand_category_rel ADD KEY idx_bcr_brand (brand_name);
--   ALTER TABLE bidb.brand_category_rel ADD KEY idx_bcr_primary (brand_name, is_primary);
-- 页面：/otb/brand-category（品牌-品类关系设定）
-- ============================================================
-- END
