Feature: 六边形架构骨架就绪

  作为系统架构师
  我想要验证六边形架构骨架已正确实现
  以便确保领域逻辑与技术实现隔离

  Scenario: 架构目录结构创建成功
    Given 项目初始化完成
    When 检查项目目录结构
    Then 应存在 src/domain/ 目录
    And 应存在 src/application/ 目录
    And 应存在 src/interfaces/ 目录
    And 应存在 src/infrastructure/ 目录

  Scenario: 领域层零依赖验证
    Given 领域层代码已创建
    When 扫描领域层导入语句
    Then 领域层仅使用 Python 标准库
    And 不存在外部框架导入 (如 langgraph, prefect, fastapi, pydantic, sqlalchemy)

  Scenario: 依赖方向验证
    Given 六边形架构已创建
    When 检查模块依赖方向
    Then 领域层不依赖应用层
    And 领域层不依赖接口层
    And 领域层不依赖基础设施层
    And 应用层不依赖接口层
    And 应用层不依赖基础设施层
    And 接口层可依赖应用层和领域层
    And 基础设施层可依赖应用层和领域层

  Scenario: 核心领域实体骨架存在
    Given 领域层目录结构已创建
    When 检查领域实体文件
    Then StrategicPlan 实体类存在
    And Document 实体类存在
    And Agent 实体类存在
    And Tool 实体类存在
    And Checkpoint 实体类存在

  Scenario: 领域事件定义存在
    Given 领域层目录结构已创建
    When 检查领域事件文件
    Then DomainEvent 基类存在
    And DocumentProcessed 事件存在
    And ToolExecuted 事件存在
    And AgentDecided 事件存在
    And CheckpointReached 事件存在
    And CorrectionApproved 事件存在

  Scenario: 仓储接口定义完成
    Given 领域层目录结构已创建
    When 检查仓储接口文件
    Then BaseRepository 泛型接口存在
    And 接口定义 get_by_id 方法
    And 接口定义 save 方法
    And 接口定义 delete 方法
    And 接口定义 list_all 方法

  Scenario Outline: 领域实体验证方法存在
    Given 领域实体 <entity> 已创建
    When 检查实体类定义
    Then 实体包含 validate() 方法

    Examples: 核心领域实体
      | entity         |
      | StrategicPlan  |
      | Document       |
      | Agent          |
      | Tool           |
      | Checkpoint     |
