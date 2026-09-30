# language: zh-CN
# Story 4.1f: Skills 数据源扩展——三新源适配器（EPO OPS / SEC EDGAR / UN Comtrade）+ 中文参数 CJK 自适应
# 验收规范：context dict + 真实适配器实例（MockTransport 注入传输层）+ 新适配器步骤内延迟 import；
# key 就绪场景动态 skip；BDD 步骤禁 @pytest.mark.asyncio（event_loop.run_until_complete）。

功能: 数据源扩展验收（AC-1 中文参数自适应 / AC-2 EPO OPS / AC-3 SEC EDGAR / AC-4 UN Comtrade）
  作为工具工程师,
  我想要三个新数据源适配器与现有源中文参数自适应交付,
  以便 Skills 工具箱维度级三角化缺口实质收敛。

  背景:
    假如 数据源扩展验收基础设施已初始化（真实事件总线与缓存，适配器经 MockTransport 注入传输层，新适配器步骤内延迟导入）

  # === AC-1: 中文参数 CJK 自适应（tavily/newsapi 双态） ===

  场景: AC-1.1 - tavily 中文 query 自适应注入国家参数
    假如 构造真实 tavily 适配器并注入捕获传输层
    当 以中文 query "比亚迪 战略动态 并购" 执行数据采集
    那么 请求体自动包含国家参数 "china"

  场景: AC-1.2 - tavily 英文 query 请求体零变化
    假如 构造真实 tavily 适配器并注入捕获传输层
    当 以英文 query "BYD strategy news" 执行数据采集
    那么 请求体与既有形态逐键一致（不含国家参数）

  场景: AC-1.3 - newsapi 中文 query 自适应注入语言参数
    假如 构造真实 newsapi 适配器并注入捕获传输层
    当 以中文 query "宁德时代 产能扩张 最新报道" 执行数据采集
    那么 请求参数自动包含语言参数 "zh"

  场景: AC-1.4 - newsapi 英文 query 请求参数零变化
    假如 构造真实 newsapi 适配器并注入捕获传输层
    当 以英文 query "CATL capacity expansion" 执行数据采集
    那么 请求参数与既有形态逐键一致（不含语言参数）

  # === AC-2: EPO OPS 适配器（OAuth2 + 配额守卫 + 申请人检索） ===

  场景: AC-2.1 - EPO OAuth2 令牌自动获取并检索专利
    假如 构造 EPO OPS 适配器并注入 OAuth2 令牌与检索应答传输层
    当 以 CQL 检索式 "pa=\"华为\" and ti=\"battery\"" 执行数据采集
    那么 OAuth2 令牌经 Basic 凭证自动获取
    并且 业务请求携带 Bearer 令牌
    并且 结果结构化为专利列表（含标题/申请人/申请日）

  场景: AC-2.2 - EPO 令牌缓存命中不重复获取
    假如 构造 EPO OPS 适配器并注入 OAuth2 令牌与检索应答传输层
    当 连续执行两次 CQL 检索
    那么 令牌端点仅被请求一次（缓存命中）

  场景: AC-2.3 - EPO 业务请求 401 令牌失效重取一次
    假如 构造 EPO OPS 适配器并注入首令牌过期场景传输层
    当 以 CQL 检索式 "pa=\"BYD\"" 执行数据采集
    那么 令牌自动刷新一次并重发业务请求
    并且 重试后检索成功

  场景: AC-2.4 - EPO 周配额超限前置拦截抛 412
    假如 构造 EPO OPS 适配器并注入已耗尽周配额计数
    当 以 CQL 检索式 "pa=\"华为\"" 执行数据采集
    那么 前置拦截抛出限流异常（EXCEPTION_412）
    并且 上游零请求消耗

  场景: AC-2.5 - EPO 凭据缺失时条件注册跳过
    假如 子进程环境清理全部数据源凭据
    当 执行组合根引导并检查端口注册态
    那么 EPO 端口未注册（双凭据门关闭）
    并且 EDGAR 与 Comtrade 端口无条件注册

  # === AC-3: SEC EDGAR 适配器（UA 规范 + 双模式） ===

  场景: AC-3.1 - EDGAR 免 key 检索模式返回财报列表
    假如 构造 SEC EDGAR 适配器并注入财报检索应答传输层
    当 以检索式 "market share forms=10-K" 执行数据采集
    那么 全部请求携带规范 UA 头（公司名 邮箱格式）
    并且 结果结构化为财报列表（含公司/表单/申报日）

  场景: AC-3.2 - EDGAR XBRL 前缀分派返回指标时序
    假如 构造 SEC EDGAR 适配器并注入 XBRL 概念应答传输层
    当 以 XBRL 检索式 "xbrl:CIK0001318605:Revenues" 执行数据采集
    那么 请求分派至 XBRL 数据端点
    并且 结果结构化为指标时序（含概念/单位/数值序列）

  场景: AC-3.3 - EDGAR 非法前缀请求前置校验拒绝
    假如 构造 SEC EDGAR 适配器并注入应答传输层
    当 以非法前缀检索式 "bad:foo:bar" 执行数据采集
    那么 前置校验抛出参数校验异常（EXCEPTION_201）
    并且 上游零请求消耗

  # === AC-4: UN Comtrade 适配器（key 可选 + 日配额守卫） ===

  场景: AC-4.1 - Comtrade 免 key preview 检索返回贸易记录
    假如 构造 UN Comtrade 适配器（无 key）并注入贸易记录应答传输层
    当 以管道串 "reporter=156|cmd=8703|flow=X|period=2024" 执行数据采集
    那么 请求不携带订阅头（免 key 模式）
    并且 结果结构化为贸易记录列表（含商品码/贸易值/期间）

  场景: AC-4.2 - Comtrade 配置 key 时附加订阅头
    假如 构造 UN Comtrade 适配器（配置 key）并注入贸易记录应答传输层
    当 以管道串 "reporter=156|cmd=8703" 执行数据采集
    那么 请求自动携带订阅密钥头

  场景: AC-4.3 - Comtrade 管道串缺商品码前置校验拒绝
    假如 构造 UN Comtrade 适配器并注入应答传输层
    当 以缺商品码管道串 "reporter=156|flow=X" 执行数据采集
    那么 前置校验抛出参数校验异常（EXCEPTION_201）
    并且 上游零请求消耗

  场景: AC-4.4 - Comtrade 日配额超限前置拦截抛 412
    假如 构造 UN Comtrade 适配器并注入已耗尽日配额计数
    当 以管道串 "reporter=156|cmd=8703" 执行数据采集
    那么 前置拦截抛出限流异常（EXCEPTION_412）
    并且 上游零请求消耗
