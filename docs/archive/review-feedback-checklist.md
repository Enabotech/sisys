"""代码审查反馈检查清单

从 Epic 1（23 个 Story、1353+ 测试）的代码审查中提取的常见陷阱检查清单。
每个 Story 开发前逐项检查，减少审查迭代轮次。

典型痛点：Epic 1 中高迭代 Story（1.17 十轮、1.18a 十轮、1.3 多轮）的根因分析表明，
超过 60% 的审查问题属于六大重复模式。本清单将这些模式固化为可操作检查项。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

# 代码审查反馈检查清单

**版本:** 1.0.0
**日期:** 2026-05-25
**用途:** 每个 Story 开发前/代码审查时的自检清单

---

## 1. 边界防护（最高频，5+ Story 反复出现）

边界防护是 Epic 1 审查中最高频的问题类型。开发时容易只关注"正常路径"而忽略状态极端值、
重复调用、集合篡改等边界场景。审查者反复发现：advance_phase 无最终相位防护、
from_dict 错误信息缺少上下文导致调试困难、completed_phases 重复累积等问题。

- [ ] 状态转换有无最终相位防护？（如 `advance_phase` 不能超过最后一个阶段）
- [ ] `complete_phase` 是否检查当前状态？（已归档/已审批的规划不可再推进）
- [ ] 参数校验失败时错误信息是否包含上下文？（如 `from_dict` 失败时输出具体字段名和实际值）
- [ ] `fail`/`reject` 方法是否会被重复调用覆盖原因？（需幂等或追加而非覆盖）
- [ ] 列表/集合是否可被外部篡改？（返回副本或冻结视图，`completed_phases` 需防重复累积）
- [ ] 枚举/状态转换是否只允许合法邻接？（禁止跳过中间阶段）
- [ ] 空值/零值/负值是否在入口处拦截？（构造器 `__post_init__` 校验）

## 2. Optional 字段一致性

Epic 1 中 Story 间数据模型传递时，nullable 与 Optional 标注不一致、datetime 时区混用、
frozen dataclass 缺少默认值等问题频繁出现。根因：上游 Story 定义的字段约束未同步到下游。

- [ ] `nullable=True` 是否与上游 Story 的 `Optional` 标注匹配？（数据库列定义 vs Python 类型标注）
- [ ] datetime 时区是否统一使用 aware？（统一 `TIMESTAMP WITH TIME ZONE`，禁止 naive datetime）
- [ ] frozen dataclass 扩展字段是否都有默认值？（新增字段必须提供 `default` 或 `default_factory`）
- [ ] JSON 序列化/反序列化时 Optional 字段缺失是否正确处理？（`None` vs 字段不存在）

## 3. 锁策略

Epic 1 中 Story 1.3（事件总线）在 InMemoryOutboxRepository 中误用 `threading.Lock`，
导致审查多轮反复修正。async 上下文使用 `threading.Lock` 会阻塞事件循环，是必须杜绝的硬伤。
同时 `asyncio.Lock` 声明位置（类变量 vs 实例变量）也影响协程间共享。

- [ ] async 上下文是否严格使用 `asyncio.Lock`？（`threading.Lock` 会阻塞事件循环）
- [ ] `asyncio.Lock` 是否声明为类变量而非实例变量？（实例变量在协程间不共享）
- [ ] 同步上下文（如文件 I/O）才使用 `threading.Lock`，且与 `asyncio.Lock` 分离
- [ ] 锁的粒度是否合理？（单锁保护所有操作 vs 细粒度锁，需在注释中说明选择理由）

## 4. Config 注入

Story 1.17/1.18a 审查中发现领域服务直接接受 Config 对象，违反了 domain 层零外部依赖原则。
正确做法：领域服务接受原始值（str/int/float），Config 对象仅在 infrastructure/application 层
通过 `Config.from_env()` 创建并解构后注入。

- [ ] 领域服务是否接受原始值而非 Config 对象？（domain 层禁止依赖 Config 类）
- [ ] Config 对象是否通过 `Config.from_env()` 在调用端创建？（不在领域服务内调用）
- [ ] DI 注册是否使用 `lambda resolver:` 格式？（在 lambda 内创建 Config 并解构为原始值）
- [ ] Config 字段命名是否与领域服务参数名一致？（避免隐式映射导致的混淆）

## 5. DI 注册

Epic 1 中多次出现端口注册不完整（缺 registry entry 或 composition_root 注册）、
Config 对象被误注册为 port（应为 lambda factory 创建）、contract test 遗漏等问题。
这些遗漏导致运行时 ResolutionError 或测试覆盖盲区。

- [ ] Port 注册是否三件套完整？registry entry + `composition_root.py` 注册 + contract test
- [ ] Config 对象是否未作为 port 注册？（通过 `lambda resolver:` factory 创建，不走 DI 容器）
- [ ] `composition_root.py` 中 impl 字符串路径是否正确？（延迟加载路径错误不会立即报错）
- [ ] Port 生命周期是否正确标注？（SINGLETON / SCOPED / TRANSIENT 需与业务语义匹配）
- [ ] 新增 Port 后 `PortSpec` 元数据是否完整？（name / version / interface / impl / lifetime / tags）

## 6. 事件发布

Story 1.18a（Prefect 集成）审查中暴露：`PublishResult.is_full_failure` 未检查、
事件发布失败时错误地回写业务状态为 FAILED、事件类型注册表依赖 `__subclasses__()`
不可靠（仅发现已加载的子类）等问题。

- [ ] 事件发布后是否检查 `PublishResult.is_full_failure`？（记录警告日志，不静默忽略）
- [ ] 事件发布失败是否独立于业务状态？（不因发布失败回写业务状态为 FAILED）
- [ ] 事件类型注册表是否显式导入所有事件类？（`__subclasses__()` 不可靠，需模块顶层显式 import）
- [ ] 新事件是否同时更新 `config/event_channels.yaml` 和 `ChannelRouter.DEFAULT_MAPPINGS`？
- [ ] 事件发布顺序是否正确？（业务状态变更后发布事件，而非之前）

---

## 附录：Epic 1 典型案例引用

以下案例来自 Epic 1 实际审查反馈，供对照参考：

1. **Story 1.3 — 事件总线竞态与锁策略**
   `InMemoryOutboxRepository` 初版使用 `threading.Lock`，在 async 上下文中阻塞事件循环。
   审查后统一改为 `asyncio.Lock()` 类变量声明，审查轮次 5+ 轮。同时 `__subclasses__()`
   导致事件类型发现不可靠，改为模块顶层显式导入所有事件类。

2. **Story 1.17 — UDMR 路由循环防护缺失**
   `advance_phase` 无最终相位防护，`RoutingDecided` 事件 causation_id 未排除自身导致
   事件循环。审查迭代 10 轮，修复包括：最终相位校验、循环防护显式排除 RoutingDecided、
   DI 注册全部改为 `lambda resolver:` 格式。

3. **Story 1.18a — PrefectConfig 误注册为 Port**
   `PrefectConfig` 作为 port 注册到 DI 容器，违反 Config 对象不作为 port 的原则。
   审查迭代 10 轮（8 个 P0 问题），修正为 `lambda resolver:` 内 `Config.from_env()` 创建。
   同时 `PublishResult.is_full_failure` 未检查，补充分发失败日志告警。

4. **Story 1.14a-b — completed_phases 重复累积**
   `StrategicPlan.completed_phases` 列表在多次调用 `complete_phase` 时重复追加相同阶段，
   且列表引用暴露允许外部直接篡改。修复：添加 `if phase not in completed_phases` 去重检查。

5. **Story 1.9 — AuthService 接口位置错误**
   `AuthService` 接口最初放在 `services/` 目录而非 `ports/`，违反六边形架构端口定义规范。
   审查后状态完全重置到 `ports/` 位置，import-linter 约束全程保持通过。
