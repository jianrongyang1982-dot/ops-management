-- ============================================================
-- BU 定义 / BU-品牌关系 表结构 (bidb 库)
-- 用途：
--   1. BU(Business Unit 业务单元)主数据维护：新增/修改/删除/查询/导入/导出
--   2. 设定 BU 与品牌的多对多关系（含主品牌标记）
--
-- 说明：
--   * bu_code 与 bidb.otb_header.bu_code 口径一致（如 X-Beauty），作为业务主键
--   * 品牌主数据源：mdmbasedb.brand (brandid, brandname, note) 实时直读，不落地快照
--   * 一个 BU 可含多个品牌；一个品牌可跨多个 BU；is_primary 标记品牌的主 BU
--   * 所有表统一含 6 个公共审计字段：
--       entid, dbsplitcode, creator, createtime, modifier, modifytime
-- 执行方式：CREATE TABLE IF NOT EXISTS，可重复执行
-- ============================================================


-- ------------------------------------------------------------
-- 1. BU 定义表 bidb.bu_def
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.bu_def (
  id            BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  bu_code       VARCHAR(50)  NOT NULL COMMENT 'BU代码（业务主键），如 X-Beauty',
  bu_name       VARCHAR(128) DEFAULT NULL COMMENT 'BU中文名称',
  bu_name_en    VARCHAR(128) DEFAULT NULL COMMENT 'BU英文名称',
  status        TINYINT      DEFAULT 1 COMMENT '状态：1=启用，0=停用',
  sort_no       INT          DEFAULT 0 COMMENT '展示顺序',
  remark        VARCHAR(255) DEFAULT NULL COMMENT '备注',
  entid         VARCHAR(20)  DEFAULT NULL COMMENT '租户 ID',
  dbsplitcode   VARCHAR(20)  DEFAULT NULL COMMENT '分库分表编码',
  creator       VARCHAR(20)  DEFAULT NULL COMMENT '创建人',
  createtime    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  modifier      VARCHAR(20)  DEFAULT NULL COMMENT '修改人',
  modifytime    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_bu_code (bu_code),
  KEY idx_bu_status (status, sort_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='BU业务单元定义表';


-- ------------------------------------------------------------
-- 2. BU-品牌关系表 bidb.bu_brand_rel
--    多对多：一个 BU 含多个品牌；is_primary 标记品牌归属的主 BU
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.bu_brand_rel (
  id            BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  bu_code       VARCHAR(50)  NOT NULL COMMENT 'BU代码（bidb.bu_def.bu_code）',
  brand_name    VARCHAR(128) NOT NULL COMMENT '品牌名（mdmbasedb.brand.brandname）',
  brandid       VARCHAR(64)  DEFAULT NULL COMMENT '主数据品牌ID（mdmbasedb.brand.brandid）',
  brand_note    VARCHAR(64)  DEFAULT NULL COMMENT '品牌简称（mdmbasedb.brand.note，如 MMS）',
  is_primary    TINYINT      DEFAULT 0 COMMENT '是否主BU：1=品牌归属的主BU，0=副BU（每品牌最多一个主BU）',
  sort_no       INT          DEFAULT 0 COMMENT '展示顺序',
  remark        VARCHAR(255) DEFAULT NULL COMMENT '备注',
  entid         VARCHAR(20)  DEFAULT NULL COMMENT '租户 ID',
  dbsplitcode   VARCHAR(20)  DEFAULT NULL COMMENT '分库分表编码',
  creator       VARCHAR(20)  DEFAULT NULL COMMENT '创建人',
  createtime    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  modifier      VARCHAR(20)  DEFAULT NULL COMMENT '修改人',
  modifytime    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_bu_brand (bu_code, brand_name),
  KEY idx_bbr_bu (bu_code),
  KEY idx_bbr_brand (brand_name),
  KEY idx_bbr_primary (brand_name, is_primary)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='BU-品牌关系表(多对多+主BU)';


-- ============================================================
-- 接口（app/routers/bu.py、app/services/bu_service.py）：
--   BU 定义：
--     GET    /api/bu/list                 BU 列表（分页/关键字/状态）
--     GET    /api/bu/options              BU 下拉
--     POST   /api/bu                      新增 BU
--     PUT    /api/bu/{id}                 修改 BU
--     DELETE /api/bu/{id}                 删除 BU（级联删除关系）
--     GET    /api/bu/export               BU 导出 Excel
--     POST   /api/bu/import               BU 导入 Excel（新增/更新）
--   BU-品牌关系：
--     GET    /api/bu/brand-options        品牌下拉（实时读 mdmbasedb.brand）
--     GET    /api/bu/{bu_code}/brands     查询某 BU 的品牌关系
--     POST   /api/bu/{bu_code}/brands     按 BU 批量保存品牌关系（主BU唯一校验）
--     DELETE /api/bu/brand-rel/{id}       删除单条关系
--
-- 页面：/bu/definition（BU定义）、/bu/brand（BU-品牌关系）
-- ============================================================
-- END
