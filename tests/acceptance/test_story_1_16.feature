# language: zh-CN
# Story 1.16: 集成测试框架 — Gherkin 验收测试

功能: 集成测试框架基础设施与冒烟测试
  作为系统架构师与 QA 工程师
  我想要建立集成测试框架并验证已实现组件协作
  以确保六边形架构各层间协作正确性

  场景大纲: 集成测试目录结构就绪
    假如单元测试框架 pytest 已配置完成
    当创建集成测试目录结构 tests/integration/
    那么集成测试可独立运行
    并且支持外部服务 Mock
    并且测试隔离机制完善

    例子:
      | 目录                        |
      | tests/integration            |
      | tests/integration/fixtures   |
      | tests/acceptance             |

  场景大纲: 外部服务 Mock 配置
    假如需要 Mock 外部服务
    当配置 Mock fixtures
    那么 Redis 使用 fakeredis 行为级 Mock
    并且 PostgreSQL/RabbitMQ 使用 AsyncMock 接口级 Mock

    例子:
      | 服务        | Mock 类型    |
      | Redis       | 行为级       |
      | PostgreSQL  | 接口级       |
      | RabbitMQ    | 接口级       |

  场景大纲: 领域事件冒烟测试
    假如领域事件定义和内存发件箱已实现
    当通过 InMemoryOutboxRepository 发布事件 <event_type>
    那么事件被正确序列化并写入内存发件箱
    并且可通过 get_unpublished 查询到未发布事件
    并且可通过 mark_published 标记事件已发布

    例子:
      | event_type              |
      | DocumentProcessed       |
      | ToolExecuted            |
      | AgentDecided            |

  场景: 事件类型注册表 — 未知类型反序列化
    假如事件类型注册表已知 DocumentProcessed
    当反序列化未知 event_type "UnknownEventType"
    那么应抛出 ValueError

  场景: 幂等性检查原子操作
    假如 IdempotencyChecker 使用 fakeredis
    当对同一 event_id 调用 try_acquire 两次
    那么第一次返回 True
    并且第二次返回 False

  场景: 重试机制指数退避
    假如 RetryPolicy base_delay=1.0, max_delay=60.0
    当调用 get_delay(0) 和 get_delay(2)
    那么 get_delay(2) > get_delay(0)
    并且延迟包含 jitter 随机性

  场景大纲: 仓储模式冒烟测试
    假如领域层定义了仓储接口
    当通过 InMemoryOutboxRepository 保存事件
    那么领域事件可通过仓储接口保存至内存存储
    并且领域层不直接依赖具体存储实现

    例子:
      | 操作            |
      | save            |
      | get_unpublished |
      | mark_published  |

  场景: 测试数据生命周期管理
    假如每个测试使用独立 InMemoryOutboxRepository 实例
    当测试后调用 repo.clear()
    那么内存存储被清空
    并且不影响其他测试

  场景: 应用层→领域层→基础设施层协作
    假如六边形架构各层已单独通过单元测试
    当调用应用层用例方法
    那么正确调用领域层服务接口
    并且领域层通过接口访问基础设施层

  场景: 错误传播
    假如仓储层抛出异常
    当应用层调用领域服务
    那么应用层捕获异常
    并且返回正确错误信息

  场景大纲: 集成测试覆盖率与质量门禁
    假如集成测试用例已编写
    当运行集成测试覆盖率检查
    那么集成测试覆盖率 >= <min_coverage>%
    并且 Ruff 检查通过
    并且 MyPy 类型检查通过

    例子:
      | min_coverage |
      | 70           |
