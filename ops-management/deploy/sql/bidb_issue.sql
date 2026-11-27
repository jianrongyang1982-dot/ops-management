-- ============================================================
-- 运营管理系统 - 系统报障与需求管理 建表脚本
-- 目标库：bidb
-- 5 张表：工单主表 / 流转记录 / 附件 / 岗位角色配置 / 站内消息
-- 执行方式：用 bidb 库的执行权限手工执行本脚本
-- ============================================================

-- ------------------------------------------------------------
-- 1. 工单主表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.ops_issue (
  id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  issue_no      VARCHAR(32)  NOT NULL                COMMENT '工单号 BK-YYYYMMDD-NNNN',
  issue_type    TINYINT      NOT NULL DEFAULT 1      COMMENT '类型：1=需求 2=BUG',
  title         VARCHAR(200) NOT NULL                COMMENT '标题',
  description   TEXT                                 COMMENT '详细描述（BUG 用；需求用 requirement_json）',
  requirement_json TEXT                              COMMENT '需求结构化字段JSON：背景/痛点/5W1H/详细需求/角色/建议方案（仅需求类型）',
  module        VARCHAR(100) NOT NULL DEFAULT ''     COMMENT '涉及模块 Affected modules',
  priority      TINYINT      NOT NULL DEFAULT 3      COMMENT '优先级：1=紧急 2=高 3=中 4=低',
  status        TINYINT      NOT NULL DEFAULT 1      COMMENT '状态：1待处理 2已指派 3处理中 4待验证 5已关闭 6已取消',
  reporter      VARCHAR(50)  NOT NULL                COMMENT '提交人 usercode',
  reporter_name VARCHAR(200) NOT NULL DEFAULT ''     COMMENT '提交人姓名（冗余）',
  assignee      VARCHAR(50)  NOT NULL DEFAULT ''     COMMENT '处理人 usercode',
  assignee_name VARCHAR(200) NOT NULL DEFAULT ''     COMMENT '处理人姓名（冗余）',
  assigned_by   VARCHAR(50)  NOT NULL DEFAULT ''     COMMENT '指派人 usercode',
  assigned_time DATETIME     DEFAULT NULL            COMMENT '指派时间',
  created_time  DATETIME     NOT NULL                COMMENT '创建时间',
  updated_time  DATETIME     NOT NULL                COMMENT '更新时间',
  closed_time   DATETIME     DEFAULT NULL            COMMENT '关闭时间',
  close_remark  VARCHAR(500) NOT NULL DEFAULT ''     COMMENT '关闭/退回备注',
  PRIMARY KEY (id),
  UNIQUE KEY uk_issue_no (issue_no),
  KEY idx_status (status),
  KEY idx_reporter (reporter),
  KEY idx_assignee (assignee),
  KEY idx_created (created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统报障-工单主表';

-- ------------------------------------------------------------
-- 2. 流转记录表（每次状态变更写一条）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.ops_issue_log (
  id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  issue_id     BIGINT       NOT NULL                COMMENT '工单ID',
  action       VARCHAR(30)  NOT NULL                COMMENT '动作：create/assign/start/process/verify/reject/reopen/cancel',
  action_name  VARCHAR(50)  NOT NULL DEFAULT ''     COMMENT '动作显示名',
  operator     VARCHAR(50)  NOT NULL DEFAULT ''     COMMENT '操作人 usercode',
  operator_name VARCHAR(200) NOT NULL DEFAULT ''    COMMENT '操作人姓名',
  content      TEXT                                 COMMENT '备注内容',
  created_time DATETIME     NOT NULL                COMMENT '操作时间',
  PRIMARY KEY (id),
  KEY idx_issue_time (issue_id, created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统报障-流转记录';

-- ------------------------------------------------------------
-- 3. 附件表（文件存服务器，库内只存路径）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.ops_issue_attachment (
  id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  issue_id    BIGINT       NOT NULL                COMMENT '工单ID',
  file_name   VARCHAR(255) NOT NULL                COMMENT '原始文件名',
  file_path   VARCHAR(500) NOT NULL                COMMENT '相对路径 uploads/issue/...',
  file_size   INT          NOT NULL DEFAULT 0      COMMENT '文件大小(字节)',
  file_type   VARCHAR(50)  NOT NULL DEFAULT ''     COMMENT 'MIME类型',
  uploader    VARCHAR(50)  NOT NULL DEFAULT ''     COMMENT '上传人',
  created_time DATETIME    NOT NULL                COMMENT '上传时间',
  PRIMARY KEY (id),
  KEY idx_issue (issue_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统报障-附件';

-- ------------------------------------------------------------
-- 4. 岗位角色配置表（ERP岗位 -> 系统角色）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.ops_issue_role_cfg (
  id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  postcode    VARCHAR(50)  NOT NULL                COMMENT 'ERP岗位编码',
  postname    VARCHAR(200) NOT NULL DEFAULT ''     COMMENT 'ERP岗位名称',
  role        VARCHAR(20)  NOT NULL                COMMENT '角色：IT_ADMIN / HANDLER',
  status      TINYINT      NOT NULL DEFAULT 1      COMMENT '状态：1=启用 0=停用',
  created_time DATETIME    NOT NULL                COMMENT '创建时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_post_role (postcode, role),
  KEY idx_role (role, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统报障-岗位角色配置';

-- ------------------------------------------------------------
-- 5. 站内消息表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.ops_issue_message (
  id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  receiver    VARCHAR(50)  NOT NULL                COMMENT '接收人 usercode',
  issue_id    BIGINT       NOT NULL                COMMENT '工单ID',
  type        VARCHAR(30)  NOT NULL                COMMENT '类型：ASSIGNED/PROCESSED/VERIFIED/REJECTED/REOPENED',
  title       VARCHAR(200) NOT NULL DEFAULT ''     COMMENT '消息标题',
  content     VARCHAR(500) NOT NULL DEFAULT ''     COMMENT '消息内容',
  is_read     TINYINT      NOT NULL DEFAULT 0      COMMENT '是否已读：0=未读 1=已读',
  created_time DATETIME    NOT NULL                COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_receiver_read (receiver, is_read),
  KEY idx_issue (issue_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统报障-站内消息';

-- ============================================================
-- 执行后校验（可选）
-- ============================================================
-- SHOW TABLES FROM bidb LIKE 'ops_issue%';
