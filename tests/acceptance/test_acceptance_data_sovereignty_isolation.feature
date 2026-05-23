# language: zh-CN
功能: 数据主权隔离

  作为合规工程师
  我想要实现数据主权隔离（敏感数据本地优先处理，外部网络调用需审计与白名单批准）
  以便系统满足数据安全法和 PIPL 要求，确保数据境内存储和跨境传输合规

  背景:
    假如 系统已初始化完成
    并且 领域实体已正确定义

  # =========================================================================
  # AC-1: 敏感数据检测
  # =========================================================================

  场景: 检测 PII 数据
    假如 待检测内容包含身份证号
    假如 内容设置为张三的身份证号110101199001011234
    当 执行敏感数据检测
    那么 系统识别出 PII 类型数据
    并且 检测置信度大于 0.8
    并且 触发 SensitiveDataDetected 事件

  场景: 检测商业秘密数据
    假如 待检测内容包含关键词
    假如 内容设置为公司核心技术配方保密
    当 执行敏感数据检测
    那么 系统识别出 TRADE_SECRET 类型数据
    并且 触发 SensitiveDataDetected 事件

  场景: 检测金融数据
    假如 待检测内容包含银行账号
    假如 内容设置为银行账号6222021234567890123
    当 执行敏感数据检测
    那么 系统识别出 FINANCIAL 类型数据
    并且 触发 SensitiveDataDetected 事件

  场景: 敏感数据检测置信度验证
    假如 高置信度检测结果 confidence=0.95
    当 调用 is_high_confidence() 方法
    那么 返回 True

  场景: 敏感数据类型合并
    假如 两个检测结果分别包含 PII 和 FINANCIAL
    当 调用 merge_with() 方法合并
    那么 合并结果包含两种敏感类型

  # =========================================================================
  # AC-2: 数据驻留策略执行
  # =========================================================================

  场景: 中国大陆数据强制本地处理
    假如 数据驻留策略允许区域为 CHINA_DOMESTIC
    并且 禁止区域为 OVERSEAS
    并且 强制级别为 STRICT
    当 尝试将数据发送到 OVERSEAS 区域
    那么 系统阻止操作
    并且 触发 DataSovereigntyViolation 事件

  场景: STRICT 级别需要本地处理
    假如 数据驻留策略 enforcement_level 为 STRICT
    当 调用 requires_local_processing()
    那么 调用 requires_local_processing() 返回 True

  场景: 数据驻留策略上下文获取
    假如 有效的数据驻留策略
    当 调用 get_policy_context()
    那么 调用 get_policy_context() 返回包含 policy_id、name、allowed_regions 的字典

  # =========================================================================
  # AC-3: 白名单管理
  # =========================================================================

  场景: 经验证的 API 在白名单中且未过期
    假如 白名单条目 endpoint="https://api.domestic.cn" is_verified=True
    并且 白名单条目 valid_until 为 2099-12-31
    当 调用 is_allowed("https://api.domestic.cn")
    那么 调用 is_allowed 返回 True

  场景: 未验证的 API 不在白名单
    假如 白名单条目 is_verified=False
    当 调用 is_allowed()
    那么 调用 is_allowed 返回 False

  场景: 已过期的白名单条目
    假如 白名单条目 valid_until 为 2020-01-01
    当 调用 is_valid()
    那么 调用 is_valid 返回 False

  场景: 高风险 API 需要 DPO 审批
    假如 白名单条目 risk_level=HIGH
    当 调用 requires_dpo_approval()
    那么 调用 requires_dpo_approval 返回 True

  场景: 高风险 API 判断
    假如 白名单条目 risk_level=HIGH
    当 调用 is_high_risk()
    那么 调用 is_high_risk 返回 True

  场景: 距过期天数计算
    假如 白名单条目 valid_until 为 10 天后
    当 调用 days_until_expiry()
    那么 调用 days_until_expiry 返回值大于等于 9

  # =========================================================================
  # AC-4: 跨境数据传输审批
  # =========================================================================

  场景: 创建跨境传输请求
    假如 跨境传输请求 data_id="data-123" destination="US"
    当 请求状态为 pending
    那么 request_transfer() 方法可用

  场景: 跨境传输请求审批通过
    假如 跨境传输请求状态为 pending
    当 调用 approve(approver="admin-001")
    那么 新状态为 APPROVED
    并且 approver 为 "admin-001"
    并且 approval_timestamp 已记录

  场景: 跨境传输请求审批拒绝
    假如 跨境传输请求状态为 pending
    当 调用 reject(approver="admin-001")
    那么 新状态为 REJECTED

  场景: 跨境传输执行
    假如 跨境传输请求已审批通过
    当 调用 execute()
    那么 新状态为 EXECUTED

  场景: 跨境传输阻止
    假如 跨境传输请求状态为 pending
    当 调用 block()
    那么 新状态为 BLOCKED

  场景: 判断待审批状态
    假如 跨境传输请求状态为 pending
    当 调用 is_pending()
    那么 调用 is_pending 返回 True

  场景: PIPL 第 38 条 - 安全评估法律依据
    假如 跨境传输请求 legal_basis_type=security_assessment
    当 验证法律依据有效性
    那么 验证法律依据有效性返回 True

  # =========================================================================
  # AC-5: PIPL 合规
  # =========================================================================

  场景: 有效同意记录合规
    假如 PIPL 合规记录 legal_basis=consent consent_status=given
    当 调用 validate_consent()
    并且 调用 is_compliant()
    那么 调用 validate_consent 返回 True
    并且 调用 is_compliant() 返回 True

  场景: 撤回同意记录不合规
    假如 PIPL 合规记录 consent_status=withdrawn
    当 调用 validate_consent()
    那么 调用 validate_consent 返回 False

  场景: 非同意法律依据自动合规
    假如 PIPL 合规记录 legal_basis=legal_obligation
    当 调用 is_compliant()
    那么 调用 is_compliant() 返回 True

  场景: 未成年人数据需要监护人同意
    假如 PIPL 合规记录 is_minor=True guardian_consent_obtained=True consent_status=given
    当 调用 validate_minor_consent()
    那么 调用 validate_minor_consent 返回 True

  场景: 未成年人数据无监护人同意不合规
    假如 PIPL 合规记录 is_minor=True guardian_consent_obtained=False
    当 调用 validate_minor_consent()
    那么 调用 validate_minor_consent 返回 False

  # =========================================================================
  # AC-6: 合规性网关
  # =========================================================================

  场景: 合规性检查 - 本地处理强制
    假如 任务数据驻留要求为 CHINA_DOMESTIC
    当 调用 ComplianceGateway.check(task)
    那么 返回结果 allowed=True
    并且 返回结果 forced_local=True

  场景: 合规性检查 - 允许非敏感数据
    假如 任务数据驻留要求为 OVERSEAS
    并且 无敏感数据检测结果
    当 调用 ComplianceGateway.check(task)
    那么 返回结果 allowed=True

  场景: 合规结果允许判断
    假如 合规结果 allowed=True
    当 调用 is_allowed()
    那么 调用 is_allowed 返回 True

  场景: 合规结果违规判断
    假如 合规结果 violation_type="unauthorized_transfer"
    当 调用 is_violation()
    那么 调用 is_violation 返回 True

  # =========================================================================
  # 架构约束验证
  # =========================================================================

  场景: 实体不可变性
    假如 领域实体已创建
    当 尝试修改属性
    那么 抛出 AttributeError
