-- ============================================================
-- 运营管理系统 - 菜单 / 角色 / 权限 / 个人收藏 建表脚本
-- 目标库：bidb
-- 5 张表：菜单 / 角色 / 员工-角色 / 角色-菜单 / 个人收藏
-- 执行方式：用 bidb 库的执行权限手工执行本脚本
-- 权限模型：员工(ucsdb.account) -> 角色 -> 菜单；未分配角色时默认全部菜单（兼容升级）
-- ============================================================

-- ------------------------------------------------------------
-- 1. 菜单表（含分组信息，前端按 group_code 聚合渲染）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.ops_menu (
  id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  menu_code     VARCHAR(100) NOT NULL                COMMENT '菜单编码=前端路由path',
  menu_name     VARCHAR(100) NOT NULL                COMMENT '菜单中文名',
  menu_name_en  VARCHAR(100) NOT NULL DEFAULT ''     COMMENT '菜单英文名',
  path          VARCHAR(200) NOT NULL                COMMENT '前端路由地址',
  icon          VARCHAR(50)  NOT NULL DEFAULT ''     COMMENT 'Element Plus 图标名',
  group_code    VARCHAR(50)  NOT NULL DEFAULT ''     COMMENT '菜单分组编码',
  group_name    VARCHAR(100) NOT NULL DEFAULT ''     COMMENT '分组中文名',
  group_name_en VARCHAR(100) NOT NULL DEFAULT ''     COMMENT '分组英文名',
  group_sort    INT          NOT NULL DEFAULT 0      COMMENT '分组排序',
  sort_no       INT          NOT NULL DEFAULT 0      COMMENT '菜单排序',
  status        TINYINT      NOT NULL DEFAULT 1      COMMENT '状态：1启用 0停用',
  created_time  DATETIME     NOT NULL                COMMENT '创建时间',
  updated_time  DATETIME     NOT NULL                COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_menu_code (menu_code),
  KEY idx_group (group_code, sort_no),
  KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='菜单定义';

-- ------------------------------------------------------------
-- 2. 角色表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.ops_role (
  id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  role_code    VARCHAR(50)  NOT NULL                COMMENT '角色编码',
  role_name    VARCHAR(100) NOT NULL                COMMENT '角色名称',
  role_name_en VARCHAR(100) NOT NULL DEFAULT ''     COMMENT '角色英文名',
  remark       VARCHAR(500) NOT NULL DEFAULT ''     COMMENT '说明',
  is_admin     TINYINT      NOT NULL DEFAULT 0      COMMENT '是否超级管理员：1=拥有全部菜单',
  status       TINYINT      NOT NULL DEFAULT 1      COMMENT '状态：1启用 0停用',
  created_time DATETIME     NOT NULL                COMMENT '创建时间',
  updated_time DATETIME     NOT NULL                COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_role_code (role_code),
  KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色定义';

-- ------------------------------------------------------------
-- 3. 员工-角色关联（员工账号来自 ucsdb.account.usercode）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.ops_user_role (
  id           BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
  usercode     VARCHAR(50) NOT NULL                COMMENT '员工账号',
  role_code    VARCHAR(50) NOT NULL                COMMENT '角色编码',
  created_time DATETIME    NOT NULL                COMMENT '分配时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_role (usercode, role_code),
  KEY idx_usercode (usercode),
  KEY idx_role (role_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='员工-角色关联';

-- ------------------------------------------------------------
-- 4. 角色-菜单授权
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.ops_role_menu (
  id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  role_code    VARCHAR(50)  NOT NULL                COMMENT '角色编码',
  menu_code    VARCHAR(100) NOT NULL                COMMENT '菜单编码',
  created_time DATETIME     NOT NULL                COMMENT '授权时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_role_menu (role_code, menu_code),
  KEY idx_role (role_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色-菜单授权';

-- ------------------------------------------------------------
-- 5. 个人收藏菜单
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bidb.ops_user_favorite (
  id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  usercode     VARCHAR(50)  NOT NULL                COMMENT '员工账号',
  menu_code    VARCHAR(100) NOT NULL                COMMENT '菜单编码',
  sort_no      INT          NOT NULL DEFAULT 0      COMMENT '排序',
  created_time DATETIME     NOT NULL                COMMENT '收藏时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_menu (usercode, menu_code),
  KEY idx_usercode (usercode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='个人收藏菜单';

-- ============================================================
-- 初始化菜单数据（幂等：重复执行不会插入重复记录）
-- 使用 INSERT ... SELECT WHERE NOT EXISTS 兼容 OceanBase/MySQL
-- ============================================================
INSERT INTO bidb.ops_menu
  (menu_code, menu_name, menu_name_en, path, icon, group_code, group_name, group_name_en, group_sort, sort_no, status, created_time, updated_time)
SELECT * FROM (
  SELECT '/home' AS mc, '首页' AS mn, 'Home' AS mne, '/home' AS p, 'House' AS ic, 'home' AS gc, '首页' AS gn, 'Home' AS gne, 0 AS gs, 0 AS so
  UNION ALL SELECT '/container/list', '集装箱跟踪', 'Container Tracking', '/container/list', 'DataBoard', 'container-group', '集装箱', 'Containers', 10, 1
  UNION ALL SELECT '/container/dashboard', '集装箱看板', 'Container Dashboard', '/container/dashboard', 'DataBoard', 'container-group', '集装箱', 'Containers', 10, 2
  UNION ALL SELECT '/performance/coefficients', '绩效系数', 'Performance Coefficient', '/performance/coefficients', 'Setting', 'performance-group', '绩效', 'Performance', 20, 1
  UNION ALL SELECT '/performance/employee', '员工绩效', 'Employee Performance', '/performance/employee', 'User', 'performance-group', '绩效', 'Performance', 20, 2
  UNION ALL SELECT '/bu/definition', 'BU定义', 'BU Definition', '/bu/definition', 'Setting', 'bu-group', 'OTB设定', 'OTB Settings', 30, 1
  UNION ALL SELECT '/bu/brand', 'BU-品牌关系', 'BU-Brand Relation', '/bu/brand', 'OfficeBuilding', 'bu-group', 'OTB设定', 'OTB Settings', 30, 2
  UNION ALL SELECT '/otb/brand-category', '品牌-品类关系', 'Brand-Category Relation', '/otb/brand-category', 'Connection', 'bu-group', 'OTB设定', 'OTB Settings', 30, 3
  UNION ALL SELECT '/otb/sales-curve', '月度销售曲线', 'Monthly Sales Curve', '/otb/sales-curve', 'TrendCharts', 'bu-group', 'OTB设定', 'OTB Settings', 30, 4
  UNION ALL SELECT '/otb/dashboard', 'OTB看板', 'OTB Dashboard', '/otb/dashboard', 'DataBoard', 'otb-group', 'OTB与商品补货', 'OTB & Replenishment', 40, 1
  UNION ALL SELECT '/otb/category', '品类Sale Mix', 'Category Sale Mix', '/otb/category', 'Grid', 'otb-group', 'OTB与商品补货', 'OTB & Replenishment', 40, 2
  UNION ALL SELECT '/otb/brand', '品牌汇总', 'Brand Summary', '/otb/brand', 'Shop', 'otb-group', 'OTB与商品补货', 'OTB & Replenishment', 40, 3
  UNION ALL SELECT '/otb/replenishment', '商品订货补货', 'Item Replenishment', '/otb/replenishment', 'ShoppingCart', 'otb-group', 'OTB与商品补货', 'OTB & Replenishment', 40, 4
  UNION ALL SELECT '/issue/my', '我的报障', 'My Issues', '/issue/my', 'Document', 'issue-group', '系统报障', 'Issue Tracking', 50, 1
  UNION ALL SELECT '/issue/monitor', 'IT 监控台', 'IT Monitor', '/issue/monitor', 'DataBoard', 'issue-group', '系统报障', 'Issue Tracking', 50, 2
  UNION ALL SELECT '/issue/assigned', '我处理的', 'Assigned to Me', '/issue/assigned', 'Tools', 'issue-group', '系统报障', 'Issue Tracking', 50, 3
  UNION ALL SELECT '/issue/roles', '角色配置', 'Role Config', '/issue/roles', 'Setting', 'issue-group', '系统报障', 'Issue Tracking', 50, 4
  UNION ALL SELECT '/system/login-log', '登录日志', 'Login Log', '/system/login-log', 'Document', 'system-group', '系统管理', 'System', 60, 1
  UNION ALL SELECT '/system/online-users', '在线人员', 'Online Users', '/system/online-users', 'User', 'system-group', '系统管理', 'System', 60, 2
  UNION ALL SELECT '/system/change-password', '修改密码', 'Change Password', '/system/change-password', 'Lock', 'system-group', '系统管理', 'System', 60, 3
  UNION ALL SELECT '/system/permission', '菜单权限配置', 'Menu Permission', '/system/permission', 'Setting', 'system-group', '系统管理', 'System', 60, 4
) t
WHERE NOT EXISTS (SELECT 1 FROM bidb.ops_menu m WHERE m.menu_code = t.mc);

-- ------------------------------------------------------------
-- 初始化角色：超级管理员（拥有全部菜单）
-- ------------------------------------------------------------
INSERT INTO bidb.ops_role (role_code, role_name, role_name_en, remark, is_admin, status, created_time, updated_time)
SELECT 'ADMIN', '系统管理员', 'Administrator', '拥有全部菜单权限', 1, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM bidb.ops_role r WHERE r.role_code = 'ADMIN');

-- 初始化角色：普通员工（默认无授权菜单，按需在页面勾选）
INSERT INTO bidb.ops_role (role_code, role_name, role_name_en, remark, is_admin, status, created_time, updated_time)
SELECT 'STAFF', '普通员工', 'Staff', '基础角色，具体菜单按需授权', 0, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM bidb.ops_role r WHERE r.role_code = 'STAFF');

-- 超级管理员授权全部现有菜单
INSERT INTO bidb.ops_role_menu (role_code, menu_code, created_time)
SELECT 'ADMIN', m.menu_code, NOW() FROM bidb.ops_menu m
WHERE NOT EXISTS (
  SELECT 1 FROM bidb.ops_role_menu rm WHERE rm.role_code = 'ADMIN' AND rm.menu_code = m.menu_code
);

-- ------------------------------------------------------------
-- 验证
-- ------------------------------------------------------------
-- SELECT group_code, menu_code, menu_name FROM bidb.ops_menu ORDER BY group_sort, sort_no;
-- SELECT * FROM bidb.ops_role;
