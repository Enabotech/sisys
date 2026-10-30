# language: zh-CN
功能: Story 5.11 SAP 协议支持（内部 Agent 通信）
  作为系统架构师
  我希望系统实现 SAP 协议运行时——消息总线（五种消息类型分发 + 四级优先级出队 + 请求-响应 correlation 关联）+ JSON 序列化契约 + 公共黑板交互
  以便多 Agent 协作可通过统一协议进行辩论、裁决与公共黑板交互（协议基础设施就绪——协作场景编排在 Epic 9 接线）

  # 说明: 真实 Redis 依赖场景（AC-3.1/AC-3.2）采用步骤化门控（场景内 ping 探测 +
  # pytest.skip 动态跳过——禁全 feature 背景块，5-5 Redis 步骤化门控先例）；
  # 其余 12 场景为进程内替身/委托计时面，零外部服务依赖。

  # === AC-1: SAPBus 端口与进程内总线核心 ===

  场景: AC-1.1 - 四种单播类型逐一送达与 BROADCAST 全员送达
    假如 手工构造 InProcessSAPBus 实例（注入替身黑板与放行守卫）
    并且 三个接收方以 UUID 标识订阅消息
    当 依次发送 REQUEST RESPONSE NOTIFICATION DEBATE 四种单播消息
    并且 三个接收方场景下发送 BROADCAST 消息
    那么 每种类型消息 15 字段与发送实例全等且 epics 十键逐键一致
    并且 BROADCAST 全员送达同一 message_id

  场景: AC-1.2 - 四级优先级乱序插队与同级 FIFO 出队
    假如 手工构造 InProcessSAPBus 实例（注入替身黑板与放行守卫）
    并且 单接收方订阅消息并记录出队顺序
    当 乱序注入六级消息（LOW NORMAL HIGH URGENT 各一加两条 NORMAL）
    那么 出队顺序为 URGENT HIGH NORMAL×3（入队序）LOW

  场景: AC-1.3 - 协议校验面 fail-loud 与关闭态 461
    假如 手工构造 InProcessSAPBus 实例（注入替身黑板与放行守卫）
    并且 一个接收方以 UUID 标识订阅消息
    当 进行未注册接收方与非 UUID 双侧及组合双向校验违规操作
    并且 发送 requires_response 的 REQUEST 并后台挂起等待者
    并且 关闭总线后二次关闭并调用 send subscribe wait_for_response
    那么 四类校验违规各抛 461 且 reason 逐项匹配闭集
    并且 挂起等待者收到 461 总线关闭异常
    并且 二次关闭幂等零异常
    并且 关闭态三方法均抛 461 且 reason 为 bus_closed

  # === AC-2: 请求-响应关联 ===

  场景: AC-2.1 - REQUEST 等待与 RESPONSE correlation 关联送达
    假如 请求方与响应方两方装配（响应方回发指向请求的 RESPONSE）
    当 请求方发送 requires_response 的 REQUEST 并等待其 message_id 锚
    那么 wait_for_response 返回消息的 correlation_id 与请求 message_id 相等
    并且 请求方 handler 同时收到该 RESPONSE（双动作送达）

  场景: AC-2.2 - 超时 460 与索引清理及迟到双响应防御
    假如 请求方与静默响应方装配（订阅自身且无人回发）
    当 发送 REQUEST 后无人回发并以 0.1 秒短超时等待
    那么 抛出 460 且 context 携带 correlation_id 与 timeout_seconds
    并且 超时后索引零残留（迟到 RESPONSE 零崩溃零 resolve）
    并且 正常双响应幂等（第二条 RESPONSE 零 InvalidStateError）

  场景: AC-2.3 - 默认无等待语义与并发请求键控隔离
    假如 两对请求响应装配（响应方各自回发）
    当 发送 requires_response 为 False 的 NOTIFICATION
    那么 消息直达 handler 且未挂起 correlation 的等待按超时路径抛 460
    并且 两对并发请求各自关联 resolve 互不干扰

  # === AC-3: 公共黑板交互 ===

  场景: AC-3.1 - 公共黑板 MVCC 写入（真实 Redis）
    假如 真实 Redis 可用且装配真实 RedisPublicBlackboard 与放行守卫
    当 发送两条 blackboard_visible 为真的消息
    那么 get 读回版本号恰为 v1 与 v1+1 两级递增
    并且 读回 content 的 message_id 与发送消息一致
    并且 teardown 后黑板键与版本键均不存在

  场景: AC-3.2 - L4 真实隔离链写黑板 449 透传
    假如 真实 Redis 可用且真实实例化 L4 CEO Agent 并装配真实隔离链
    当 L4 Agent 发送 blackboard_visible 为真的消息
    那么 抛出 449 且 context 的 reason 为 data_isolation:read_only
    并且 真实黑板 get 读回为空（零写入）

  场景: AC-3.3 - 零写入边界与写失败 fail-loud 462
    假如 手工构造 InProcessSAPBus 实例（注入替身黑板与放行守卫）
    并且 两个接收方以 UUID 标识订阅消息
    当 发送 blackboard_visible 为假的 NOTIFICATION 与 BROADCAST 消息
    并且 发送 blackboard_visible 为真的 NOTIFICATION 消息
    并且 发送 blackboard_visible 为真的 BROADCAST 消息
    并且 替身守卫拒绝后发送可见消息
    并且 替换黑板为 post 返 0 的失败替身后发送可见消息
    那么 替身黑板零 post 调用（可见性开关是唯一闸门）
    并且 post 四键投影与守卫四参数锚正确
    并且 BROADCAST 可见消息 post 计数恰为 1 且全员送达
    并且 449 原样透传且消息不投递
    并且 抛出 462 且消息不投递

  # === AC-4: 序列化契约与端口接线 ===

  场景: AC-4.1 - JSON 序列化往返保真
    假如 构造 15 字段全显式赋值的 SAPMessage 实例
    当 serialize 后 deserialize 往返
    那么 往返实例与原实例逐字段相等
    并且 坏 JSON 反序列化抛 pydantic ValidationError 原样透传

  场景: AC-4.2 - 组合根 sap_bus 端口注册与注入链
    假如 组合根 bootstrap 完成
    当 resolve 解析 sap_bus 端口
    那么 返回 InProcessSAPBus 实例且 PortSpec 元数据四项正确
    并且 实例的黑板与守卫依赖注入链非空
    并且 依赖缺失时抛 ConfigurationError（fail-fast 非降级）

  # === AC-5: 性能三锚 ===

  场景: AC-5.1 - 消息传递与序列化 P95 双锚（委托计时）
    假如 集成计时委托模块已加载（_PERF_CACHE 委托采样）
    当 读取委托采样的传递与序列化 P95 摘要
    那么 传递 P95 小于 200ms（常量单源 SAP_DELIVERY_P95_LIMIT_SECONDS 等值断言）
    并且 序列化 P95 小于 50ms（常量单源 SAP_SERIALIZATION_P95_LIMIT_SECONDS 等值断言）
    并且 正向锚收到计数为 21

  场景: AC-5.2 - 50 并发消息全送达与队列清空
    假如 手工构造 InProcessSAPBus 实例（注入替身黑板与放行守卫）
    并且 单接收方订阅消息并记录出队顺序
    当 一次性并发发送 50 条消息
    那么 50 条全部送达零丢失
    并且 接收方处理完成后队列清空（积压归零）

  # === 收尾: 开发结束验收 ===

  场景: 开发结束 - 交付完成清单逐项确认
    假如 Story 5.11 交付完成
    那么 src 完成清单七件全部就位且关键符号可导入
    并且 tests 完成清单全部就位
    并且 组合根注册与导出及文档联动全部就位
