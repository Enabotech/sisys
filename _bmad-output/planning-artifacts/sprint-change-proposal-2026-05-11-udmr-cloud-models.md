# Sprint Change Proposal: UDMR 云端大模型配置支持

**日期:** 2026-05-11
**状态:** ✅ Implemented
**触发原因:** Story 1.17 UDMR 基础路由审查后功能增强需求

---

## 1. Issue Summary

### 1.1 问题陈述

Story 1.17 UDMR 基础路由当前实现中：

1. **云端模型仅支持名称列表** - `cloud_models: list[str]`，无 API 配置
2. **云端模型硬编码** - `["qwen-turbo", "qwen-plus", "claude-3-haiku"]`
3. **无多云端支持** - 无法配置多个不同 API 提供商

业务需求：
- 支持 GLM-5.1、MiniMax-M2.7、DeepSeek 等国产大模型
- 支持 OpenAI/Anthropic 兼容的 API 格式
- 支持配置 API endpoint、API key、模型名称

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | 影响 | 说明 |
|------|------|------|
| Epic 1 | 无 | Story 1.17 范围内增强 |
| Epic 11 (UDMR 动态模型路由) | 加速 | 云端模型配置是 L2/L3 的前置依赖 |

### 2.2 Story Impact

| Story | 影响 | 说明 |
|-------|------|------|
| 1-17 UDMR 基础路由 | **扩展** | 新增云端配置支持 |
| 11-1 UDMR 三层决策 | 加速 | L1/L2/L3 依赖云端配置 |

### 2.3 Artifact Impact

| Artifact | 需要更新 |
|----------|---------|
| `1-17-udmr-basic-routing.md` | ✅ SDD 规范 + AC |
| `architecture.md` | ✅ UDMR 配置章节 |
| 代码实现 | ✅ UDMRConfig 扩展 |

### 2.4 Technical Impact

- `UDMRConfig` 新增云端模型配置字段
- 支持多云端配置（UDMR_CLOUD_0_, UDMR_CLOUD_1_, ...）
- 支持 API 类型（openai, anthropic, custom）

---

## 3. Recommended Approach

**类型:** Minor - 现有 Story 范围内功能增强

**方案:** 在 Story 1.17 中新增 Task 4（云端模型配置支持）

---

## 4. Detailed Change Proposals

### 4.1 Story 1.17 变更

**Section: SDD 规范定义（Task 0）**

#### 新增配置模型 Schema

```yaml
#### 配置模型扩展 (Configuration Models)
- [ ] UDMRConfig 云端模型配置扩展（`src/infrastructure/config/udmr.py`）
  - 环境变量:
    - UDMR_CLOUD_0_API_TYPE: openai | anthropic | custom  # API 类型
    - UDMR_CLOUD_0_ENDPOINT: https://api.minimax.chat/v1  # API 端点
    - UDMR_CLOUD_0_API_KEY: xxx  # API 密钥
    - UDMR_CLOUD_0_MODEL: MiniMax-M2.7  # 模型名称
    - UDMR_CLOUD_0_ENABLED: true | false  # 启用状态
  - 支持多云端配置（UDMR_CLOUD_0_, UDMR_CLOUD_1_, UDMR_CLOUD_2_, ...）
  - 向后兼容: UDMR_CLOUD_MODELS 仍支持，仅配置模型名称
```

#### 新增验收标准

```yaml
### AC-5: 云端模型配置支持

**Given** 系统配置了云端模型 API
**When** UDMRouter 执行路由决策
**Then** 支持路由至配置的云端模型
**And** 记录云端模型类型和 endpoint

**验证标准:**
- [ ] 云端模型 API 类型配置（openai | anthropic | custom）
- [ ] 云端模型 Endpoint 配置
- [ ] 云端模型 API Key 配置（安全存储）
- [ ] 多云端配置支持（至少 3 个）
- [ ] 向后兼容: 原有 UDMR_CLOUD_MODELS 环境变量仍有效
```

### 4.2 Architecture 变更

**Section: 4. 统一动态模型路由框架 UDMR**

在 4.x 节新增云端配置说明：

```markdown
### 4.X 云端模型配置

UDMR 支持多云端模型配置，每种配置包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| api_type | openai \| anthropic \| custom | API 格式类型 |
| endpoint | string | API 端点 URL |
| api_key | string | API 密钥（环境变量引用） |
| model | string | 模型名称 |
| enabled | bool | 是否启用 |

环境变量示例：
```bash
# 云端模型 0 - MiniMax
UDMR_CLOUD_0_API_TYPE=custom
UDMR_CLOUD_0_ENDPOINT=https://api.minimax.chat/v1
UDMR_CLOUD_0_API_KEY=${MINIMAX_API_KEY}
UDMR_CLOUD_0_MODEL=MiniMax-M2.7
UDMR_CLOUD_0_ENABLED=true

