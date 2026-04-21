# Deferred Work

## Deferred from: code review of 1-10-unified-audit-log.md (2026-04-20)

- **W1: Archive 不强制 7 年保留** — MVP 限制，MinIO WORM V2 才实现
- **W2: 缺少 CLI 命令** — Spec 要求但未实现，属于后续 Story
- **W3: 事件监听器映射非 spec 事件类型** — 实现的类型与 spec 列出略有差异
- **W4: 合规分析不验证完整覆盖** — MVP 限制，完整验证 V2 实现
- **W5: Outbox 状态转换过于宽松** — RLS 策略设计决策

## Deferred from: code review of 20-1-sisys-testing-refactor.md (2026-04-21)

- **fresh_test_env_config fixture 命名与行为不符** — fixture 名称暗示"新的/干净的"配置，但实现只是返回全局共享配置对象，非阻塞性问题
- **CI 环境变量缺少认证信息** — 仅暴露 host/port，未包含认证凭据，可能是 CI 环境使用默认无认证配置
- **TestTenant.id 使用 default_factory 但 __post_init__ 依赖它** — 初始化顺序可能造成混淆，但功能上正确，属于可读性问题
