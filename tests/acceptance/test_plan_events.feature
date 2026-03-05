# 战略规划领域事件验收测试

Feature: 战略规划领域事件
  作为领域开发者
  我希望领域事件符合 Schema 规范
  这样我可以确保事件驱动架构的正确性

  Scenario: 创建有效的战略规划创建事件
    Given 一个有效的战略规划创建事件数据
    When 创建 PlanCreated 事件
    Then 事件应该通过 Pydantic 验证
    And 事件 ID 应该自动生成
    And 事件时间戳应该自动设置
    And 事件类型应该自动设置为'plan.created'

  Scenario: 创建事件时提供自定义 ID 和时间
    Given 一个带有自定义 ID 和时间的领域事件
    When 创建事件
    Then 应该使用提供的 ID
    And 应该使用提供的时间

  Scenario: 事件关联聚合根
    Given 一个领域事件
    When 设置聚合根 ID
    Then 事件应该正确关联到聚合根

  Scenario: 事件载荷验证
    Given 一个领域事件
    When 设置事件载荷
    Then 载荷应该是字典类型
    And 载荷应该包含必要字段

  Scenario: 事件继承关系
    Given 一个战略规划事件
    When 检查继承关系
    Then PlanCreated 应该继承自 DomainEvent
    And 应该实现所有必需属性

  Scenario: 事件清空
    Given 一个有多个事件的战略规划
    When 调用 clear_events() 方法
    Then 事件列表应该为空
    And 不影响规划的其他属性

  Scenario: 事件迭代
    Given 一个有多个事件的战略规划
    When 迭代事件列表
    Then 应该按时间顺序返回事件
    And 每个事件都应该是 DomainEvent 类型
