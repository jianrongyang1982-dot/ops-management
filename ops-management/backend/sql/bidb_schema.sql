-- ============================================================
-- OTB 采买与商品补货功能 - 表结构 (bidb 库)
-- 生成依据：OTB与商品补货功能系统设计文档_v4
-- 约定：复用现有 OceanBase 连接(roc 账号)，SQL 中以 bidb.表名 全限定访问
-- 所有表统一包含 6 个公共审计字段：
--   entid, dbsplitcode, creator, createtime, modifier, modifytime
-- 执行方式：在数据库客户端执行本脚本（CREATE TABLE IF NOT EXISTS，可重复执行）
-- ============================================================

-- 若 bidb 库不存在可先创建（如已存在请忽略）
-- CREATE DATABASE IF NOT EXISTS bidb DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;


-- ------------------------------------------------------------
-- 1. OTB 主参数表 bidb.otb_header
--    对应 Excel OTB_X-Beauty sheet，一行 = 一个 BU 一个财年
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.otb_header (
  id                        BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  fiscal_year               VARCHAR(20)  NOT NULL COMMENT '财年，如 FY2027',
  bu_code                   VARCHAR(50)  DEFAULT NULL COMMENT '业务单元代码，如 X-Beauty',
  opening_stock_cost        DECIMAL(18,2) DEFAULT 0 COMMENT 'Opening Stock Cost 期初库存成本',
  planned_sales_cost        DECIMAL(18,2) DEFAULT 0 COMMENT 'Planned Sales Cost 计划销售成本(成本口径)',
  planned_sales_total_retail DECIMAL(18,2) DEFAULT 0 COMMENT 'Planned Sales Total 零售口径全年计划销售',
  planned_markdown_cost     DECIMAL(18,2) DEFAULT 0 COMMENT 'Planned Markdown Cost 计划降价成本',
  target_closing_stock_cost DECIMAL(18,2) DEFAULT 0 COMMENT 'Target Closing Stock Cost 目标期末库存成本',
  good_in_transit_cost      DECIMAL(18,2) DEFAULT 0 COMMENT 'Good In-Transit Cost 在途库存成本',
  otb_cost                  DECIMAL(18,2) DEFAULT 0 COMMENT 'OTB Cost 采买预算金额(计算结果)',
  stock_cover_months        INT          DEFAULT 5 COMMENT 'Stock Cover (Months) 库存覆盖月数',
  gp_pct                    DECIMAL(6,4) DEFAULT 0.65 COMMENT 'GP% 全局毛利率',
  cogs_rate                 DECIMAL(6,4) DEFAULT 0.35 COMMENT 'COGS 率 = 1 - gp_pct',
  cost_rate                 DECIMAL(6,4) DEFAULT 0.3240 COMMENT '全局成本率 Buy/Retail',
  calc_batch_id             VARCHAR(64)  DEFAULT NULL COMMENT '计算批次号(幂等键)',
  entid                     VARCHAR(20)  DEFAULT NULL COMMENT '租户 ID',
  dbsplitcode               VARCHAR(20)  DEFAULT NULL COMMENT '分库分表编码',
  creator                   VARCHAR(20)  DEFAULT NULL COMMENT '创建人',
  createtime                TIMESTAMP    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  modifier                  VARCHAR(20)  DEFAULT NULL COMMENT '修改人',
  modifytime                TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (id),
  KEY idx_otb_header_fy_bu (fiscal_year, bu_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='OTB 主参数表';


-- ------------------------------------------------------------
-- 2. OTB 月度明细表 bidb.otb_monthly
--    对应 Excel 2027 OTB sheet 12 个月拆解区
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.otb_monthly (
  id                  BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  otb_header_id       BIGINT       DEFAULT NULL COMMENT '关联 OTB 主记录',
  brand_id            BIGINT       DEFAULT NULL COMMENT '品牌 ID(公司级汇总行为空)',
  fiscal_year         VARCHAR(20)  DEFAULT NULL COMMENT '财年',
  month_seq           INT          DEFAULT NULL COMMENT '月序 1-12(财年 Apr->Mar)',
  period              VARCHAR(10)  DEFAULT NULL COMMENT '期间，如 2027-04',
  sales_mix_pct       DECIMAL(6,4) DEFAULT NULL COMMENT '该月销售节奏系数',
  opening_stock       DECIMAL(18,2) DEFAULT 0 COMMENT '期初库存',
  retail_sales        DECIMAL(18,2) DEFAULT 0 COMMENT '零售销售额',
  cogs                DECIMAL(18,2) DEFAULT 0 COMMENT '销售成本 = retail_sales * cogs_rate',
  gp_pct              DECIMAL(6,4) DEFAULT NULL COMMENT '毛利率',
  intake_value_cost   DECIMAL(18,2) DEFAULT 0 COMMENT '当月入库金额',
  closing_stock       DECIMAL(18,2) DEFAULT 0 COMMENT '期末库存',
  forward_month_cover DECIMAL(8,2) DEFAULT NULL COMMENT '前置库存覆盖月数',
  retail_q4_factor    DECIMAL(6,4) DEFAULT 1.0000 COMMENT 'Q4 零售旺季系数(默认1,Q4月=1.3)',
  intake_q4_factor    DECIMAL(6,4) DEFAULT 1.0000 COMMENT 'Q4 入库旺季系数(默认1,Q4月=1.2)',
  amount_basis        VARCHAR(10)  DEFAULT 'COST' COMMENT '金额口径枚举 COST/RETAIL(防错)',
  calc_batch_id       VARCHAR(64)  DEFAULT NULL COMMENT '计算批次号',
  entid               VARCHAR(20)  DEFAULT NULL COMMENT '租户 ID',
  dbsplitcode         VARCHAR(20)  DEFAULT NULL COMMENT '分库分表编码',
  creator             VARCHAR(20)  DEFAULT NULL COMMENT '创建人',
  createtime          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  modifier            VARCHAR(20)  DEFAULT NULL COMMENT '修改人',
  modifytime          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (id),
  KEY idx_otb_monthly_hdr (otb_header_id, month_seq),
  KEY idx_otb_monthly_batch (calc_batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='OTB 月度明细表';


-- ------------------------------------------------------------
-- 3. 参数配置表 bidb.otb_param_config
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.otb_param_config (
  id           BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  config_key   VARCHAR(64)  NOT NULL COMMENT '参数键 COGS_RATE/COST_RATE/NEW_ITEM_RATIO/Q4_RETAIL_FACTOR...',
  config_value VARCHAR(128) DEFAULT NULL COMMENT '参数值(字符串存储)',
  config_desc  VARCHAR(255) DEFAULT NULL COMMENT '参数说明',
  fiscal_year  VARCHAR(20)  DEFAULT NULL COMMENT '适用财年(空=全局默认)',
  version      VARCHAR(32)  DEFAULT NULL COMMENT '版本号',
  entid        VARCHAR(20)  DEFAULT NULL COMMENT '租户 ID',
  dbsplitcode  VARCHAR(20)  DEFAULT NULL COMMENT '分库分表编码',
  creator      VARCHAR(20)  DEFAULT NULL COMMENT '创建人',
  createtime   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  modifier     VARCHAR(20)  DEFAULT NULL COMMENT '修改人',
  modifytime   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_param_key (config_key, fiscal_year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='参数配置表';


-- ------------------------------------------------------------
-- 4. 销售节奏配置表 bidb.sales_mix_config
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.sales_mix_config (
  id          BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  fiscal_year VARCHAR(20)  NOT NULL COMMENT '财年',
  month_seq   INT          NOT NULL COMMENT '月序 1-12',
  mix_pct     DECIMAL(6,4) DEFAULT NULL COMMENT '该月销售占比(12 月合计=1)',
  version     VARCHAR(32)  DEFAULT 'v1' COMMENT '版本号',
  entid       VARCHAR(20)  DEFAULT NULL COMMENT '租户 ID',
  dbsplitcode VARCHAR(20)  DEFAULT NULL COMMENT '分库分表编码',
  creator     VARCHAR(20)  DEFAULT NULL COMMENT '创建人',
  createtime  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  modifier    VARCHAR(20)  DEFAULT NULL COMMENT '修改人',
  modifytime  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_mix_fy_month_ver (fiscal_year, month_seq, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销售节奏配置表';


-- ------------------------------------------------------------
-- 5. 品类汇总表 bidb.category_summary
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.category_summary (
  id            BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  fiscal_year   VARCHAR(20)   NOT NULL COMMENT '财年',
  bu_code       VARCHAR(50)   DEFAULT NULL COMMENT 'BU代码（bidb.bu_def.bu_code）',
  brandid       VARCHAR(64)   DEFAULT NULL COMMENT '品牌编码（mdmbasedb.brand.brandid）',
  brand_name    VARCHAR(128)  DEFAULT NULL COMMENT '品牌名称（可空=品类级汇总行）',
  category_code VARCHAR(64)   NOT NULL COMMENT '品类代码，如 SKINCARE',
  category_name VARCHAR(128)  DEFAULT NULL COMMENT '品类名称',
  sales_retail  DECIMAL(18,2) DEFAULT 0 COMMENT 'SALES Retail',
  sale_mix_pct  DECIMAL(6,4)  DEFAULT NULL COMMENT 'Sale Mix %（该品牌该品类占全年销售占比）',
  fc_buy_plan   DECIMAL(18,2) DEFAULT 0 COMMENT 'FC Buy Plan',
  cost_rate     DECIMAL(6,4)  DEFAULT 0.3240 COMMENT '成本率',
  calc_batch_id VARCHAR(64)   DEFAULT NULL COMMENT '计算批次号',
  entid         VARCHAR(20)   DEFAULT NULL COMMENT '租户 ID',
  dbsplitcode   VARCHAR(20)   DEFAULT NULL COMMENT '分库分表编码',
  creator       VARCHAR(20)   DEFAULT NULL COMMENT '创建人',
  createtime    TIMESTAMP     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  modifier      VARCHAR(20)   DEFAULT NULL COMMENT '修改人',
  modifytime    TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_cat_fy_brand_code (fiscal_year, brand_name, category_code),
  KEY idx_cs_bu (fiscal_year, bu_code),
  KEY idx_cs_brand (fiscal_year, brand_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='品类汇总表(品牌×品类明细)';

-- 迁移提示（已建表从品类级升级为品牌×品类明细）：
-- ALTER TABLE bidb.category_summary DROP INDEX uk_cat_fy_code;
-- ALTER TABLE bidb.category_summary ADD COLUMN bu_code VARCHAR(50) DEFAULT NULL COMMENT 'BU代码' AFTER fiscal_year;
-- ALTER TABLE bidb.category_summary ADD COLUMN brandid VARCHAR(64) DEFAULT NULL COMMENT '品牌编码' AFTER bu_code;
-- ALTER TABLE bidb.category_summary ADD COLUMN brand_name VARCHAR(128) DEFAULT NULL COMMENT '品牌名称' AFTER brandid;
-- ALTER TABLE bidb.category_summary ADD UNIQUE KEY uk_cat_fy_brand_code (fiscal_year, brand_name, category_code);
-- ALTER TABLE bidb.category_summary ADD KEY idx_cs_bu (fiscal_year, bu_code);
-- ALTER TABLE bidb.category_summary ADD KEY idx_cs_brand (fiscal_year, brand_name);


-- ------------------------------------------------------------
-- 6. 品牌汇总表 bidb.brand_summary
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.brand_summary (
  id                   BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  fiscal_year          VARCHAR(20)   NOT NULL COMMENT '财年',
  category_code        VARCHAR(64)   DEFAULT NULL COMMENT '主品类代码',
  brand_name           VARCHAR(128)  NOT NULL COMMENT '品牌名称',
  sub_brand_id         VARCHAR(64)   DEFAULT NULL COMMENT 'BRANDCHILD子品牌编码(glsdb.lookupitem.fieldvalue)',
  item_count           INT           DEFAULT 0 COMMENT 'Count of Item Code',
  total_sales_value    DECIMAL(18,2) DEFAULT 0 COMMENT 'Total Sales Value 2027',
  sale_mix_pct         DECIMAL(6,4)  DEFAULT NULL COMMENT 'Sale Mix %',
  total_sales_qty_ytd  BIGINT        DEFAULT 0 COMMENT 'Total Sales Qty (YTD 2026)',
  total_sales_cost_ytd DECIMAL(18,2) DEFAULT 0 COMMENT 'Total Sales Cost (YTD 2026)',
  gp_pct               DECIMAL(6,4)  DEFAULT NULL COMMENT 'GP% (YTD 2026 口径)',
  business_soh_cost    DECIMAL(18,2) DEFAULT 0 COMMENT 'Business SOH Cost as of Nov',
  spot_month_cover     DECIMAL(6,2)  DEFAULT NULL COMMENT 'Spot Month Cover',
  fc_sales_plan        DECIMAL(18,2) DEFAULT 0 COMMENT '2027 FC Sales Plan',
  fc_buy_plan          DECIMAL(18,2) DEFAULT 0 COMMENT '2027 FC Buy Plan',
  actual_buy_ytd       DECIMAL(18,2) DEFAULT 0 COMMENT '2026 Actual Buy as of Nov',
  monthly_mix_version  VARCHAR(32)   DEFAULT NULL COMMENT '月度曲线版本',
  calc_batch_id        VARCHAR(64)   DEFAULT NULL COMMENT '计算批次号',
  entid                VARCHAR(20)   DEFAULT NULL COMMENT '租户 ID',
  dbsplitcode          VARCHAR(20)   DEFAULT NULL COMMENT '分库分表编码',
  creator              VARCHAR(20)   DEFAULT NULL COMMENT '创建人',
  createtime           TIMESTAMP     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  modifier             VARCHAR(20)   DEFAULT NULL COMMENT '修改人',
  modifytime           TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_brand_fy_name (fiscal_year, brand_name),
  KEY idx_brand_cat (category_code),
  KEY idx_brand_subid (sub_brand_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='品牌汇总表';

-- 迁移提示（已建表增加 sub_brand_id）：
-- ALTER TABLE bidb.brand_summary ADD COLUMN sub_brand_id VARCHAR(64) DEFAULT NULL COMMENT 'BRANDCHILD子品牌编码' AFTER brand_name;
-- ALTER TABLE bidb.brand_summary ADD KEY idx_brand_subid (sub_brand_id);
-- 亦可重复执行 python sql/migrate_brand_sub_brand_id.py


-- ------------------------------------------------------------
-- 7. 品牌月度采买曲线表 bidb.brand_monthly_mix
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.brand_monthly_mix (
  id          BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  brand_id    BIGINT       DEFAULT NULL COMMENT '品牌 ID',
  fiscal_year VARCHAR(20)  DEFAULT NULL COMMENT '财年',
  month_seq   INT          DEFAULT NULL COMMENT '月序 1-12',
  mix_pct     DECIMAL(6,4) DEFAULT NULL COMMENT '该品牌当月采买占比',
  source      VARCHAR(20)  DEFAULT 'global' COMMENT 'global / brand_override',
  version     VARCHAR(32)  DEFAULT 'v1' COMMENT '版本号',
  entid       VARCHAR(20)  DEFAULT NULL COMMENT '租户 ID',
  dbsplitcode VARCHAR(20)  DEFAULT NULL COMMENT '分库分表编码',
  creator     VARCHAR(20)  DEFAULT NULL COMMENT '创建人',
  createtime  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  modifier    VARCHAR(20)  DEFAULT NULL COMMENT '修改人',
  modifytime  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_bmix_brand_fy_month_ver (brand_id, fiscal_year, month_seq, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='品牌月度采买曲线表';


-- ------------------------------------------------------------
-- 8. 商品主数据与预算表 bidb.item_plan
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.item_plan (
  id                   BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  brand_id             BIGINT        DEFAULT NULL COMMENT '所属品牌',
  item_code            VARCHAR(64)   NOT NULL COMMENT 'Item Code',
  product_name         VARCHAR(255)  DEFAULT NULL COMMENT 'Product Name',
  sale_mix_pct         DECIMAL(6,4)  DEFAULT NULL COMMENT 'Sale Mix % 商品在品牌内占比',
  fc_sales_plan_retail DECIMAL(18,2) DEFAULT 0 COMMENT '2027 FC Sales Plan Retail',
  fc_buy_plan_cost     DECIMAL(18,2) DEFAULT 0 COMMENT '2027 FC Buy Plan Cost',
  uae_wh               INT           DEFAULT 0 COMMENT 'UAE 仓库库存',
  uae_stores           INT           DEFAULT 0 COMMENT 'UAE 门店库存',
  qtr_wh               INT           DEFAULT 0 COMMENT 'QTR 仓库库存',
  qtr_stores           INT           DEFAULT 0 COMMENT 'QTR 门店库存',
  bah_wh               INT           DEFAULT 0 COMMENT 'BAH 仓库库存',
  bah_stores           INT           DEFAULT 0 COMMENT 'BAH 门店库存',
  total_stock          INT           DEFAULT 0 COMMENT 'TOTAL STOCK 六地合计',
  ros_wk_ytd           DECIMAL(8,2)  DEFAULT NULL COMMENT 'ROS/WK YTD 周销速',
  spot_week_cover      DECIMAL(8,2)  DEFAULT NULL COMMENT 'Spot Week Cover',
  stocks_in_transit    INT           DEFAULT 0 COMMENT 'Stocks InTransit 在途数量',
  propose_the_qty      INT           DEFAULT NULL COMMENT 'Propose the Qty 建议订货量',
  forecasted_wk_cover  DECIMAL(8,2)  DEFAULT 20 COMMENT 'Forecasted WK Cover 目标覆盖周数',
  order_remarks        VARCHAR(32)   DEFAULT NULL COMMENT 'Order Remarks',
  calc_batch_id        VARCHAR(64)   DEFAULT NULL COMMENT '计算批次号',
  entid                VARCHAR(20)   DEFAULT NULL COMMENT '租户 ID',
  dbsplitcode          VARCHAR(20)   DEFAULT NULL COMMENT '分库分表编码',
  creator              VARCHAR(20)   DEFAULT NULL COMMENT '创建人',
  createtime           TIMESTAMP     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  modifier             VARCHAR(20)   DEFAULT NULL COMMENT '修改人',
  modifytime           TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_item_code (item_code),
  KEY idx_item_brand (brand_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品主数据与预算表';


-- ------------------------------------------------------------
-- 9. 商品周度销量表 bidb.item_weekly_sales
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.item_weekly_sales (
  id          BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  item_code   VARCHAR(64) NOT NULL COMMENT 'Item Code',
  week_seq    INT         NOT NULL COMMENT '周序 1-52',
  sales_qty   INT         DEFAULT 0 COMMENT '该周销量',
  entid       VARCHAR(20) DEFAULT NULL COMMENT '租户 ID',
  dbsplitcode VARCHAR(20) DEFAULT NULL COMMENT '分库分表编码',
  creator     VARCHAR(20) DEFAULT NULL COMMENT '创建人',
  createtime  TIMESTAMP   DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  modifier    VARCHAR(20) DEFAULT NULL COMMENT '修改人',
  modifytime  TIMESTAMP   DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_weekly_item_week (item_code, week_seq)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品周度销量表';


-- ------------------------------------------------------------
-- 10. 库存来源表 bidb.item_stock_snapshot
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.item_stock_snapshot (
  id            BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  item_code     VARCHAR(64) NOT NULL COMMENT 'Item Code',
  location_type VARCHAR(32) NOT NULL COMMENT 'UAE_WH/UAE_STORES/QTR_WH/QTR_STORES/BAH_WH/BAH_STORES',
  stock_qty     INT         DEFAULT 0 COMMENT '库存数量',
  snapshot_date DATE        DEFAULT NULL COMMENT '快照日期',
  entid         VARCHAR(20) DEFAULT NULL COMMENT '租户 ID',
  dbsplitcode   VARCHAR(20) DEFAULT NULL COMMENT '分库分表编码',
  creator       VARCHAR(20) DEFAULT NULL COMMENT '创建人',
  createtime    TIMESTAMP   DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  modifier      VARCHAR(20) DEFAULT NULL COMMENT '修改人',
  modifytime    TIMESTAMP   DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_snap_item_loc_date (item_code, location_type, snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存来源表';


-- ------------------------------------------------------------
-- 11. 补货建议表 bidb.replenishment_suggestion
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.replenishment_suggestion (
  id                   BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  sku_id               BIGINT        DEFAULT NULL COMMENT '商品 ID',
  brand_id             BIGINT        DEFAULT NULL COMMENT '品牌 ID',
  otb_header_id        BIGINT        DEFAULT NULL COMMENT '关联 OTB',
  suggest_date         DATE          DEFAULT NULL COMMENT '建议生成日期',
  available_stock      DECIMAL(18,2) DEFAULT 0 COMMENT '可用库存',
  safety_stock         DECIMAL(18,2) DEFAULT 0 COMMENT '安全库存水位',
  current_cover_months DECIMAL(6,2)  DEFAULT NULL COMMENT '当前覆盖月数',
  suggest_qty          DECIMAL(18,2) DEFAULT 0 COMMENT '建议补货量',
  suggest_amount       DECIMAL(18,2) DEFAULT 0 COMMENT '建议补货金额',
  otb_remaining_amount DECIMAL(18,2) DEFAULT 0 COMMENT 'OTB 剩余可用金额',
  reason               VARCHAR(255)  DEFAULT NULL COMMENT '触发原因说明',
  status               VARCHAR(20)   DEFAULT '待确认' COMMENT '待确认/已采纳/已否决',
  item_code            VARCHAR(64)   DEFAULT NULL COMMENT 'Item Code(冗余便于查询)',
  propose_the_qty      INT           DEFAULT NULL COMMENT '本次建议订货量(来自 item_plan)',
  order_remarks        VARCHAR(32)   DEFAULT NULL COMMENT '订货备注',
  calc_batch_id        VARCHAR(64)   DEFAULT NULL COMMENT '计算批次号',
  entid                VARCHAR(20)   DEFAULT NULL COMMENT '租户 ID',
  dbsplitcode          VARCHAR(20)   DEFAULT NULL COMMENT '分库分表编码',
  creator              VARCHAR(20)   DEFAULT NULL COMMENT '创建人',
  createtime           TIMESTAMP     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  modifier             VARCHAR(20)   DEFAULT NULL COMMENT '修改人',
  modifytime           TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (id),
  KEY idx_replen_batch (calc_batch_id),
  KEY idx_replen_item (item_code),
  KEY idx_replen_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='补货建议表';


-- ============================================================
-- 初始化参数（可选）
-- ============================================================
INSERT INTO bidb.otb_param_config (config_key, config_value, config_desc, creator)
SELECT 'COGS_RATE', '0.35', 'COGS 率', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.otb_param_config WHERE config_key='COGS_RATE');
INSERT INTO bidb.otb_param_config (config_key, config_value, config_desc, creator)
SELECT 'COST_RATE', '0.3240', '全局成本率 Buy/Retail', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.otb_param_config WHERE config_key='COST_RATE');
INSERT INTO bidb.otb_param_config (config_key, config_value, config_desc, creator)
SELECT 'NEW_ITEM_RATIO', '0.30', 'Newness 占比', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.otb_param_config WHERE config_key='NEW_ITEM_RATIO');
INSERT INTO bidb.otb_param_config (config_key, config_value, config_desc, creator)
SELECT 'REPLENISHMENT_RATIO', '0.70', 'Replenishment 占比', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.otb_param_config WHERE config_key='REPLENISHMENT_RATIO');
INSERT INTO bidb.otb_param_config (config_key, config_value, config_desc, creator)
SELECT 'Q4_RETAIL_FACTOR', '1.3', 'Q4 零售旺季系数', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.otb_param_config WHERE config_key='Q4_RETAIL_FACTOR');
INSERT INTO bidb.otb_param_config (config_key, config_value, config_desc, creator)
SELECT 'Q4_INTAKE_FACTOR', '1.2', 'Q4 入库旺季系数', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.otb_param_config WHERE config_key='Q4_INTAKE_FACTOR');
INSERT INTO bidb.otb_param_config (config_key, config_value, config_desc, creator)
SELECT 'FORECASTED_WK_COVER', '20', 'Target Weeks of Cover', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.otb_param_config WHERE config_key='FORECASTED_WK_COVER');

-- 默认 Sales Mix 曲线：6,6,9,8,8,8,9,9,9,9,9,10（财年 Apr->Mar，月序 1-12）
INSERT INTO bidb.sales_mix_config (fiscal_year, month_seq, mix_pct, version, creator)
SELECT 'FY2027', 1, 0.06, 'v1', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.sales_mix_config WHERE fiscal_year='FY2027' AND month_seq=1 AND version='v1');
INSERT INTO bidb.sales_mix_config (fiscal_year, month_seq, mix_pct, version, creator)
SELECT 'FY2027', 2, 0.06, 'v1', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.sales_mix_config WHERE fiscal_year='FY2027' AND month_seq=2 AND version='v1');
INSERT INTO bidb.sales_mix_config (fiscal_year, month_seq, mix_pct, version, creator)
SELECT 'FY2027', 3, 0.09, 'v1', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.sales_mix_config WHERE fiscal_year='FY2027' AND month_seq=3 AND version='v1');
INSERT INTO bidb.sales_mix_config (fiscal_year, month_seq, mix_pct, version, creator)
SELECT 'FY2027', 4, 0.08, 'v1', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.sales_mix_config WHERE fiscal_year='FY2027' AND month_seq=4 AND version='v1');
INSERT INTO bidb.sales_mix_config (fiscal_year, month_seq, mix_pct, version, creator)
SELECT 'FY2027', 5, 0.08, 'v1', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.sales_mix_config WHERE fiscal_year='FY2027' AND month_seq=5 AND version='v1');
INSERT INTO bidb.sales_mix_config (fiscal_year, month_seq, mix_pct, version, creator)
SELECT 'FY2027', 6, 0.08, 'v1', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.sales_mix_config WHERE fiscal_year='FY2027' AND month_seq=6 AND version='v1');
INSERT INTO bidb.sales_mix_config (fiscal_year, month_seq, mix_pct, version, creator)
SELECT 'FY2027', 7, 0.09, 'v1', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.sales_mix_config WHERE fiscal_year='FY2027' AND month_seq=7 AND version='v1');
INSERT INTO bidb.sales_mix_config (fiscal_year, month_seq, mix_pct, version, creator)
SELECT 'FY2027', 8, 0.09, 'v1', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.sales_mix_config WHERE fiscal_year='FY2027' AND month_seq=8 AND version='v1');
INSERT INTO bidb.sales_mix_config (fiscal_year, month_seq, mix_pct, version, creator)
SELECT 'FY2027', 9, 0.09, 'v1', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.sales_mix_config WHERE fiscal_year='FY2027' AND month_seq=9 AND version='v1');
INSERT INTO bidb.sales_mix_config (fiscal_year, month_seq, mix_pct, version, creator)
SELECT 'FY2027', 10, 0.09, 'v1', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.sales_mix_config WHERE fiscal_year='FY2027' AND month_seq=10 AND version='v1');
INSERT INTO bidb.sales_mix_config (fiscal_year, month_seq, mix_pct, version, creator)
SELECT 'FY2027', 11, 0.09, 'v1', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.sales_mix_config WHERE fiscal_year='FY2027' AND month_seq=11 AND version='v1');
INSERT INTO bidb.sales_mix_config (fiscal_year, month_seq, mix_pct, version, creator)
SELECT 'FY2027', 12, 0.10, 'v1', 'sys' WHERE NOT EXISTS (SELECT 1 FROM bidb.sales_mix_config WHERE fiscal_year='FY2027' AND month_seq=12 AND version='v1');

-- END