# 云端模型 1 - DeepSeek
UDMR_CLOUD_1_API_TYPE=openai
UDMR_CLOUD_1_ENDPOINT=https://api.deepseek.com/v1
UDMR_CLOUD_1_API_KEY=${DEEPSEEK_API_KEY}
UDMR_CLOUD_1_MODEL=deepseek-chat
UDMR_CLOUD_1_ENABLED=true

# 云端模型 2 - GLM
UDMR_CLOUD_2_API_TYPE=custom
UDMR_CLOUD_2_ENDPOINT=https://open.bigmodel.cn/api/paas/v4
UDMR_CLOUD_2_API_KEY=${ZHIPU_API_KEY}
UDMR_CLOUD_2_MODEL=glm-5.1
UDMR_CLOUD_2_ENABLED=true
```
```

### 4.3 代码实现提案

#### UDMRConfig 扩展

```python
@dataclass(frozen=True)
class CloudModelConfig:
    """单云端模型配置."""
    api_type: str = "openai"  # openai | anthropic | custom
    endpoint: str = ""
    api_key: str = ""
    model: str = ""
    enabled: bool = True

@dataclass(frozen=True)
class UDMRConfig:
    # ... 现有字段 ...

    # 云端模型配置（新增）
    cloud_configs: list[CloudModelConfig] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> UDMRConfig:
        # ... 解析 UDMR_CLOUD_0_API_TYPE, UDMR_CLOUD_0_ENDPOINT, ...
        cloud_configs = []
        for i in range(10):  # 支持 0-9
            c_type = os.getenv(f"UDMR_CLOUD_{i}_API_TYPE")
            if c_type is None:
                break
            cloud_configs.append(CloudModelConfig(
                api_type=c_type,
                endpoint=os.getenv(f"UDMR_CLOUD_{i}_ENDPOINT", ""),
                api_key=os.getenv(f"UDMR_CLOUD_{i}_API_KEY", ""),
                model=os.getenv(f"UDMR_CLOUD_{i}_MODEL", ""),
                enabled=os.getenv(f"UDMR_CLOUD_{i}_ENABLED", "true").lower() in ("true", "1"),
            ))
        return cls(cloud_configs=cloud_configs, ...)
```

---

## 5. Implementation Handoff

**Scope:** Minor - 可由 Developer agent 直接实现

**任务分解:**

| Task | 内容 | 预估 | 状态 |
|------|------|------|------|
| Task 4.1 | TDD 红 - 编写 CloudModelConfig 测试 | 1h | ✅ |
| Task 4.2 | 绿 - 实现 CloudModelConfig | 1h | ✅ |
| Task 4.3 | TDD 红 - 编写云端配置解析测试 | 1h | ✅ |
| Task 4.4 | 绿 - 实现 from_env 云端配置解析 | 2h | ✅ |
| Task 4.5 | 重构 - mypy + pytest + ruff | 1h | ✅ |

**总计:** ~6h → 实际实现 ~2h

**成功标准:**
- ✅ CloudModelConfig frozen dataclass 实现
- ✅ from_env 支持解析 UDMR_CLOUD_* 环境变量
- ✅ 向后兼容: UDMR_CLOUD_MODELS 仍有效
- ✅ mypy + pytest + ruff 全部通过

---

## 6. Backward Compatibility

**UDMR_CLOUD_MODELS 环境变量:**

```python
# 如果 UDMR_CLOUD_0_API_TYPE 等未配置，但 UDMR_CLOUD_MODELS 配置了
# 自动创建兼容配置的 CloudModelConfig
if not cloud_configs and cloud_models:
    for model in cloud_models:
        cloud_configs.append(CloudModelConfig(
            api_type="openai",  # 默认 OpenAI 兼容格式
            endpoint="",     # 使用默认 endpoint
            api_key="",
            model=model,
            enabled=True,
        ))
```

---

## 7. Alternatives Considered

### 方案 A: 仅支持环境变量（当前提案）
- ✅ 简单，符合现有模式
- ✅ 向后兼容
- ❌ 不支持运行时配置

### 方案 B: 支持数据库配置
- ✅ 支持运行时更改
- ❌ 复杂度高，引入存储依赖
- ❌ 超出 Story 1.17 范围

### 方案 C: 支持配置文件（YAML/JSON）
- ✅ 集中管理
- ❌ 引入新配置文件类型
- ❌ 与现有 from_env 模式不一致
