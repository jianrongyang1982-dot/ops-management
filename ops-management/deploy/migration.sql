-- 数据库变更脚本
-- 1. 新增 voyage 字段（存飞驼返回的航次）
ALTER TABLE transit_containers
ADD COLUMN IF NOT EXISTS voyage varchar(50) DEFAULT NULL COMMENT '航次' AFTER ship_name;

-- 2. creator 字段确认为字符串类型（用户已改，此处仅为记录，若未改可执行）
-- ALTER TABLE transit_containers MODIFY COLUMN creator varchar(50) DEFAULT NULL COMMENT '创建人登录账号';
