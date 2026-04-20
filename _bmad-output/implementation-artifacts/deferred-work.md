# Deferred Work

## Deferred from: code review of 1-10-unified-audit-log.md (2026-04-20)

- **W1: Archive 不强制 7 年保留** — MVP 限制，MinIO WORM V2 才实现
- **W2: 缺少 CLI 命令** — Spec 要求但未实现，属于后续 Story
- **W3: 事件监听器映射非 spec 事件类型** — 实现的类型与 spec 列出略有差异
- **W4: 合规分析不验证完整覆盖** — MVP 限制，完整验证 V2 实现
- **W5: Outbox 状态转换过于宽松** — RLS 策略设计决策
