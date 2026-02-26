# 附录 L：数据库 ER 图与表结构设计

**副标题：** 企业战略规划管理系统 - 完整数据库设计

**版本：** 1.0.0
**状态：** 已批准
**创建日期：** 2026-02-25
**评审日期：** 2026-02-25

**关联文档：**
- 架构设计文档 v6.0.0 - 第 9 章 领域实体完整定义
- 架构设计文档 v6.0.0 - 第 11 章 存储架构设计
- Saga 事务一致性设计方案 - 第 7 章 Saga 配置管理

---

## 文档目录

1. [数据库架构概述](#1-数据库架构概述)
2. [概念 ER 图](#2-概念-er-图)
3. [逻辑数据模型](#3-逻辑数据模型)
4. [物理表结构](#4-物理表结构)
5. [索引设计](#5-索引设计)
6. [多租户 Schema 设计](#6-多租户-schema-设计)
7. [数据迁移策略](#7-数据迁移策略)

---

## 1. 数据库架构概述

### 1.1 数据库技术选型

| 数据库 | 用途 | 版本 | 部署方式 |
|--------|------|------|---------|
| **PostgreSQL** | 主数据库（元数据、业务实体） | 15+ | 主从复制 |
| **Redis** | 缓存层（会话、状态快照） | 7.0+ | 集群模式 |
| **Qdrant** | 向量数据库（嵌入向量） | 1.7+ | 分布式 |
| **Neo4j** | 图数据库（知识图谱） | 5.x | 因果集群 |
| **MinIO** | 对象存储（文档、证据包） | 最新 | 分布式 WORM |

### 1.2 PostgreSQL 数据库设计原则

- **六边形架构**：领域层不依赖数据库实现
- **CQRS 模式**：命令侧和查询侧分离
- **事件溯源**：关键业务操作记录事件
- **多租户隔离**：Schema per Tenant（专业版及以上）
- **审计追踪**：所有变更自动记录审计日志

### 1.3 数据库连接配置

```python
# 数据库连接池配置
DATABASE_CONFIG = {
    "host": "postgres-primary.internal",
    "port": 5432,
    "database": "sisys",
    "user": "sisys_app",
    "password": "${DB_PASSWORD}",
    
    # 连接池配置
    "pool_size": 20,
    "max_overflow": 40,
    "pool_timeout": 30,
    "pool_recycle": 1800,
    
    # SSL 配置
    "ssl_mode": "require",
    "ssl_cert": "/etc/ssl/certs/postgresql.crt",
    "ssl_key": "/etc/ssl/private/postgresql.key",
    "ssl_rootcert": "/etc/ssl/certs/ca-bundle.crt"
}
```

---

## 2. 概念 ER 图

### 2.1 核心实体关系

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    企业战略规划管理系统 - 概念 ER 图                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐          │
│  │   Tenant     │      │    User      │      │    Agent     │          │
│  │   租户       │      │    用户      │      │   Agent      │          │
│  ├──────────────┤      ├──────────────┤      ├──────────────┤          │
│  │ id           │      │ id           │      │ id           │          │
│  │ name         │      │ tenant_id ◄──┼──────│ tenant_id    │          │
│  │ slug         │      │ email        │      │ role         │          │
│  │ tier         │      │ password_hash│      │ identity     │          │
│  │ status       │      │ status       │      │ state        │          │
│  └──────┬───────┘      └──────┬───────┘      └──────┬───────┘          │
│         │ 1:N                 │ 1:N                 │ 1:N              │
│         │                     │                     │                  │
│         ▼                     ▼                     ▼                  │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐          │
│  │    Role      │      │ User_Role    │      │    Tool      │          │
│  │    角色      │      │  用户角色关联 │      │    工具      │          │
│  ├──────────────┤      ├──────────────┤      ├──────────────┤          │
│  │ id           │      │ user_id      │      │ id           │          │
│  │ tenant_id    │      │ role_id      │      │ tenant_id    │          │
│  │ name         │      │ granted_at   │      │ name         │          │
│  │ permissions  │      │ granted_by   │      │ version      │          │
│  └──────────────┘      └──────────────┘      │ agent_id ◄───┼──┐       │
│         │ 1:N                                │ config       │  │       │
│         │                                    └──────────────┘  │       │
│         ▼                                                      │       │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │       │
│  │Role_Permission│     │  Permission  │      │StrategicPlan │◄─┘       │
│  │ 角色权限关联  │     │    权限      │      │   战略规划    │          │
│  ├──────────────┤     ├──────────────┤     ├──────────────┤          │
│  │ role_id      │     │ id           │     │ id           │          │
│  │ permission_id│     │ tenant_id    │     │ tenant_id    │          │
│  │ resource_scope│    │ code         │     │ creator_id ◄─┼──────┐   │
│  └──────────────┘     │ name         │     │ plan_type    │      │   │
│                       │ resource_type│     │ blm_stage    │      │   │
│                       │ actions      │     │ status       │      │   │
│                       └──────────────┘     │ evidence_ref │      │   │
│                                            └──────┬───────┘      │   │
│                                                   │ 1:N          │   │
│                                                   ▼              │   │
│                                            ┌──────────────┐     │   │
│                                            │  Checkpoint  │     │   │
│                                            │   检查点     │     │   │
│                                            ├──────────────┤     │   │
│                                            │ id           │     │   │
│                                            │ plan_id      │     │   │
│                                            │ stage_id     │     │   │
│                                            │ state_snapshot│    │   │
│                                            │ recovery_mode│     │   │
│                                            │ branch_id    │◄────┘   │
│                                            └──────────────┘          │
│                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 实体关系说明

| 关系 | 类型 | 说明 |
|------|------|------|
| Tenant → User | 1:N | 一个租户拥有多个用户 |
| Tenant → Agent | 1:N | 一个租户拥有多个 Agent |
| Tenant → Role | 1:N | 一个租户拥有多个角色 |
| Tenant → StrategicPlan | 1:N | 一个租户拥有多个战略规划 |
| User ↔ Role | M:N | 用户通过 User_Role 关联多个角色 |
| Role ↔ Permission | M:N | 角色通过 Role_Permission 关联多个权限 |
| Agent → Tool | 1:N | 一个 Agent 拥有多个工具 |
| StrategicPlan → Checkpoint | 1:N | 一个规划有多个检查点 |

---

## 3. 逻辑数据模型

### 3.1 租户管理模块

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    租户管理模块数据模型                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐                                                   │
│  │     tenant      │                                                   │
│  ├─────────────────┤                                                   │
│  │ id (PK)         │                                                   │
│  │ name            │                                                   │
│  │ slug            │                                                   │
│  │ tier            │                                                   │
│  │ status          │                                                   │
│  │ data_residency  │                                                   │
│  │ settings        │                                                   │
│  │ max_users       │                                                   │
│  │ max_storage     │                                                   │
│  │ features        │                                                   │
│  │ created_at      │                                                   │
│  │ expires_at      │                                                   │
│  └─────────────────┘                                                   │
│           │                                                           │
│           │ 1:N                                                       │
│           ▼                                                           │
│  ┌─────────────────┐      ┌─────────────────┐                         │
│  │   tenant_user   │      │  tenant_schema  │                         │
│  ├─────────────────┤      ├─────────────────┤                         │
│  │ id (PK)         │      │ id (PK)         │                         │
│  │ tenant_id (FK)  │      │ tenant_id (FK)  │                         │
│  │ user_id (FK)    │      │ schema_name     │                         │
│  │ role            │      │ created_at      │                         │
│  │ status          │      │ status          │                         │
│  │ created_at      │      └─────────────────┘                         │
│  └─────────────────┘                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 用户与权限模块

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    用户与权限模块数据模型                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐                                                   │
│  │      user       │                                                   │
│  ├─────────────────┤                                                   │
│  │ id (PK)         │                                                   │
│  │ tenant_id (FK)  │                                                   │
│  │ email           │                                                   │
│  │ password_hash   │                                                   │
│  │ display_name    │                                                   │
│  │ avatar_url      │                                                   │
│  │ status          │                                                   │
│  │ last_login_at   │                                                   │
│  │ created_at      │                                                   │
│  └─────────────────┘                                                   │
│           │                                                           │
│           │ M:N (通过 user_role)                                       │
│           ▼                                                           │
│  ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐│
│  │    user_role    │      │     role        │      │   permission    ││
│  ├─────────────────┤      ├─────────────────┤      ├─────────────────┤│
│  │ id (PK)         │      │ id (PK)         │      │ id (PK)         ││
│  │ user_id (FK)    │      │ tenant_id (FK)  │      │ tenant_id (FK)  ││
│  │ role_id (FK)    │◄─────│ name            │◄─────│ code            ││
│  │ granted_at      │      │ code            │      │ name            ││
│  │ granted_by (FK) │      │ description     │      │ resource_type   ││
│  └─────────────────┘      │ is_system_role  │      │ actions         ││
│                           └─────────────────┘      │ description     ││
│                                    │ 1:N           └─────────────────┘│
│                                    ▼                                  │
│                           ┌─────────────────┐                         │
│                           │ role_permission │                         │
│                           ├─────────────────┤                         │
│                           │ id (PK)         │                         │
│                           │ role_id (FK)    │                         │
│                           │ permission_id (FK)│                       │
│                           │ resource_scope  │                         │
│                           └─────────────────┘                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 战略规划模块

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    战略规划模块数据模型                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    strategic_plan                               │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │ id (PK)                         │ plan_type (SP/BP)             │   │
│  │ tenant_id (FK)                  │ blm_stage / bem_stage         │   │
│  │ creator_id (FK)                 │ status                        │   │
│  │ title                           │ current_stage_id (FK)         │   │
│  │ description                     │ evidence_package_ref          │   │
│  │ sp_ref (FK, BP 专用)            │ version                       │   │
│  │ created_at                      │ updated_at                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│           │                                                             │
│           │ 1:N                                                         │
│           ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      checkpoint                                 │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │ id (PK)                         │ stage_name                    │   │
│  │ plan_id (FK)                    │ stage_status                  │   │
│  │ stage_id                        │ state_snapshot (JSONB)        │   │
│  │ stage_sequence                  │ recovery_mode                 │   │
│  │ entered_at                      │ completed_at                  │   │
│  │ branch_id (自引用)              │ parent_checkpoint_id (自引用) │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.4 Agent 与工具模块

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Agent 与工具模块数据模型                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        agent                                    │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │ id (PK)                         │ role (CEO/CFO/CMO/...)        │   │
│  │ tenant_id (FK)                  │ identity (JSONB)              │   │
│  │ owner_id (FK)                   │ status                        │   │
│  │ name                            │ isolation_level               │   │
│  │ description                     │ state_snapshot (JSONB)        │   │
│  │ created_at                      │ updated_at                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│           │                                                             │
│           │ 1:N                                                         │
│           ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        tool                                     │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │ id (PK)                         │ version                       │   │
│  │ tenant_id (FK)                  │ input_schema (JSONB)          │   │
│  │ agent_id (FK)                   │ output_schema (JSONB)         │   │
│  │ name                            │ config (JSONB)                │   │
│  │ description                     │ reliability_score             │   │
│  │ enabled                         │ last_executed_at              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.5 审计日志模块

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    审计日志模块数据模型                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐ │
│  │routing_decision │      │isolation_switch │      │  saga_audit_log │ │
│  │      _log       │      │      _log       │      │                 │ │
│  ├─────────────────┤      ├─────────────────┤      ├─────────────────┤ │
│  │ id (PK)         │      │ id (PK)         │      │ id (PK)         │ │
│  │ tenant_id (FK)  │      │ tenant_id (FK)  │      │ tenant_id (FK)  │ │
│  │ task_id         │      │ agent_id (FK)   │      │ saga_id         │ │
│  │ l1_result (JSONB)│     │ from_level      │      │ saga_type       │ │
│  │ l2_scores (JSONB)│     │ to_level        │      │ status          │ │
│  │ l3_decision     │      │ trigger         │      │ started_at      │ │
│  │ estimated_cost  │      │ triggered_by    │      │ completed_at    │ │
│  │ actual_cost     │      │ worm_ref        │      │ worm_ref        │ │
│  │ routing_latency │      │ created_at      │      │ error_message   │ │
│  │ created_at      │      └─────────────────┘      └─────────────────┘ │
│  │ worm_ref        │                                                    │
│  └─────────────────┘                                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 物理表结构

### 4.1 租户管理表

```sql
-- ============================================================================
-- 租户表
-- ============================================================================
CREATE TABLE tenant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(50) NOT NULL UNIQUE,
    tier VARCHAR(20) NOT NULL DEFAULT 'basic',  -- basic/professional/enterprise/government
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active/suspended/expired
    data_residency VARCHAR(20) NOT NULL DEFAULT 'global',  -- global/china_domestic/eu_gdpr/us_only
    settings JSONB NOT NULL DEFAULT '{}',
    max_users INTEGER NOT NULL DEFAULT 100,
    max_storage_bytes BIGINT NOT NULL DEFAULT 10737418240,  -- 10GB
    features TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_tenant_slug ON tenant(slug);
CREATE INDEX idx_tenant_status ON tenant(status);
CREATE INDEX idx_tenant_tier ON tenant(tier);
CREATE INDEX idx_tenant_expires_at ON tenant(expires_at);

-- 触发器：自动更新 updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tenant_updated_at
    BEFORE UPDATE ON tenant
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 租户 Schema 映射表
-- ============================================================================
CREATE TABLE tenant_schema (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    schema_name VARCHAR(100) NOT NULL UNIQUE,
    database_name VARCHAR(100),  -- Enterprise 租户独立数据库时使用
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
);

CREATE INDEX idx_tenant_schema_tenant ON tenant_schema(tenant_id);
CREATE INDEX idx_tenant_schema_status ON tenant_schema(status);

-- ============================================================================
-- 租户用户关联表
-- ============================================================================
CREATE TABLE tenant_user (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,  -- 引用用户表，可能是跨租户的
    role VARCHAR(50) NOT NULL DEFAULT 'member',  -- owner/admin/member/auditor
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    joined_at TIMESTAMPTZ,
    invited_by UUID,
    UNIQUE(tenant_id, user_id)
);

CREATE INDEX idx_tenant_user_tenant ON tenant_user(tenant_id);
CREATE INDEX idx_tenant_user_user ON tenant_user(user_id);
CREATE INDEX idx_tenant_user_status ON tenant_user(status);
```

### 4.2 用户与权限表

```sql
-- ============================================================================
-- 用户表
-- ============================================================================
CREATE TABLE "user" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    avatar_url TEXT,
    phone VARCHAR(20),
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active/inactive/locked
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_secret VARCHAR(255),
    last_login_at TIMESTAMPTZ,
    last_login_ip INET,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_user_email ON "user"(email);
CREATE INDEX idx_user_status ON "user"(status);
CREATE INDEX idx_user_created_at ON "user"(created_at);

-- 触发器
CREATE TRIGGER user_updated_at
    BEFORE UPDATE ON "user"
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 角色表
-- ============================================================================
CREATE TABLE role (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) NOT NULL,
    description TEXT,
    is_system_role BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, code)
);

CREATE INDEX idx_role_tenant ON role(tenant_id);
CREATE INDEX idx_role_code ON role(code);
CREATE INDEX idx_role_system ON role(is_system_role);

CREATE TRIGGER role_updated_at
    BEFORE UPDATE ON role
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 权限表
-- ============================================================================
CREATE TABLE permission (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenant(id) ON DELETE CASCADE,  -- NULL 表示系统权限
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    resource_type VARCHAR(50) NOT NULL,  -- document/plan/agent/tool/...
    actions TEXT[] NOT NULL,  -- [read, write, delete, approve]
    is_system_permission BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_permission_tenant ON permission(tenant_id);
CREATE INDEX idx_permission_code ON permission(code);
CREATE INDEX idx_permission_resource ON permission(resource_type);

-- ============================================================================
-- 用户角色关联表
-- ============================================================================
CREATE TABLE user_role (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES role(id) ON DELETE CASCADE,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by UUID,
    expires_at TIMESTAMPTZ,
    UNIQUE(user_id, role_id)
);

CREATE INDEX idx_user_role_user ON user_role(user_id);
CREATE INDEX idx_user_role_role ON user_role(role_id);

-- ============================================================================
-- 角色权限关联表
-- ============================================================================
CREATE TABLE role_permission (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES role(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permission(id) ON DELETE CASCADE,
    resource_scope VARCHAR(255),  -- 资源范围限制，如 plans:2026-*
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(role_id, permission_id, resource_scope)
);

CREATE INDEX idx_role_permission_role ON role_permission(role_id);
CREATE INDEX idx_role_permission_permission ON role_permission(permission_id);
```

### 4.3 战略规划表

```sql
-- ============================================================================
-- 战略规划表
-- ============================================================================
CREATE TABLE strategic_plan (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,  -- 多租户隔离，实际 Schema 隔离
    creator_id UUID NOT NULL REFERENCES "user"(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    plan_type VARCHAR(2) NOT NULL CHECK (plan_type IN ('SP', 'BP')),  -- SP/BP
    sp_ref UUID REFERENCES strategic_plan(id),  -- BP 关联的 SP
    blm_stage VARCHAR(50),  -- BLM 六阶段
    bem_stage VARCHAR(50),  -- BEM 六阶段
    status VARCHAR(20) NOT NULL DEFAULT 'draft',  -- draft/in_progress/in_review/approved/archived
    current_stage_id UUID,
    evidence_package_ref TEXT,  -- MinIO WORM 存储引用
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);

CREATE INDEX idx_strategic_plan_tenant ON strategic_plan(tenant_id);
CREATE INDEX idx_strategic_plan_creator ON strategic_plan(creator_id);
CREATE INDEX idx_strategic_plan_type ON strategic_plan(plan_type);
CREATE INDEX idx_strategic_plan_status ON strategic_plan(status);
CREATE INDEX idx_strategic_plan_sp_ref ON strategic_plan(sp_ref) WHERE sp_ref IS NOT NULL;

CREATE TRIGGER strategic_plan_updated_at
    BEFORE UPDATE ON strategic_plan
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 检查点表
-- ============================================================================
CREATE TABLE checkpoint (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES strategic_plan(id) ON DELETE CASCADE,
    stage_id VARCHAR(50) NOT NULL,
    stage_name VARCHAR(100) NOT NULL,
    stage_sequence INTEGER NOT NULL,
    stage_status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending/in_progress/completed/skipped
    state_snapshot JSONB NOT NULL DEFAULT '{}',
    recovery_mode VARCHAR(20) DEFAULT 'replay',  -- replay/override
    branch_id UUID,  -- 分支 ID，NULL 表示主线
    parent_checkpoint_id UUID REFERENCES checkpoint(id),  -- 自引用，用于分支
    entered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    completed_by UUID REFERENCES "user"(id),
    feedback TEXT,
    feedback_rating INTEGER CHECK (feedback_rating >= 1 AND feedback_rating <= 5)
);

CREATE INDEX idx_checkpoint_plan ON checkpoint(plan_id);
CREATE INDEX idx_checkpoint_stage ON checkpoint(stage_id);
CREATE INDEX idx_checkpoint_status ON checkpoint(stage_status);
CREATE INDEX idx_checkpoint_branch ON checkpoint(branch_id) WHERE branch_id IS NOT NULL;
CREATE INDEX idx_checkpoint_parent ON checkpoint(parent_checkpoint_id) WHERE parent_checkpoint_id IS NOT NULL;

-- ============================================================================
-- 规划修正表
-- ============================================================================
CREATE TABLE plan_correction (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES strategic_plan(id) ON DELETE CASCADE,
    checkpoint_id UUID REFERENCES checkpoint(id),
    correction_type VARCHAR(20) NOT NULL,  -- L0/L1/L2/L3
    description TEXT NOT NULL,
    proposed_by UUID NOT NULL REFERENCES "user"(id),
    proposed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending/approved/rejected/auto_consolidated
    reviewed_by UUID REFERENCES "user"(id),
    reviewed_at TIMESTAMPTZ,
    review_comments TEXT,
    consolidated_at TIMESTAMPTZ
);

CREATE INDEX idx_plan_correction_plan ON plan_correction(plan_id);
CREATE INDEX idx_plan_correction_checkpoint ON plan_correction(checkpoint_id);
CREATE INDEX idx_plan_correction_status ON plan_correction(status);
CREATE INDEX idx_plan_correction_type ON plan_correction(correction_type);
```

### 4.4 Agent 与工具表

```sql
-- ============================================================================
-- Agent 表
-- ============================================================================
CREATE TABLE agent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    owner_id UUID REFERENCES "user"(id),
    name VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL,  -- CEO/CFO/CMO/CTO/COO/CHO/AUD/SYS
    identity JSONB NOT NULL DEFAULT '{}',
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    isolation_level VARCHAR(20) NOT NULL DEFAULT 'L4',  -- L4/L3/L2/L1
    state_snapshot JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ
);

CREATE INDEX idx_agent_tenant ON agent(tenant_id);
CREATE INDEX idx_agent_owner ON agent(owner_id);
CREATE INDEX idx_agent_role ON agent(role);
CREATE INDEX idx_agent_status ON agent(status);

CREATE TRIGGER agent_updated_at
    BEFORE UPDATE ON agent
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 工具表
-- ============================================================================
CREATE TABLE tool (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    agent_id UUID REFERENCES agent(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    input_schema JSONB NOT NULL DEFAULT '{}',
    output_schema JSONB NOT NULL DEFAULT '{}',
    config JSONB DEFAULT '{}',
    reliability_score DECIMAL(3,2) DEFAULT 1.00,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    execution_count INTEGER NOT NULL DEFAULT 0,
    last_executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tool_tenant ON tool(tenant_id);
CREATE INDEX idx_tool_agent ON tool(agent_id);
CREATE INDEX idx_tool_enabled ON tool(enabled);

CREATE TRIGGER tool_updated_at
    BEFORE UPDATE ON tool
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 工具执行日志表
-- ============================================================================
CREATE TABLE tool_execution_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    tool_id UUID NOT NULL REFERENCES tool(id),
    agent_id UUID REFERENCES agent(id),
    input_data JSONB NOT NULL,
    output_data JSONB,
    status VARCHAR(20) NOT NULL,  -- success/failed/timeout
    error_message TEXT,
    execution_time_ms INTEGER,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_tool_execution_log_tool ON tool_execution_log(tool_id);
CREATE INDEX idx_tool_execution_log_status ON tool_execution_log(status);
CREATE INDEX idx_tool_execution_log_started ON tool_execution_log(started_at);

-- 分区表：2026 年 2 月 -2027 年 1 月（12 个月）
CREATE TABLE tool_execution_log_2026_02 PARTITION OF tool_execution_log
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE tool_execution_log_2026_03 PARTITION OF tool_execution_log
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE tool_execution_log_2026_04 PARTITION OF tool_execution_log
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE tool_execution_log_2026_05 PARTITION OF tool_execution_log
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE tool_execution_log_2026_06 PARTITION OF tool_execution_log
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE tool_execution_log_2026_07 PARTITION OF tool_execution_log
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE tool_execution_log_2026_08 PARTITION OF tool_execution_log
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE tool_execution_log_2026_09 PARTITION OF tool_execution_log
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE tool_execution_log_2026_10 PARTITION OF tool_execution_log
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE tool_execution_log_2026_11 PARTITION OF tool_execution_log
    FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE tool_execution_log_2026_12 PARTITION OF tool_execution_log
    FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');
CREATE TABLE tool_execution_log_2027_01 PARTITION OF tool_execution_log
    FOR VALUES FROM ('2027-01-01') TO ('2027-02-01');
```

### 4.5 审计日志表

```sql
-- ============================================================================
-- 路由决策日志表
-- ============================================================================
CREATE TABLE routing_decision_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    task_id UUID NOT NULL,
    l1_compliance_result JSONB NOT NULL,
    l2_model_scores JSONB NOT NULL,
    l3_routing_decision JSONB NOT NULL,
    estimated_cost DECIMAL(10,6),
    actual_cost DECIMAL(10,6),
    routing_latency_ms INTEGER,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    worm_storage_ref TEXT  -- WORM 存储引用（7 年归档）
);

CREATE INDEX idx_routing_decision_tenant ON routing_decision_log(tenant_id);
CREATE INDEX idx_routing_decision_task ON routing_decision_log(task_id);
CREATE INDEX idx_routing_decision_created ON routing_decision_log(created_at);

-- ============================================================================
-- 隔离切换日志表
-- ============================================================================
CREATE TABLE isolation_switch_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    from_level VARCHAR(20) NOT NULL,
    to_level VARCHAR(20) NOT NULL,
    trigger_type VARCHAR(50) NOT NULL,  -- sys_command/keyword_frequency/task_dependency/user_request
    triggered_by UUID,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    worm_storage_ref TEXT
);

CREATE INDEX idx_isolation_switch_tenant ON isolation_switch_log(tenant_id);
CREATE INDEX idx_isolation_switch_agent ON isolation_switch_log(agent_id);
CREATE INDEX idx_isolation_switch_created ON isolation_switch_log(created_at);

-- ============================================================================
-- Saga 审计日志表
-- ============================================================================
CREATE TABLE saga_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    saga_id UUID NOT NULL,
    saga_type VARCHAR(100) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    step_name VARCHAR(100),
    step_sequence INTEGER,
    error_message TEXT,
    context_snapshot JSONB,
    correlation_id VARCHAR(100),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    worm_storage_ref TEXT
);

CREATE INDEX idx_saga_audit_tenant ON saga_audit_log(tenant_id);
CREATE INDEX idx_saga_audit_saga ON saga_audit_log(saga_id);
CREATE INDEX idx_saga_audit_type ON saga_audit_log(saga_type);
CREATE INDEX idx_saga_audit_started ON saga_audit_log(started_at);

-- 分区表：2026 年 2 月 -2027 年 1 月（12 个月）
CREATE TABLE saga_audit_log_2026_02 PARTITION OF saga_audit_log
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE saga_audit_log_2026_03 PARTITION OF saga_audit_log
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE saga_audit_log_2026_04 PARTITION OF saga_audit_log
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE saga_audit_log_2026_05 PARTITION OF saga_audit_log
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE saga_audit_log_2026_06 PARTITION OF saga_audit_log
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE saga_audit_log_2026_07 PARTITION OF saga_audit_log
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE saga_audit_log_2026_08 PARTITION OF saga_audit_log
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE saga_audit_log_2026_09 PARTITION OF saga_audit_log
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE saga_audit_log_2026_10 PARTITION OF saga_audit_log
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE saga_audit_log_2026_11 PARTITION OF saga_audit_log
    FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE saga_audit_log_2026_12 PARTITION OF saga_audit_log
    FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');
CREATE TABLE saga_audit_log_2027_01 PARTITION OF saga_audit_log
    FOR VALUES FROM ('2027-01-01') TO ('2027-02-01');
```

### 4.6 Saga 配置表

```sql
-- ============================================================================
-- Saga 类型配置表
-- ============================================================================
CREATE TABLE saga_type_config (
    saga_type VARCHAR(100) PRIMARY KEY,
    description TEXT,
    consistency_requirement VARCHAR(20) NOT NULL,  -- strong/eventual
    saga_pattern VARCHAR(20) NOT NULL,  -- orchestration/choreography
    max_retries INTEGER NOT NULL DEFAULT 3,
    retry_delay_seconds INTEGER NOT NULL DEFAULT 5,
    step_timeout_seconds INTEGER NOT NULL DEFAULT 300,
    compensation_timeout_seconds INTEGER NOT NULL DEFAULT 60,
    dlq_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    audit_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Saga 步骤配置表
-- ============================================================================
CREATE TABLE saga_step_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    saga_type VARCHAR(100) NOT NULL REFERENCES saga_type_config(saga_type),
    step_name VARCHAR(100) NOT NULL,
    step_sequence INTEGER NOT NULL,
    handler_class VARCHAR(255) NOT NULL,
    timeout_seconds INTEGER NOT NULL DEFAULT 300,
    retry_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    compensation_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(saga_type, step_sequence),
    UNIQUE(saga_type, step_name)
);

CREATE INDEX idx_saga_step_saga_type ON saga_step_config(saga_type);

-- ============================================================================
-- Saga 执行历史表
-- ============================================================================
CREATE TABLE saga_execution_history (
    saga_id UUID PRIMARY KEY,
    saga_type VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    total_steps INTEGER NOT NULL,
    completed_steps INTEGER NOT NULL DEFAULT 0,
    failed_step_name VARCHAR(100),
    error_message TEXT,
    compensation_triggered BOOLEAN NOT NULL DEFAULT FALSE,
    retry_count INTEGER NOT NULL DEFAULT 0,
    correlation_id VARCHAR(100),
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_saga_execution_type ON saga_execution_history(saga_type);
CREATE INDEX idx_saga_execution_status ON saga_execution_history(status);
CREATE INDEX idx_saga_execution_started ON saga_execution_history(started_at);
```

### 4.7 事件发件箱表

```sql
-- ============================================================================
-- 事件发件箱表（事务性消息）
-- ============================================================================
CREATE TABLE event_outbox (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    event_payload JSONB NOT NULL,
    event_metadata JSONB DEFAULT '{}',
    aggregate_id UUID,
    aggregate_type VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending/published/failed/archived
    last_error TEXT,
    next_retry_at TIMESTAMPTZ
);

CREATE INDEX idx_event_outbox_status ON event_outbox(status);
CREATE INDEX idx_event_outbox_created ON event_outbox(created_at);
CREATE INDEX idx_event_outbox_type ON event_outbox(event_type);
CREATE INDEX idx_event_outbox_aggregate ON event_outbox(aggregate_id, aggregate_type);
CREATE INDEX idx_event_outbox_retry ON event_outbox(next_retry_at) WHERE status = 'pending';

-- 归档表（已发布超过 30 天的事件）
CREATE TABLE event_outbox_archive (
    LIKE event_outbox INCLUDING ALL
);
```

---

## 5. 索引设计

### 5.1 索引策略

| 索引类型 | 使用场景 | 注意事项 |
|---------|---------|---------|
| **B-Tree** | 等值查询、范围查询 | 默认索引类型 |
| **GIN** | JSONB 数组、全文检索 | 适合 JSONB 字段 |
| **GiST** | 地理位置、范围查询 | 特殊数据类型 |
| **BRIN** | 时间序列大表 | 块级索引，节省空间 |
| **部分索引** | 条件查询 | 只索引符合条件的行 |

### 5.2 核心表索引设计

```sql
-- ============================================================================
-- 战略规划表索引
-- ============================================================================

-- 组合索引：租户 + 状态 + 创建时间（常用查询）
CREATE INDEX idx_strategic_plan_tenant_status_created 
    ON strategic_plan(tenant_id, status, created_at DESC);

-- 组合索引：创建者 + 计划类型
CREATE INDEX idx_strategic_plan_creator_type 
    ON strategic_plan(creator_id, plan_type);

-- 部分索引：只索引进行中的规划
CREATE INDEX idx_strategic_plan_in_progress 
    ON strategic_plan(tenant_id, created_at DESC) 
    WHERE status IN ('draft', 'in_progress');

-- ============================================================================
-- 检查点表索引
-- ============================================================================

-- 组合索引：计划 + 阶段序列
CREATE INDEX idx_checkpoint_plan_sequence 
    ON checkpoint(plan_id, stage_sequence);

-- 组合索引：计划 + 分支 + 状态
CREATE INDEX idx_checkpoint_plan_branch_status 
    ON checkpoint(plan_id, branch_id, stage_status)
    WHERE branch_id IS NOT NULL;

-- ============================================================================
-- 审计日志表索引（BRIN 用于时间范围查询）
-- ============================================================================

-- BRIN 索引：时间范围查询（大表优化）
CREATE INDEX idx_routing_decision_log_created_brin 
    ON routing_decision_log USING BRIN(created_at);

CREATE INDEX idx_saga_audit_log_started_brin 
    ON saga_audit_log USING BRIN(started_at);

-- ============================================================================
-- JSONB 字段索引
-- ============================================================================

-- GIN 索引：Agent 身份档案
CREATE INDEX idx_agent_identity_gin 
    ON agent USING GIN(identity);

-- GIN 索引：检查点状态快照
CREATE INDEX idx_checkpoint_state_snapshot_gin 
    ON checkpoint USING GIN(state_snapshot);

-- 提取索引：JSONB 中的特定字段
CREATE INDEX idx_agent_role_extracted 
    ON agent((identity->>'role'));
```

### 5.3 索引维护策略

```sql
-- 定期重建索引（每月执行）
REINDEX TABLE CONCURRENTLY strategic_plan;
REINDEX TABLE checkpoint;

-- 分析表统计信息（每周执行）
ANALYZE strategic_plan;
ANALYZE checkpoint;
ANALYZE agent;
ANALYZE tool;

-- 清理未使用的索引（查询 pg_stat_user_indexes）
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY tablename, indexname;
```

---

## 6. 多租户 Schema 设计

### 6.1 Schema 创建脚本

```sql
-- ============================================================================
-- 创建租户 Schema 函数
-- ============================================================================
CREATE OR REPLACE FUNCTION create_tenant_schema(
    p_tenant_id UUID,
    p_tenant_slug VARCHAR
) RETURNS VOID AS $$
DECLARE
    v_schema_name TEXT;
    v_schema_tables TEXT[];
BEGIN
    -- 生成 Schema 名称
    v_schema_name := 'tenant_' || replace(p_tenant_id::text, '-', '_');

    -- 创建 Schema
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', v_schema_name);

    -- 设置 Schema 权限
    EXECUTE format('GRANT ALL ON SCHEMA %I TO sisys_app', v_schema_name);

    -- 复制表结构到租户 Schema
    v_schema_tables := ARRAY[
        'strategic_plan', 'checkpoint', 'plan_correction',
        'agent', 'tool', 'tool_execution_log',
        'routing_decision_log', 'isolation_switch_log',
        'document', 'saga_audit_log'
    ];

    FOREACH table_name IN ARRAY v_schema_tables
    LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I.%I (LIKE public.%I INCLUDING ALL)',
            v_schema_name, table_name, table_name
        );
    END LOOP;

    -- 记录 Schema 创建
    INSERT INTO tenant_schema (tenant_id, schema_name, created_at)
    VALUES (p_tenant_id, v_schema_name, NOW());

    RAISE NOTICE 'Tenant schema % created successfully', v_schema_name;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 删除租户 Schema 函数
-- ============================================================================
CREATE OR REPLACE FUNCTION drop_tenant_schema(p_tenant_id UUID)
RETURNS VOID AS $$
DECLARE
    v_schema_name TEXT;
BEGIN
    -- 获取 Schema 名称
    SELECT schema_name INTO v_schema_name
    FROM tenant_schema
    WHERE tenant_id = p_tenant_id;

    IF v_schema_name IS NOT NULL THEN
        -- 删除 Schema（级联删除所有对象）
        EXECUTE format('DROP SCHEMA IF EXISTS %I CASCADE', v_schema_name);

        -- 删除记录
        DELETE FROM tenant_schema WHERE tenant_id = p_tenant_id;

        RAISE NOTICE 'Tenant schema % dropped successfully', v_schema_name;
    END IF;
END;
$$ LANGUAGE plpgsql;
```

### 6.2 租户数据迁移

```sql
-- ============================================================================
-- 迁移现有数据到租户 Schema
-- ============================================================================
CREATE OR REPLACE FUNCTION migrate_tenant_data(p_tenant_id UUID)
RETURNS VOID AS $$
DECLARE
    v_schema_name TEXT;
    r RECORD;
BEGIN
    -- 获取 Schema 名称
    SELECT schema_name INTO v_schema_name
    FROM tenant_schema
    WHERE tenant_id = p_tenant_id;

    IF v_schema_name IS NULL THEN
        RAISE EXCEPTION 'Tenant schema not found for tenant %', p_tenant_id;
    END IF;

    -- 迁移战略规划
    EXECUTE format(
        'INSERT INTO %I.strategic_plan SELECT * FROM public.strategic_plan WHERE tenant_id = $1',
        v_schema_name
    ) USING p_tenant_id;

    -- 迁移 Agent
    EXECUTE format(
        'INSERT INTO %I.agent SELECT * FROM public.agent WHERE tenant_id = $1',
        v_schema_name
    ) USING p_tenant_id;

    -- 迁移工具
    EXECUTE format(
        'INSERT INTO %I.tool SELECT * FROM public.tool WHERE tenant_id = $1',
        v_schema_name
    ) USING p_tenant_id;

    RAISE NOTICE 'Data migration completed for tenant %', p_tenant_id;
END;
$$ LANGUAGE plpgsql;
```

### 6.3 租户查询视图

```sql
-- ============================================================================
-- 当前租户上下文视图（通过 SET LOCAL 切换）
-- ============================================================================
CREATE OR REPLACE VIEW current_tenant_strategic_plan AS
SELECT * FROM strategic_plan
WHERE tenant_id = current_setting('app.current_tenant_id')::UUID;

CREATE OR REPLACE VIEW current_tenant_checkpoint AS
SELECT * FROM checkpoint
WHERE plan_id IN (
    SELECT id FROM current_tenant_strategic_plan
);

-- 使用示例：
-- SET LOCAL app.current_tenant_id = '550e8400-e29b-41d4-a716-446655440000';
-- SELECT * FROM current_tenant_strategic_plan;
```

---

## 7. 数据迁移策略

### 7.1 迁移工具配置

```python
# 数据库迁移配置（Alembic）
[alembic]
script_location = migrations/
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = postgresql://sisys_app:${DB_PASSWORD}@postgres/sisys

[post_write_hooks]
hooks = black
black.type = console_scripts
black.entrypoint = black
black.options = -q
```

### 7.2 迁移脚本示例

```python
"""迁移脚本：创建初始 Schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-02-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建扩展
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    
    # 创建租户表
    op.create_table(
        'tenant',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(50), unique=True, nullable=False),
        sa.Column('tier', sa.String(20), nullable=False, default='basic'),
        # ... 其他字段
    )
    
    # 创建索引
    op.create_index('idx_tenant_slug', 'tenant', ['slug'])
    op.create_index('idx_tenant_status', 'tenant', ['status'])


def downgrade() -> None:
    op.drop_table('tenant')
```

### 7.3 数据归档策略

```sql
-- ============================================================================
-- 归档老数据（超过 1 年的完成规划）
-- ============================================================================
CREATE OR REPLACE FUNCTION archive_old_plans()
RETURNS INTEGER AS $$
DECLARE
    v_archived_count INTEGER;
BEGIN
    -- 创建归档表（如果不存在）
    CREATE TABLE IF NOT EXISTS strategic_plan_archive (
        LIKE strategic_plan INCLUDING ALL
    );

    -- 移动数据
    WITH moved AS (
        DELETE FROM strategic_plan
        WHERE status = 'archived'
          AND archived_at < NOW() - INTERVAL '1 year'
        RETURNING *
    )
    INSERT INTO strategic_plan_archive
    SELECT * FROM moved;

    GET DIAGNOSTICS v_archived_count = ROW_COUNT;

    -- 清理关联
    VACUUM ANALYZE strategic_plan;

    RETURN v_archived_count;
END;
$$ LANGUAGE plpgsql;

-- 定期执行（每月）
-- SELECT archive_old_plans();
```

---

## 附录 A：表结构完整清单

| 表名 | 用途 | 记录量级（年） | 分区策略 |
|------|------|--------------|---------|
| tenant | 租户信息 | <1000 | 无 |
| user | 用户信息 | <100,000 | 无 |
| role | 角色定义 | <10,000 | 无 |
| permission | 权限定义 | <1,000 | 无 |
| strategic_plan | 战略规划 | <100,000 | 按租户 Schema |
| checkpoint | 检查点 | <1,000,000 | 按租户 Schema |
| agent | Agent 信息 | <100,000 | 按租户 Schema |
| tool | 工具定义 | <100,000 | 按租户 Schema |
| tool_execution_log | 工具执行日志 | <10,000,000 | 按月分区 |
| routing_decision_log | 路由决策日志 | <10,000,000 | 按月分区 |
| saga_audit_log | Saga 审计日志 | <10,000,000 | 按月分区 |
| event_outbox | 事件发件箱 | <1,000,000 | 定期归档 |

---

## 附录 B：参考文档

- [PostgreSQL 官方文档](https://www.postgresql.org/docs/)
- [Alembic 迁移工具](https://alembic.sqlalchemy.org/)
- [多租户数据库设计模式](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/implement-multi-tenancy-in-your-application-using-database-isolation.html)

---

**文档版本：** 1.0.0
**最后更新：** 2026-02-25
**审核状态：** 已批准
**下一步：** 实施数据库迁移脚本开发
