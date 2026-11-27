-- ============================================================
-- 系统报障/需求模块：需求结构化字段表结构变更
-- 目标库：bidb
-- 背景：需求类型工单改用图片中的标准需求申请单模板，
--       新增 6 个结构化字段，统一存到一个 JSON 列中。
-- 执行方式：用 bidb 库的执行权限手工执行本脚本（可重复执行，幂等）。
-- ============================================================

-- 字段说明（requirement_json 内的键）：
--   background          业务背景与现状 / Business Background & Current Situation
--   pain_points         业务问题与痛点 / Business Problem & Pain Points
--   scenario_5w1h       需求场景 (5W1H) / Business Scenario (5W1H)
--   detailed_description 详细需求描述 / Detailed Requirement Description
--   roles               业务场景角色 / Business Roles Involved
--   proposed_solution   建议解决方案 / Proposed Solution
--
-- 说明：
--   “涉及模块”沿用 ops_issue.module 列
--   “需求名称”沿用 ops_issue.title 列
--   “关联附件”沿用 bidb.ops_issue_attachment 表
--   “优先级”沿用 ops_issue.priority 列

-- ------------------------------------------------------------
-- 幂等新增 requirement_json 列（OceanBase / MySQL 均适用）
-- ------------------------------------------------------------
SET @col_exists = (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'bidb'
    AND TABLE_NAME = 'ops_issue'
    AND COLUMN_NAME = 'requirement_json'
);

SET @ddl = IF(
  @col_exists = 0,
  'ALTER TABLE bidb.ops_issue ADD COLUMN requirement_json TEXT NULL COMMENT ''需求结构化字段JSON（仅需求类型）'' AFTER description',
  'SELECT ''requirement_json 已存在，跳过'' AS msg'
);

PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 如果你的客户端不支持 PREPARE，可直接执行下面这一条（重复执行会报列已存在）：
-- ALTER TABLE bidb.ops_issue
--   ADD COLUMN requirement_json TEXT NULL
--   COMMENT '需求结构化字段JSON（仅需求类型）' AFTER description;

-- ------------------------------------------------------------
-- 验证
-- ------------------------------------------------------------
-- SHOW COLUMNS FROM bidb.ops_issue LIKE 'requirement_json';
