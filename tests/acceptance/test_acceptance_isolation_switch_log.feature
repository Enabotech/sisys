# language: zh-CN
功能: 隔离切换日志记录（Story 5.6 — FR-AC-06 审计留痕面）

  作为合规工程师
  我想要系统记录隔离切换日志（AGENT ID、时间戳、原隔离等级、目标隔离等级、触发原因、审批链）并支持多维检索
  以便满足审计追踪要求（FR-AC-06——每次隔离等级变更留有不可篡改的完整审计痕迹）

  # =========================================================================
  # AC-1: IsolationSwitchLog 领域实体与事件映射（端口级——无服务依赖，脱离门控）
  # =========================================================================

  场景: AC-1.1 - from_event 六字段映射与审计字段完整
    假如 已构造真实切换事件 IsolationLevelSwitched（六字段 payload）
    当 调用 IsolationSwitchLog.from_event 映射日志实体
    那么 六字段逐项映射完整（agent_id/switch_timestamp/previous_level/target_level/trigger_reason/approval_chain）
    并且 switch_timestamp 取事件 switch_timestamp（单钟纪律）
    并且 approval_chain 为不可变 tuple 形态（list 冻结拷贝）
    并且 log_id 为自铸 UUID4
    并且 worm_ref 默认 None（OD-1 预留）

  场景: AC-1.2 - 实体不变量与不可变形态
    假如 实体构造通道已就绪
    当 分别注入五类非法输入构造日志实体
    那么 每类输入抛 EntityValidationError 242 且 context 携带字段名
    并且 to_dict 全字段可序列化（UUID→str/Enum→value/datetime→ISO 8601/tuple→list）
    并且 frozen 赋值被拒绝（日志不可变性）

  # =========================================================================
  # AC-2: 切换链 audit-first 日志写入（服务级——AC-2.3 Redis 单门控，余者 Redis+PG）
  # =========================================================================

  场景: AC-2.1 - 切换成功六字段落库
    假如 Redis 缓存服务可用
    并且 PostgreSQL 服务可用
    并且 真实 Agent 已实例化（默认 L4）
    并且 真实切换链已手动组装（含 PG 日志仓储）
    当 请求切换隔离等级到 "L3" 原因 "审计留痕验证" 审批链 "合规负责人"
    那么 切换结果 switched 为 True
    并且 PG 检索取回日志六字段逐项一致（含 approval_chain JSONB roundtrip）

  场景: AC-2.2 - no-op 零日志新增
    假如 Redis 缓存服务可用
    并且 PostgreSQL 服务可用
    并且 真实 Agent 已实例化并已切换到 "L3"
    当 再次请求切换隔离等级到 "L3" 原因 "重复请求"
    那么 切换结果 switched 为 False
    并且 检索该 Agent 日志 total 保持不变

  场景: AC-2.3 - audit-first 拒绝路径（日志写失败切换被拒）
    假如 Redis 缓存服务可用
    并且 真实 Agent 已实例化（默认 L4）
    并且 切换链已注入坏连接日志仓储（不可达端点 127.0.0.1:1，不设请求 session）
    当 请求切换隔离等级到 "L3" 原因 "故障注入"
    那么 抛出 StorageError 103
    并且 Redis 隔离等级未变（仍为 L4）
    并且 零事件发布

  场景: AC-2.4 - audit 联动记录
    假如 Redis 缓存服务可用
    并且 PostgreSQL 服务可用
    并且 真实 Agent 已实例化（默认 L4）
    并且 真实切换链已手动组装（含真实 audit_service）
    当 请求切换隔离等级到 "L3" 原因 "联动审计验证"
    那么 audit_log 表含 isolation:switch 记录一条且 correlation_id 匹配事件
    并且 old_value 与 new_value 形态正确（level 为 .value 字符串）

  # =========================================================================
  # AC-3: 多维检索（服务级——真实 PG 门控）
  # =========================================================================

  场景: AC-3.1 - 按 AGENT 检索
    假如 PostgreSQL 服务可用
    并且 多 Agent 切换日志已造数（3 Agent × 2 条，覆盖 L4→L3 与 L4→L2）
    当 以 agent_id 维度检索切换日志
    那么 仅返回该 Agent 的日志且 total 等于该 Agent 条数
    并且 检索不要求 Agent 现存（无 443 守卫）

  场景: AC-3.2 - 时间范围与隔离等级组合检索（level 双向命中）
    假如 PostgreSQL 服务可用
    并且 多 Agent 切换日志已造数（3 Agent × 2 条，覆盖 L4→L3 与 L4→L2）
    当 以时间范围与隔离等级 "L3" 组合检索
    那么 命中日志满足 previous_level 或 target_level 任一为 L3
    并且 L4→L3 切换在 level "L4" 检索亦返回（previous 命中）
    并且 组合条件为 AND 语义

  场景: AC-3.3 - 分页与排序
    假如 PostgreSQL 服务可用
    并且 单 Agent 五条切换日志已造数（独立分页造数）
    当 以 limit 2 offset 0 检索
    那么 返回 2 条且 total 为 5
    当 以 offset 4 检索
    那么 返回 1 条
    当 以 offset 5 检索（空页边界）
    那么 返回 0 条且 total 为 5
    并且 排序为 switch_timestamp 降序（最新在前）

  # =========================================================================
  # AC-4: 持久化与不可篡改（服务级——真实 PG 门控）
  # =========================================================================

  场景: AC-4.1 - RLS 篡改拒绝
    假如 PostgreSQL 服务可用
    并且 真实切换日志已落库一条
    并且 数据库连接角色为非绕过（rolsuper/rolbypassrls/owner 任一即跳过）
    当 尝试 UPDATE 修改日志行 target_level
    那么 影响 0 行（deny UPDATE）
    当 尝试 DELETE 删除日志行
    那么 影响 0 行（deny DELETE）

  场景: AC-4.2 - worm_ref 预留与表结构与 CheckConstraint 拒绝
    假如 PostgreSQL 服务可用
    并且 真实切换日志已落库一条
    当 检查 ORM 模型与表结构
    那么 列集完整（含 worm_ref nullable 与 created_at server_default）
    并且 索引五项齐备（agent_id/switch_timestamp/previous_level/target_level/组合索引）
    并且 worm_ref 检索 roundtrip 保持 None
    当 直插 previous_level 等于 target_level 行
    那么 抛出 IntegrityError（CheckConstraint 拒绝 no-op 日志）

  # =========================================================================
  # AC-5: 性能与存储成功率（委托集成计时——Redis+PG 双门控）
  # =========================================================================

  场景: AC-5.1 - 日志记录延迟 P95 小于 50ms
    假如 Redis 缓存服务可用
    并且 PostgreSQL 服务可用
    当 执行切换全链计时采样（委托集成缓存——禁 20 采样双跑）
    那么 P95 延迟小于 50ms

  场景: AC-5.2 - 检索响应 P95 小于 500ms 与存储成功率 100%
    假如 Redis 缓存服务可用
    并且 PostgreSQL 服务可用
    当 执行检索计时采样（委托集成缓存）与连续 20 次真实切换
    那么 检索 P95 延迟小于 500ms
    并且 20 次切换产生 20 条日志（20/20 分子分母）

  # =========================================================================
  # AC-6: 端口接线、CLI、架构合规与回归（端口级 + 服务级 + 静态）
  # =========================================================================

  场景: AC-6.1 - 组合根接线与端口注册
    假如 组合根已引导装配
    那么 isolation_switch_log_repository 端口 resolve 可达且 PortSpec 元数据完整（SINGLETON）
    并且 isolation_management_service 实例第五依赖为日志仓储端口实例（接线内省——禁发真实命令）
    并且 第六依赖 audit_service 可选注入可达

  场景: AC-6.2 - CLI isolation-logs 真实链检索
    假如 PostgreSQL 服务可用
    并且 切换日志已直构落库一条（fallback 独立会话 commit——生产 CLI 真实形态）
    当 进程内执行 isolation-logs 命令（CLI fallback 全链）
    那么 退出码为 0 且 stdout 含等级与原因行
    并且 造数行清理零残留（superuser 连接 DELETE——非绕过环境跳过）

  场景: AC-6.3 - 架构合规静态扫描
    当 扫描 domain 实体与端口文件 import
    那么 零外部依赖（仅标准库与同层 import）
    当 扫描组合根外 PostgreSQLIsolationSwitchLogRepository 实例化点
    那么 仅组合根与测试文件出现
    并且 CLI import 白名单合规（domain/application 合法，infrastructure 禁入）

  场景: AC-6.4 - 回归面资产在位
    那么 5-4 与 5-5 验收及探针测试文件存在
    并且 AuditActionType.ISOLATION_SWITCH 枚举项已注册（值 isolation:switch）
    并且 IsolationLevelSwitched 事件双登记不漂移（yaml 与 DEFAULT_MAPPINGS）

  # =========================================================================
  # 收尾: 交付完成清单（Task 6 追加——18 场景终态）
  # =========================================================================

  场景: 收尾 - 交付完成清单
    那么 src 交付八文件全部在位（实体/端口/模型/迁移/仓储/服务/CLI/组合根）
    并且 tests 四目录交付文件全部在位（unit/contracts/integration/acceptance）
