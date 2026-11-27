-- ============================================================
-- 运营管理系统 - 登录日志 / 在线人员 建表脚本
-- 目标库：bidb
-- 说明：本系统自建表，不沿用 ERP 的 logdb.loginlog
-- 执行方式：用 bidb 库的执行权限手工执行本脚本
-- ============================================================

-- ------------------------------------------------------------
-- 1. 登录日志表
--    记录本系统的每一次登录尝试（成功 / 失败都记录）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.ops_login_log (
  id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  usercode    VARCHAR(50)  NOT NULL                COMMENT '账号',
  username    VARCHAR(200) NOT NULL DEFAULT ''     COMMENT '姓名',
  terminal    VARCHAR(20)  NOT NULL DEFAULT 'PC-WEB' COMMENT '终端平台',
  product     VARCHAR(50)  NOT NULL DEFAULT 'web'  COMMENT '产品',
  device      VARCHAR(255) NOT NULL DEFAULT ''     COMMENT '设备信息',
  success     TINYINT      NOT NULL DEFAULT 1      COMMENT '是否成功：1=成功 0=失败',
  client_ip   VARCHAR(50)  NOT NULL DEFAULT ''     COMMENT '客户端IP',
  cost_ms     INT          NOT NULL DEFAULT 0      COMMENT '消耗时间(毫秒)',
  login_time  DATETIME     NOT NULL                COMMENT '登录时间',
  remark      VARCHAR(255) NOT NULL DEFAULT ''     COMMENT '备注（失败原因等）',
  create_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '写入时间',
  PRIMARY KEY (id),
  KEY idx_usercode (usercode),
  KEY idx_login_time (login_time),
  KEY idx_user_time (usercode, login_time),
  KEY idx_success_time (success, login_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='运营系统-登录日志';

-- ------------------------------------------------------------
-- 2. 在线人员表
--    每个账号一条记录（uk_usercode 唯一），登录时 upsert，后台退出时置 status=0
--    岗位名称 / 部门名称在登录时从 ucsdb 字典表取快照写入，查询时只读本表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.ops_online_user (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  usercode        VARCHAR(50)  NOT NULL                COMMENT '账号',
  username        VARCHAR(200) NOT NULL DEFAULT ''     COMMENT '姓名',
  terminal        VARCHAR(20)  NOT NULL DEFAULT 'PC-WEB' COMMENT '终端平台',
  product         VARCHAR(50)  NOT NULL DEFAULT 'web'  COMMENT '产品',
  postname        VARCHAR(200) NOT NULL DEFAULT ''     COMMENT '岗位名称',
  deptname        VARCHAR(200) NOT NULL DEFAULT ''     COMMENT '部门名称',
  client_ip       VARCHAR(50)  NOT NULL DEFAULT ''     COMMENT '客户端IP',
  device          VARCHAR(255) NOT NULL DEFAULT ''     COMMENT '设备信息',
  login_time      DATETIME     NOT NULL                COMMENT '登录时间',
  last_active_time DATETIME    NOT NULL                COMMENT '最后活跃时间',
  status          TINYINT      NOT NULL DEFAULT 1      COMMENT '状态：1=在线 0=已退出',
  logout_time     DATETIME     DEFAULT NULL            COMMENT '退出时间',
  logout_reason   VARCHAR(100) NOT NULL DEFAULT ''     COMMENT '退出原因',
  create_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '首次登录时间',
  update_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_usercode (usercode),
  KEY idx_status_login (status, login_time),
  KEY idx_active (last_active_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='运营系统-在线人员';

-- ============================================================
-- 执行后校验（可选）
-- ============================================================
-- SHOW CREATE TABLE bidb.ops_login_log\G
-- SHOW CREATE TABLE bidb.ops_online_user\G
