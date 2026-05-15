-- =============================================================================
-- PostgreSQL 初始化脚本
-- Story 1.5: PostgreSQL Relational Layer
-- =============================================================================
-- 说明：基础初始化，仅创建扩展和基本配置
-- 表结构由 Alembic 迁移脚本创建 (deploy/postgresql/alembic/versions/001_initial.py)
-- =============================================================================

-- 启用 UUID 扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 启用 JSONB 支持
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 设置默认时区
SET timezone = 'UTC';

-- 创建应用用户（可选，生产环境使用独立用户）
-- CREATE USER sisys_app WITH PASSWORD 'app_password';   -- pragma: allowlist secret
-- CREATE USER sisys_reader WITH PASSWORD 'reader_password';   -- pragma: allowlist secret

-- 授予权限（如果用户存在）
-- GRANT CONNECT ON DATABASE sisys TO sisys_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sisys_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sisys_app;

-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO sisys_reader;
-- GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sisys_reader;

-- 记录初始化完成
DO $$
BEGIN
    RAISE NOTICE 'PostgreSQL initialization completed successfully';
END $$;
