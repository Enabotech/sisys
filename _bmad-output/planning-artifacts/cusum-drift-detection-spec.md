# CUSUM 漂移检测基线与阈值规范

**版本：** 1.0.0  
**状态：** 已批准  
**评审日期：** 2026-02-25  
**关联文档：** 架构设计文档 v6.0.0 第 14 章、ADR-012、第 26 章  
**解决问题：** H4 - "CUSUM 漂移检测缺乏基线定义"

---

## 目录

1. [CUSUM 算法原理说明](#1-cusum-算法原理说明)
2. [基线建立流程](#2-基线建立流程)
3. [阈值定义规范](#3-阈值定义规范)
4. [监控指标体系](#4-监控指标体系)
5. [漂移响应流程](#5-漂移响应流程)
6. [自适应阈值机制](#6-自适应阈值机制)
7. [实现代码示例](#7-实现代码示例)
8. [验收标准](#8-验收标准)

---

## 1. CUSUM 算法原理说明

### 1.1 算法数学原理

CUSUM（Cumulative Sum Control Chart，累积和控制图）是一种统计过程控制方法，用于检测过程均值的小幅持续性偏移。相比传统的 Shewhart 控制图，CUSUM 对小幅漂移（0.5σ-2σ）更加敏感。

#### 1.1.1 核心公式

**单侧 CUSUM（检测正向漂移）：**
```
S₀ = 0
Sₜ = max(0, Sₜ₋₁ + (xₜ - μ₀ - k))
```

**单侧 CUSUM（检测负向漂移）：**
```
S₀ = 0
Sₜ = max(0, Sₜ₋₁ + (μ₀ - k - xₜ))
```

**双侧 CUSUM（同时检测双向漂移）：**
```
Sₕ₀ = 0, Sₗ₀ = 0
Sₕₜ = max(0, Sₕₜ₋₁ + (xₜ - μ₀ - k))    # 检测正向漂移
Sₗₜ = max(0, Sₗₜ₋₁ + (μ₀ - k - xₜ))    # 检测负向漂移

漂移判定：Sₕₜ > h 或 Sₗₜ > h → 漂移告警
```

**参数说明：**
| 符号 | 含义 | 计算方法 |
|------|------|---------|
| xₜ | t 时刻的观测值 | 实际测量指标 |
| μ₀ | 目标均值（基线） | 基线期平均值 |
| σ₀ | 目标标准差（基线） | 基线期标准差 |
| k | 参考值（松弛参数） | k = δ × σ₀ / 2，δ为期望检测的最小漂移量（单位：σ） |
| h | 决策阈值（控制限） | h = 5 × σ₀（经验值，可调） |

#### 1.1.2 算法特性

| 特性 | 说明 | 本系统应用 |
|------|------|-----------|
| **累积效应** | 小幅偏差持续累积，最终触发告警 | 检测性能的持续性下降 |
| **记忆性** | 考虑历史所有数据的影响 | 避免单点异常误报 |
| **灵敏度可调** | 通过 k 和 h 参数调节检测灵敏度 | 不同指标采用不同参数 |
| **方向性** | 可分别检测正向和负向漂移 | 区分性能提升和下降 |

### 1.2 为什么适合本系统

| 系统特点 | CUSUM 优势 | 匹配度 |
|---------|-----------|-------|
| **LLM 性能波动大** | 对小幅持续性漂移敏感，过滤随机波动 | ✅ 高 |
| **需要早期预警** | 比 Shewhart 控制图提前 3-5 个周期发现漂移 | ✅ 高 |
| **多指标监控** | 参数可独立配置，适应不同指标特性 | ✅ 高 |
| **误报成本控制** | 累积机制减少单点异常误报 | ✅ 高 |
| **可解释性要求** | 数学原理清晰，便于根因分析 | ✅ 高 |

#### 1.2.1 与其他漂移检测算法对比

| 算法 | 检测灵敏度 | 误报率 | 计算复杂度 | 可解释性 | 适用场景 |
|------|-----------|-------|-----------|---------|---------|
| **CUSUM** | 高（小幅漂移） | 低 | O(n) | 高 | ✅ 本系统 |
| Shewhart 控制图 | 低（大幅漂移） | 中 | O(1) | 高 | 突变检测 |
| EWMA | 中 | 低 | O(n) | 中 | 趋势检测 |
| ADWIN | 高 | 中 | O(log n) | 低 | 数据流概念漂移 |
| Page-Hinkley | 高 | 低 | O(n) | 中 | 在线学习 |

---

## 2. 基线建立流程

### 2.1 基线数据采集期要求

#### 2.1.1 采集期时长

| 阶段 | 时长 | 数据量要求 | 目的 |
|------|------|-----------|------|
| **初始基线** | 14 天 | ≥1000 个有效样本 | 建立初始统计量 |
| **验证基线** | 7 天 | ≥500 个有效样本 | 验证基线稳定性 |
| **正式基线** | 持续更新 | 滑动窗口 30 天 | 生产环境使用 |

#### 2.1.2 数据质量要求

| 要求 | 标准 | 验证方法 |
|------|------|---------|
| **完整性** | 数据缺失率 < 5% | 时间序列连续性检查 |
| **代表性** | 覆盖所有业务场景 | 场景覆盖率统计 |
| **稳定性** | 无重大系统变更 | 变更日志审计 |
| **正常运营** | 无已知故障期间 | 故障记录排除 |

#### 2.1.3 异常数据排除规则

```python
EXCLUSION_RULES = [
    # 规则 1: 系统故障期间数据
    {"type": "incident", "window": "故障开始 - 故障恢复后 2 小时"},
    
    # 规则 2: 重大变更后 24 小时
    {"type": "change", "window": "变更完成 + 24h"},
    
    # 规则 3: 统计离群值（3σ原则）
    {"type": "outlier", "method": "z_score > 3"},
    
    # 规则 4: 节假日特殊流量
    {"type": "holiday", "calendar": "国家法定节假日"},
    
    # 规则 5: 压测/演练期间
    {"type": "test", "tags": ["load_test", "drill"]}
]
```

### 2.2 基线统计量计算方法

#### 2.2.1 核心统计量

```python
class BaselineStatistics:
    """基线统计量计算"""
    
    def __init__(self, data: List[float], confidence_level: float = 0.95):
        self.data = np.array(data)
        self.confidence_level = confidence_level
        
    def compute(self) -> BaselineResult:
        return BaselineResult(
            mean=np.mean(self.data),
            std=np.std(self.data, ddof=1),
            median=np.median(self.data),
            p95=np.percentile(self.data, 95),
            p99=np.percentile(self.data, 99),
            min=np.min(self.data),
            max=np.max(self.data),
            sample_size=len(self.data),
            confidence_interval=self._compute_ci()
        )
    
    def _compute_ci(self) -> Tuple[float, float]:
        """计算均值的置信区间"""
        n = len(self.data)
        se = np.std(self.data, ddof=1) / np.sqrt(n)
        z = stats.norm.ppf((1 + self.confidence_level) / 2)
        mean = np.mean(self.data)
        return (mean - z * se, mean + z * se)
```

#### 2.2.2 分时段基线（季节性调整）

为应对业务的周期性变化，采用**分时段基线**策略：

| 时段类型 | 划分维度 | 基线数量 |
|---------|---------|---------|
| **小时级** | 按小时（0-23 点） | 24 个基线 |
| **工作日/周末** | 工作日 vs 周末 | 2 个基线 |
| **业务周期** | 月初/月中/月末 | 3 个基线 |

**组合策略：** 24 小时 × 2 类型 × 3 周期 = **144 个独立基线**

```python
class TimeSegmentedBaseline:
    """分时段基线管理器"""
    
    def __init__(self):
        self.baselines: Dict[str, BaselineResult] = {}
        
    def get_segment_key(self, timestamp: datetime) -> str:
        """生成时段键"""
        hour = timestamp.hour
        is_weekend = timestamp.weekday() >= 5
        day_segment = self._get_day_segment(timestamp.day)
        
        return f"{hour:02d}_{'weekend' if is_weekend else 'weekday'}_{day_segment}"
    
    def _get_day_segment(self, day: int) -> str:
        if day <= 10:
            return "month_start"
        elif day <= 20:
            return "month_mid"
        else:
            return "month_end"
```

### 2.3 基线有效性验证

#### 2.3.1 稳定性检验

使用**变异系数（CV）**评估基线稳定性：

```
CV = σ / μ

稳定性等级：
- CV < 0.1: 优秀（A 级）
- 0.1 ≤ CV < 0.2: 良好（B 级）
- 0.2 ≤ CV < 0.3: 可接受（C 级）
- CV ≥ 0.3: 不稳定（D 级，需要重新采集）
```

#### 2.3.2 正态性检验

使用**Shapiro-Wilk 检验**验证数据分布：

```python
def validate_baseline(data: List[float]) -> ValidationReport:
    """基线有效性验证"""
    
    # 1. 样本量检查
    if len(data) < 30:
        return ValidationReport(valid=False, reason="样本量不足")
    
    # 2. 缺失值检查
    missing_rate = sum(1 for x in data if x is None) / len(data)
    if missing_rate > 0.05:
        return ValidationReport(valid=False, reason=f"缺失率过高：{missing_rate:.2%}")
    
    # 3. 正态性检验（Shapiro-Wilk）
    stat, p_value = stats.shapiro(data)
    is_normal = p_value > 0.05
    
    # 4. 稳定性检验（变异系数）
    cv = np.std(data) / np.mean(data)
    stability_grade = self._get_stability_grade(cv)
    
    # 5. 趋势检验（Mann-Kendall）
    trend = self._mann_kendall_test(data)
    
    return ValidationReport(
        valid=is_normal and stability_grade in ['A', 'B', 'C'],
        normality=p_value,
        stability_grade=stability_grade,
        has_trend=trend != "no_trend",
        recommendations=self._generate_recommendations(cv, is_normal, trend)
    )
```

#### 2.3.3 基线验证报告模板

| 检验项 | 结果 | 阈值 | 状态 |
|-------|------|------|------|
| 样本量 | 1250 | ≥1000 | ✅ 通过 |
| 缺失率 | 2.3% | <5% | ✅ 通过 |
| 正态性 (p 值) | 0.082 | >0.05 | ✅ 通过 |
| 变异系数 (CV) | 0.15 | <0.3 | ✅ 通过 (B 级) |
| 趋势检验 | 无显著趋势 | - | ✅ 通过 |
| **综合结论** | - | - | ✅ 基线有效 |

---

## 3. 阈值定义规范

### 3.1 控制限（Control Limit）计算

#### 3.1.1 标准 CUSUM 参数配置

| 参数 | 符号 | 默认值 | 计算方法 | 说明 |
|------|------|-------|---------|------|
| 参考值 | k | 0.5σ₀ | k = δ × σ₀ / 2 | 期望检测的最小漂移量 δ=1σ |
| 决策阈值 | h | 5σ₀ | h = 5 × σ₀ | 经验值，平衡灵敏度与误报率 |
| 滑动窗口 | w | 7 天 | 业务定义 | 基线更新周期 |

#### 3.1.2 控制限分级

| 级别 | 阈值 | 触发动作 | 响应时间 |
|------|------|---------|---------|
| **观察级** | S > 3σ₀ | 记录日志，不告警 | - |
| **警告级** | S > 5σ₀ | 发送告警通知 | 15 分钟 |
| **严重级** | S > 8σ₀ | 紧急告警 + 自动降级 | 5 分钟 |

### 3.2 漂移判定阈值

#### 3.2.1 漂移等级定义

| 漂移等级 | CUSUM 值范围 | 性能影响 | 响应策略 |
|---------|-------------|---------|---------|
| **无漂移** | S ≤ 3σ₀ | <5% | 持续监控 |
| **轻微漂移** | 3σ₀ < S ≤ 5σ₀ | 5-10% | 观察 + 记录 |
| **中度漂移** | 5σ₀ < S ≤ 8σ₀ | 10-20% | 告警 + 分析 |
| **严重漂移** | S > 8σ₀ | >20% | 紧急响应 + 自动降级 |

#### 3.2.2 漂移确认机制

单次触发不立即告警，采用**N 中 M 确认机制**：

```
确认规则：在连续 M 个检测周期内，至少 N 个周期触发阈值

默认配置：
- 警告级：3 中 5 确认（60% 触发率）
- 严重级：2 中 3 确认（67% 触发率）
```

```python
class DriftConfirmation:
    """漂移确认器"""
    
    def __init__(self, warning_n=3, warning_m=5, critical_n=2, critical_m=3):
        self.warning_n = warning_n
        self.warning_m = warning_m
        self.critical_n = critical_n
        self.critical_m = critical_m
        self.history: Deque[bool] = deque(maxlen=5)
    
    def add_detection(self, is_drift: bool, level: str) -> Optional[str]:
        self.history.append(is_drift)
        
        if len(self.history) < self.warning_m:
            return None
        
        threshold = self.warning_n if level == "warning" else self.critical_n
        window_size = self.warning_m if level == "warning" else self.critical_m
        
        trigger_count = sum(self.history[-window_size:])
        
        if trigger_count >= threshold:
            return "confirmed"
        return None
```

### 3.3 不同指标的阈值参数

#### 3.3.1 性能指标阈值

| 指标 | 基线计算 | k 值 | h 值 | 检测周期 | 确认规则 |
|------|---------|-----|-----|---------|---------|
| **P95 延迟** | 滑动 7 天均值 | 0.5σ | 5σ | 5 分钟 | 3 中 5 |
| **P99 延迟** | 滑动 7 天均值 | 0.5σ | 6σ | 5 分钟 | 3 中 5 |
| **吞吐量** | 滑动 7 天均值 | 0.5σ | 5σ | 1 分钟 | 3 中 5 |
| **错误率** | 滑动 7 天均值 | 0.3σ | 4σ | 1 分钟 | 2 中 3 |
| **队列等待时间** | 滑动 7 天均值 | 0.5σ | 5σ | 1 分钟 | 3 中 5 |

#### 3.3.2 质量指标阈值

| 指标 | 基线计算 | k 值 | h 值 | 检测周期 | 确认规则 |
|------|---------|-----|-----|---------|---------|
| **准确率** | 滑动 7 天均值 | 0.5σ | 5σ | 15 分钟 | 3 中 5 |
| **幻觉率** | 滑动 7 天均值 | 0.3σ | 4σ | 15 分钟 | 2 中 3 |
| **响应相关性** | 滑动 7 天均值 | 0.5σ | 5σ | 15 分钟 | 3 中 5 |
| **用户满意度** | 滑动 7 天均值 | 0.5σ | 5σ | 1 小时 | 3 中 5 |

#### 3.3.3 成本指标阈值

| 指标 | 基线计算 | k 值 | h 值 | 检测周期 | 确认规则 |
|------|---------|-----|-----|---------|---------|
| **Token 成本/请求** | 滑动 7 天均值 | 0.5σ | 5σ | 1 小时 | 3 中 5 |
| **本地路由占比** | 滑动 7 天均值 | 0.5σ | 4σ | 1 小时 | 3 中 5 |
| **云端 API 调用成本** | 滑动 7 天均值 | 0.5σ | 5σ | 1 小时 | 3 中 5 |

#### 3.3.4 阈值配置管理

```yaml
# config/cusum_thresholds.yaml
cusum:
  global:
    baseline_window_days: 7
    update_interval_hours: 24
    
  metrics:
    # 性能指标
    performance:
      latency_p95:
        k_multiplier: 0.5    # k = 0.5 * σ
        h_multiplier: 5.0    # h = 5 * σ
        detection_interval: 300s  # 5 分钟
        confirmation:
          warning: { n: 3, m: 5 }
          critical: { n: 2, m: 3 }
      
      latency_p99:
        k_multiplier: 0.5
        h_multiplier: 6.0    # P99 更敏感
        detection_interval: 300s
        confirmation:
          warning: { n: 3, m: 5 }
          critical: { n: 2, m: 3 }
      
      throughput:
        k_multiplier: 0.5
        h_multiplier: 5.0
        detection_interval: 60s
        confirmation:
          warning: { n: 3, m: 5 }
          critical: { n: 2, m: 3 }
      
      error_rate:
        k_multiplier: 0.3    # 错误率更敏感
        h_multiplier: 4.0
        detection_interval: 60s
        confirmation:
          warning: { n: 2, m: 3 }
          critical: { n: 2, m: 2 }
    
    # 质量指标
    quality:
      accuracy:
        k_multiplier: 0.5
        h_multiplier: 5.0
        detection_interval: 900s  # 15 分钟
        confirmation:
          warning: { n: 3, m: 5 }
          critical: { n: 2, m: 3 }
      
      hallucination_rate:
        k_multiplier: 0.3
        h_multiplier: 4.0
        detection_interval: 900s
        confirmation:
          warning: { n: 2, m: 3 }
          critical: { n: 2, m: 2 }
    
    # 成本指标
    cost:
      token_cost_per_request:
        k_multiplier: 0.5
        h_multiplier: 5.0
        detection_interval: 3600s  # 1 小时
        confirmation:
          warning: { n: 3, m: 5 }
          critical: { n: 2, m: 3 }
      
      local_routing_ratio:
        k_multiplier: 0.5
        h_multiplier: 4.0    # 本地路由占比更重要
        detection_interval: 3600s
        confirmation:
          warning: { n: 3, m: 5 }
          critical: { n: 2, m: 3 }
```

---

## 4. 监控指标体系

### 4.1 性能指标（Performance Metrics）

#### 4.1.1 延迟指标

| 指标名称 | 定义 | 计算方式 | 基线目标 | 告警阈值 |
|---------|------|---------|---------|---------|
| `latency_p50` | 中位延迟 | 50 百分位 | <400ms | >800ms |
| `latency_p95` | 95 分位延迟 | 95 百分位 | <600ms | >1000ms |
| `latency_p99` | 99 分位延迟 | 99 百分位 | <800ms | >1500ms |
| `latency_mean` | 平均延迟 | 算术平均 | <500ms | >900ms |

**测量点：**
- API Gateway 入口 → 出口（端到端）
- UDMR 路由决策（L1+L2+L3）
- LLM 调用（本地/云端）
- 数据库查询（PostgreSQL/Qdrant/Neo4j）
- 工作流执行（Prefect/LangGraph）

#### 4.1.2 吞吐量指标

| 指标名称 | 定义 | 计算方式 | 基线目标 | 告警阈值 |
|---------|------|---------|---------|---------|
| `requests_per_second` | 请求速率 | 每秒请求数 | ≥50 RPS | <30 RPS |
| `tokens_per_second` | Token 处理速率 | 每秒处理 Token 数 | ≥10000 TPS | <5000 TPS |
| `workflows_per_hour` | 工作流完成率 | 每小时完成工作流数 | ≥100 WF/h | <50 WF/h |

#### 4.1.3 可靠性指标

| 指标名称 | 定义 | 计算方式 | 基线目标 | 告警阈值 |
|---------|------|---------|---------|---------|
| `error_rate` | 错误率 | 错误请求数/总请求数 | <1% | >5% |
| `retry_rate` | 重试率 | 重试次数/总请求数 | <5% | >15% |
| `timeout_rate` | 超时率 | 超时请求数/总请求数 | <0.5% | >3% |
| `availability` | 可用性 | 正常运行时间/总时间 | ≥99% | <98% |

### 4.2 质量指标（Quality Metrics）

#### 4.2.1 LLM 输出质量

| 指标名称 | 定义 | 计算方式 | 基线目标 | 告警阈值 |
|---------|------|---------|---------|---------|
| `accuracy` | 准确率 | 正确响应数/总响应数 | ≥90% | <80% |
| `hallucination_rate` | 幻觉率 | 幻觉响应数/总响应数 | <3% | >8% |
| `relevance_score` | 相关性评分 | 平均相关性（1-5 分） | ≥4.0 | <3.0 |
| `completeness_score` | 完整性评分 | 平均完整性（1-5 分） | ≥4.0 | <3.0 |

**质量检测方法：**
```python
class QualityDetector:
    """LLM 输出质量检测器"""
    
    def __init__(self, shield_cortex: ShieldCortex):
        self.shield_cortex = shield_cortex
    
    async def evaluate(self, response: LLMResponse) -> QualityMetrics:
        # 1. 幻觉检测（ShieldCortex）
        hallucination_score = await self.shield_cortex.detect_hallucination(response)
        
        # 2. 事实准确性（引用验证）
        factual_accuracy = await self._verify_citations(response)
        
        # 3. 相关性（语义相似度）
        relevance = cosine_similarity(response.embedding, query.embedding)
        
        # 4. 完整性（结构化检查）
        completeness = self._check_structure_completeness(response)
        
        return QualityMetrics(
            hallucination_rate=hallucination_score,
            accuracy=factual_accuracy,
            relevance=relevance,
            completeness=completeness
        )
```

#### 4.2.2 用户反馈指标

| 指标名称 | 定义 | 计算方式 | 基线目标 | 告警阈值 |
|---------|------|---------|---------|---------|
| `user_satisfaction` | 用户满意度 | 平均评分（1-5 分） | ≥4.2 | <3.5 |
| `thumbs_up_ratio` | 点赞率 | 点赞数/总反馈数 | ≥80% | <60% |
| `correction_rate` | 用户修正率 | 修正次数/总使用次数 | <10% | >25% |
| `nps_score` | 净推荐值 | 推荐者% - 贬损者% | ≥50 | <30 |

### 4.3 成本指标（Cost Metrics）

#### 4.3.1 Token 成本

| 指标名称 | 定义 | 计算方式 | 基线目标 | 告警阈值 |
|---------|------|---------|---------|---------|
| `cost_per_request` | 单次请求成本 | 总成本/总请求数 | <¥0.05 | >¥0.10 |
| `cost_per_1k_tokens` | 千 Token 成本 | 总成本/(总 Token/1000) | <¥0.02 | >¥0.05 |
| `total_daily_cost` | 日总成本 | 每日累计成本 | <¥500 | >¥1000 |

#### 4.3.2 路由效率

| 指标名称 | 定义 | 计算方式 | 基线目标 | 告警阈值 |
|---------|------|---------|---------|---------|
| `local_routing_ratio` | 本地路由占比 | 本地路由数/总路由数 | ≥80% | <60% |
| `cloud_routing_ratio` | 云端路由占比 | 云端路由数/总路由数 | ≤20% | >40% |
| `routing_efficiency` | 路由效率 | 本地成功数/本地总数 | ≥95% | <85% |

#### 4.3.3 资源利用率

| 指标名称 | 定义 | 计算方式 | 基线目标 | 告警阈值 |
|---------|------|---------|---------|---------|
| `gpu_utilization` | GPU 利用率 | GPU 使用时间/总时间 | 40-70% | >85% |
| `memory_utilization` | 内存利用率 | 内存使用/总内存 | 50-70% | >85% |
| `cache_hit_ratio` | 缓存命中率 | 缓存命中数/总请求数 | ≥60% | <40% |

### 4.4 指标采集架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    指标采集架构                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ 应用层埋点    │    │ 基础设施监控  │    │ 业务层指标    │      │
│  │ (OpenTelemetry)│   │ (Prometheus) │    │ (自定义)     │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         └───────────────────┼───────────────────┘               │
│                             ▼                                   │
│                  ┌─────────────────────┐                        │
│                  │   指标聚合服务       │                        │
│                  │   (Metrics Aggregator)│                       │
│                  └──────────┬──────────┘                        │
│                             │                                   │
│              ┌──────────────┼──────────────┐                   │
│              ▼              ▼              ▼                   │
│     ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│     │ Prometheus  │ │ Grafana     │ │ CUSUM       │            │
│     │ (时序存储)   │ │ (可视化)     │ │ (漂移检测)   │            │
│     └─────────────┘ └─────────────┘ └──────┬──────┘            │
│                                            │                    │
│                                            ▼                    │
│                                   ┌──────────────┐             │
│                                   │ 告警中心      │             │
│                                   │ (AlertCenter)│             │
│                                   └──────────────┘             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. 漂移响应流程

### 5.1 漂移确认机制

#### 5.1.1 多级确认流程

```
检测触发 → 初步确认 → 深度分析 → 根因定位 → 响应执行

1. 检测触发：CUSUM 统计量超过阈值
2. 初步确认：N 中 M 确认机制验证
3. 深度分析：关联指标分析、时间窗口对比
4. 根因定位：故障树分析、变更关联
5. 响应执行：告警通知、自动降级、人工介入
```

#### 5.1.2 确认状态机

```python
class DriftStateMachine:
    """漂移确认状态机"""
    
    states = {
        "IDLE": ["DETECTING"],
        "DETECTING": ["CONFIRMING", "IDLE"],
        "CONFIRMING": ["ANALYZING", "IDLE"],
        "ANALYZING": ["RESPONDING", "IDLE"],
        "RESPONDING": ["RESOLVED", "ESCALATING"],
        "ESCALATING": ["RESPONDING"],
        "RESOLVED": ["IDLE"]
    }
    
    async def transition(self, event: DriftEvent) -> str:
        current_state = self.state
        valid_transitions = self.states.get(current_state, [])
        
        next_state = self._determine_next_state(event)
        
        if next_state not in valid_transitions:
            raise InvalidTransitionError(current_state, next_state)
        
        self.state = next_state
        await self._execute_state_actions(next_state, event)
        
        return next_state
```

### 5.2 告警分级

#### 5.2.1 告警级别定义

| 级别 | 名称 | 触发条件 | 响应时间 | 通知渠道 | 升级策略 |
|------|------|---------|---------|---------|---------|
| **P0** | 紧急 | 严重漂移 + 业务影响>30% | 5 分钟 | 电话 + 短信 + IM | 15 分钟未响应→CTO |
| **P1** | 高 | 中度漂移 + 业务影响 10-30% | 15 分钟 | 短信 + IM | 30 分钟未响应→运维负责人 |
| **P2** | 中 | 轻微漂移 + 业务影响 5-10% | 1 小时 | IM + 邮件 | 2 小时未响应→值班工程师 |
| **P3** | 低 | 观察级漂移 + 业务影响<5% | 4 小时 | 邮件 | 自动关闭 |

#### 5.2.2 告警模板

```yaml
# 告警通知模板
alert_template:
  title: "[{severity}] CUSUM 漂移告警 - {metric_name}"
  
  content: |
    ## 告警详情
    
    **告警级别:** {severity}
    **告警时间:** {timestamp}
    **指标名称:** {metric_name}
    
    ### 漂移信息
    - 当前值：{current_value}
    - 基线值：{baseline_mean} ± {baseline_std}
    - CUSUM 统计量：{cusum_value}
    - 漂移幅度：{drift_percentage}%
    
    ### 影响评估
    - 业务影响：{business_impact}
    - 影响范围：{affected_services}
    - 预计用户影响：{estimated_user_impact}
    
    ### 根因线索
    - 最近变更：{recent_changes}
    - 关联指标：{correlated_metrics}
    - 相似历史：{similar_incidents}
    
    ### 建议操作
    1. {recommended_action_1}
    2. {recommended_action_2}
    3. {recommended_action_3}
    
    [查看详情]({dashboard_url}) | [确认告警]({ack_url}) | [升级告警]({escalate_url})
```

### 5.3 根因分析流程

#### 5.3.1 故障树分析（FTA）

```
CUSUM 漂移告警
├── 性能漂移
│   ├── 延迟增加
│   │   ├── 数据库查询变慢
│   │   │   ├── 索引失效
│   │   │   ├── 锁竞争
│   │   │   └── 数据量增长
│   │   ├── LLM 响应变慢
│   │   │   ├── 云端 API 限流
│   │   │   ├── 本地 GPU 过载
│   │   │   └── 网络延迟
│   │   └── 资源瓶颈
│   │       ├── CPU 饱和
│   │       ├── 内存不足
│   │       └── 磁盘 IO 瓶颈
│   └── 吞吐量下降
│       ├── 队列积压
│       ├── 并发限制
│       └── 外部依赖故障
├── 质量漂移
│   ├── 准确率下降
│   │   ├── 模型性能退化
│   │   ├── 数据分布变化
│   │   └── Prompt 失效
│   └── 幻觉率上升
│       ├── 模型温度过高
│       ├── 上下文截断
│       └── 知识截止
└── 成本漂移
    ├── Token 成本上升
    │   ├── 请求长度增加
    │   ├── 重试次数增加
    │   └── 云端路由比例上升
    └── 本地路由占比下降
        ├── 本地模型故障
        ├── 合规检查拒绝
        └── 质量阈值调整
```

#### 5.3.2 根因分析检查清单

```python
RCA_CHECKLIST = {
    "performance": [
        "检查最近 24 小时系统变更",
        "检查数据库慢查询日志",
        "检查 LLM API 响应时间",
        "检查资源利用率（CPU/内存/磁盘）",
        "检查网络延迟和丢包率",
        "检查队列积压情况"
    ],
    
    "quality": [
        "检查模型版本变更",
        "检查 Prompt 模板变更",
        "检查输入数据分布变化",
        "检查 ShieldCortex 检测结果",
        "检查用户反馈趋势",
        "抽样人工审核最近响应"
    ],
    
    "cost": [
        "检查 Token 使用量趋势",
        "检查路由决策分布",
        "检查云端 API 单价变更",
        "检查重试率变化",
        "检查缓存命中率",
        "检查异常大请求"
    ]
}
```

#### 5.3.3 自动根因分析

```python
class RootCauseAnalyzer:
    """自动根因分析器"""
    
    def __init__(self, metrics_client: MetricsClient, change_db: ChangeDB):
        self.metrics_client = metrics_client
        self.change_db = change_db
    
    async def analyze(self, drift_event: DriftEvent) -> RCAReport:
        report = RCAReport(drift_event=drift_event)
        
        # 1. 变更关联分析
        recent_changes = await self.change_db.get_recent_changes(
            window_hours=24
        )
        report.correlated_changes = self._correlate_changes(
            drift_event, recent_changes
        )
        
        # 2. 关联指标分析
        correlated_metrics = await self._find_correlated_metrics(
            drift_event.metric_name
        )
        report.correlated_metrics = correlated_metrics
        
        # 3. 历史相似事件
        similar_incidents = await self._find_similar_incidents(drift_event)
        report.similar_incidents = similar_incidents
        
        # 4. 根因假设生成
        hypotheses = self._generate_hypotheses(
            drift_event,
            report.correlated_changes,
            report.correlated_metrics
        )
        report.hypotheses = hypotheses
        
        # 5. 建议操作
        report.recommended_actions = self._generate_recommendations(hypotheses)
        
        return report
```

---

## 6. 自适应阈值机制

### 6.1 基线定期更新策略

#### 6.1.1 更新触发条件

| 触发类型 | 条件 | 更新方式 |
|---------|------|---------|
| **定时更新** | 每 24 小时（凌晨 2 点） | 增量更新 |
| **数据量触发** | 新数据≥基线样本 30% | 增量更新 |
| **分布变化触发** | KS 检验 p<0.05 | 全量重建 |
| **手动触发** | 运维人员手动执行 | 全量重建 |

#### 6.1.2 增量更新算法

```python
class IncrementalBaselineUpdater:
    """增量基线更新器"""
    
    def __init__(self, decay_factor: float = 0.95):
        self.decay_factor = decay_factor  # 历史数据衰减因子
        self.baseline: Optional[BaselineResult] = None
    
    def update(self, new_data: List[float]) -> BaselineResult:
        if self.baseline is None:
            self.baseline = self._compute_baseline(new_data)
            return self.baseline
        
        # 指数加权移动平均（EWMA）更新均值
        old_mean = self.baseline.mean
        old_var = self.baseline.std ** 2
        new_mean = np.mean(new_data)
        new_var = np.var(new_data)
        n_old = self.baseline.sample_size
        n_new = len(new_data)
        
        # 加权更新
        alpha = n_new / (n_old + n_new)
        updated_mean = self.decay_factor * old_mean + (1 - self.decay_factor) * new_mean
        
        # 方差更新（合并方差公式）
        updated_var = (
            self.decay_factor * (old_var + old_mean**2) +
            (1 - self.decay_factor) * (new_var + new_mean**2) -
            updated_mean**2
        )
        
        self.baseline = BaselineResult(
            mean=updated_mean,
            std=np.sqrt(updated_var),
            sample_size=n_old + n_new,
            # ... 其他统计量
        )
        
        return self.baseline
```

#### 6.1.3 基线版本管理

```python
class BaselineVersionManager:
    """基线版本管理器"""
    
    def __init__(self, storage: BaselineStorage):
        self.storage = storage
        self.retention_days = 90  # 保留 90 天历史基线
    
    def save_version(self, baseline: BaselineResult, metadata: BaselineMetadata) -> str:
        version_id = f"baseline_{datetime.now().isoformat()}"
        
        self.storage.save(
            version_id=version_id,
            baseline=baseline,
            metadata=metadata
        )
        
        # 清理过期版本
        self._cleanup_old_versions()
        
        return version_id
    
    def rollback(self, target_version: str) -> BaselineResult:
        """回滚到指定版本"""
        return self.storage.get(target_version)
    
    def compare_versions(self, version_a: str, version_b: str) -> BaselineComparison:
        """比较两个基线版本"""
        baseline_a = self.storage.get(version_a)
        baseline_b = self.storage.get(version_b)
        
        return BaselineComparison(
            mean_diff=baseline_b.mean - baseline_a.mean,
            std_diff=baseline_b.std - baseline_a.std,
            relative_change=(baseline_b.mean - baseline_a.mean) / baseline_a.mean
        )
```

### 6.2 季节性调整

#### 6.2.1 季节性模式识别

```python
class SeasonalityDetector:
    """季节性模式检测器"""
    
    def __init__(self, data: List[float], frequency: int = 24):
        self.data = np.array(data)
        self.frequency = frequency  # 周期频率（小时级=24，天级=7）
    
    def detect(self) -> SeasonalityResult:
        # 1. STL 分解（Seasonal-Trend decomposition using LOESS）
        from statsmodels.tsa.seasonal import STL
        
        stl = STL(self.data, period=self.frequency)
        result = stl.fit()
        
        # 2. 季节性强度计算
        seasonal_strength = 1 - (np.var(result.resid) / np.var(result.seasonal + result.resid))
        
        # 3. 周期性检验
        acf = sm.tsa.acf(self.data, nlags=self.frequency * 2)
        is_periodic = np.any(np.abs(acf[self.frequency:]) > 0.5)
        
        return SeasonalityResult(
            has_seasonality=seasonal_strength > 0.5,
            strength=seasonal_strength,
            is_periodic=is_periodic,
            seasonal_component=result.seasonal,
            trend_component=result.trend
        )
```

#### 6.2.2 季节性调整因子

| 时段 | 调整因子 | 说明 |
|------|---------|------|
| 工作日 9-18 点 | 1.2 | 业务高峰 |
| 工作日 18-22 点 | 0.9 | 业务下降 |
| 工作日 22-9 点 | 0.6 | 业务低谷 |
| 周末全天 | 0.5 | 业务低峰 |
| 月初 1-5 日 | 1.3 | 月报高峰 |
| 月末 25-31 日 | 1.2 | 月末高峰 |
| 法定节假日 | 0.3 | 假期低谷 |

#### 6.2.3 季节性调整实现

```python
class SeasonalAdjustedCUSUM:
    """季节性调整 CUSUM 检测器"""
    
    def __init__(self, baselines: Dict[str, BaselineResult], seasonality_factors: Dict[str, float]):
        self.baselines = baselines
        self.seasonality_factors = seasonality_factors
    
    def detect(self, value: float, timestamp: datetime) -> DriftResult:
        # 1. 获取对应时段的基线
        segment_key = self._get_segment_key(timestamp)
        baseline = self.baselines[segment_key]
        
        # 2. 应用季节性调整因子
        adjustment_factor = self.seasonality_factors.get(segment_key, 1.0)
        adjusted_baseline_mean = baseline.mean * adjustment_factor
        adjusted_baseline_std = baseline.std * adjustment_factor
        
        # 3. 执行 CUSUM 检测
        cusum_value = self._update_cusum(value, adjusted_baseline_mean, adjusted_baseline_std)
        
        return DriftResult(
            value=value,
            baseline_mean=adjusted_baseline_mean,
            baseline_std=adjusted_baseline_std,
            cusum=cusum_value,
            is_drift=cusum_value > 5 * adjusted_baseline_std
        )
```

### 6.3 误报抑制

#### 6.3.1 误报来源分析

| 误报来源 | 占比 | 抑制策略 |
|---------|------|---------|
| 单点异常 | 35% | N 中 M 确认机制 |
| 正常业务波动 | 25% | 季节性调整 |
| 计划内变更 | 20% | 变更窗口豁免 |
| 数据质量问题 | 15% | 数据质量检查 |
| 其他 | 5% | 人工反馈学习 |

#### 6.3.2 变更窗口豁免

```python
class ChangeWindowExemption:
    """变更窗口豁免管理器"""
    
    def __init__(self, change_db: ChangeDB):
        self.change_db = change_db
        self.exemption_windows: List[ExemptionWindow] = []
    
    def register_exemption(self, change_id: str, start: datetime, end: datetime, affected_metrics: List[str]):
        """注册豁免窗口"""
        self.exemption_windows.append(ExemptionWindow(
            change_id=change_id,
            start=start,
            end=end,
            affected_metrics=affected_metrics
        ))
    
    def is_exempted(self, metric_name: str, timestamp: datetime) -> Tuple[bool, Optional[str]]:
        """检查是否处于豁免窗口"""
        for window in self.exemption_windows:
            if (metric_name in window.affected_metrics and
                window.start <= timestamp <= window.end):
                return True, window.change_id
        return False, None
```

#### 6.3.3 误报反馈学习

```python
class FalsePositiveLearner:
    """误报反馈学习器"""
    
    def __init__(self, feedback_store: FeedbackStore):
        self.feedback_store = feedback_store
        self.model = self._train_model()
    
    def record_feedback(self, alert_id: str, is_false_positive: bool, reason: str):
        """记录用户反馈"""
        self.feedback_store.save(
            alert_id=alert_id,
            is_false_positive=is_false_positive,
            reason=reason,
            timestamp=datetime.now()
        )
        
        # 定期重新训练
        if self.feedback_store.count() % 100 == 0:
            self._retrain_model()
    
    def should_suppress(self, alert: Alert) -> bool:
        """预测是否应该抑制告警"""
        features = self._extract_features(alert)
        fp_probability = self.model.predict_proba([features])[0][1]
        
        return fp_probability > 0.7  # 70% 概率为误报则抑制
```

#### 6.3.4 告警疲劳抑制

```python
class AlertFatigueSuppressor:
    """告警疲劳抑制器"""
    
    def __init__(self, max_alerts_per_hour: int = 10):
        self.max_alerts_per_hour = max_alerts_per_hour
        self.alert_history: Deque[datetime] = deque(maxlen=100)
    
    def should_suppress(self, alert: Alert) -> bool:
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        # 清理过期记录
        while self.alert_history and self.alert_history[0] < one_hour_ago:
            self.alert_history.popleft()
        
        # 检查是否超过阈值
        if len(self.alert_history) >= self.max_alerts_per_hour:
            return True
        
        self.alert_history.append(now)
        return False
```

---

## 7. 实现代码示例

### 7.1 CUSUM 检测器实现

```python
"""
CUSUM 漂移检测器实现

文件：src/infrastructure/monitoring/cusum_detector.py
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Deque
from collections import deque
import numpy as np
from scipy import stats


@dataclass
class BaselineConfig:
    """基线配置"""
    window_days: int = 7
    min_samples: int = 100
    update_interval_hours: int = 24
    confidence_level: float = 0.95


@dataclass
class CUSUMConfig:
    """CUSUM 配置"""
    k_multiplier: float = 0.5  # k = 0.5 * σ
    h_multiplier: float = 5.0  # h = 5 * σ
    confirmation_n: int = 3  # N 中 M 确认的 N
    confirmation_m: int = 5  # N 中 M 确认的 M
    detection_interval_seconds: int = 300  # 检测间隔


@dataclass
class BaselineResult:
    """基线统计结果"""
    mean: float
    std: float
    median: float
    p95: float
    p99: float
    sample_size: int
    confidence_interval: Tuple[float, float]
    computed_at: datetime = field(default_factory=datetime.now)
    
    @property
    def cv(self) -> float:
        """变异系数"""
        return self.std / self.mean if self.mean != 0 else float('inf')


@dataclass
class DriftResult:
    """漂移检测结果"""
    metric_name: str
    value: float
    baseline_mean: float
    baseline_std: float
    cusum_high: float  # 正向漂移统计量
    cusum_low: float   # 负向漂移统计量
    is_drift: bool
    drift_direction: str  # "up", "down", "none"
    severity: str  # "none", "minor", "moderate", "severe"
    timestamp: datetime = field(default_factory=datetime.now)


class CUSUMDetector:
    """
    CUSUM 漂移检测器
    
    实现双侧 CUSUM 算法，支持：
    - 动态基线更新
    - N 中 M 确认机制
    - 多指标并行检测
    """
    
    def __init__(self, config: CUSUMConfig, baseline_config: BaselineConfig):
        self.config = config
        self.baseline_config = baseline_config
        
        # 基线存储
        self.baselines: Dict[str, BaselineResult] = {}
        
        # CUSUM 统计量
        self.cusum_high: Dict[str, float] = {}
        self.cusum_low: Dict[str, float] = {}
        
        # 确认历史
        self.confirmation_history: Dict[str, Deque[bool]] = {}
        
        # 最近检测值
        self.recent_values: Dict[str, Deque[float]] = {}
    
    def update_baseline(self, metric_name: str, data: List[float]) -> BaselineResult:
        """更新指标基线"""
        if len(data) < self.baseline_config.min_samples:
            raise ValueError(f"样本量不足：{len(data)} < {self.baseline_config.min_samples}")
        
        baseline = self._compute_baseline(data)
        self.baselines[metric_name] = baseline
        
        # 重置 CUSUM 统计量
        self.cusum_high[metric_name] = 0.0
        self.cusum_low[metric_name] = 0.0
        self.confirmation_history[metric_name] = deque(maxlen=self.config.confirmation_m)
        self.recent_values[metric_name] = deque(maxlen=self.baseline_config.window_days * 24)
        
        return baseline
    
    def detect(self, metric_name: str, value: float) -> Optional[DriftResult]:
        """
        执行 CUSUM 漂移检测
        
        Args:
            metric_name: 指标名称
            value: 当前观测值
            
        Returns:
            DriftResult 或 None（基线不存在时）
        """
        if metric_name not in self.baselines:
            return None
        
        baseline = self.baselines[metric_name]
        
        # 计算 CUSUM 统计量
        k = self.config.k_multiplier * baseline.std
        h = self.config.h_multiplier * baseline.std
        
        # 更新 CUSUM 统计量
        self.cusum_high[metric_name] = max(
            0,
            self.cusum_high[metric_name] + (value - baseline.mean - k)
        )
        self.cusum_low[metric_name] = max(
            0,
            self.cusum_low[metric_name] + (baseline.mean - k - value)
        )
        
        # 记录最近值
        self.recent_values[metric_name].append(value)
        
        # 判断是否漂移
        cusum_max = max(self.cusum_high[metric_name], self.cusum_low[metric_name])
        is_drift = cusum_max > h
        
        # 确认机制
        self.confirmation_history[metric_name].append(is_drift)
        confirmed = self._confirm_drift(metric_name)
        
        if not confirmed:
            return None
        
        # 确定漂移方向和严重程度
        direction = self._determine_direction(metric_name)
        severity = self._determine_severity(cusum_max, baseline.std)
        
        return DriftResult(
            metric_name=metric_name,
            value=value,
            baseline_mean=baseline.mean,
            baseline_std=baseline.std,
            cusum_high=self.cusum_high[metric_name],
            cusum_low=self.cusum_low[metric_name],
            is_drift=True,
            drift_direction=direction,
            severity=severity
        )
    
    def _compute_baseline(self, data: List[float]) -> BaselineResult:
        """计算基线统计量"""
        arr = np.array(data)
        
        mean = np.mean(arr)
        std = np.std(arr, ddof=1)
        
        # 置信区间
        n = len(arr)
        se = std / np.sqrt(n)
        z = stats.norm.ppf((1 + self.baseline_config.confidence_level) / 2)
        ci = (mean - z * se, mean + z * se)
        
        return BaselineResult(
            mean=float(mean),
            std=float(std),
            median=float(np.median(arr)),
            p95=float(np.percentile(arr, 95)),
            p99=float(np.percentile(arr, 99)),
            sample_size=n,
            confidence_interval=ci
        )
    
    def _confirm_drift(self, metric_name: str) -> bool:
        """N 中 M 确认机制"""
        history = self.confirmation_history.get(metric_name, deque())
        if len(history) < self.config.confirmation_m:
            return False
        
        trigger_count = sum(history[-self.config.confirmation_m:])
        return trigger_count >= self.config.confirmation_n
    
    def _determine_direction(self, metric_name: str) -> str:
        """确定漂移方向"""
        if self.cusum_high[metric_name] > self.cusum_low[metric_name]:
            return "up"
        elif self.cusum_low[metric_name] > self.cusum_high[metric_name]:
            return "down"
        return "none"
    
    def _determine_severity(self, cusum_value: float, baseline_std: float) -> str:
        """确定漂移严重程度"""
        ratio = cusum_value / baseline_std
        
        if ratio > 8:
            return "severe"
        elif ratio > 5:
            return "moderate"
        elif ratio > 3:
            return "minor"
        return "none"
    
    def get_baseline(self, metric_name: str) -> Optional[BaselineResult]:
        """获取指标基线"""
        return self.baselines.get(metric_name)
    
    def reset(self, metric_name: str):
        """重置指标检测状态"""
        if metric_name in self.cusum_high:
            self.cusum_high[metric_name] = 0.0
        if metric_name in self.cusum_low:
            self.cusum_low[metric_name] = 0.0
        if metric_name in self.confirmation_history:
            self.confirmation_history[metric_name].clear()
```

### 7.2 配置管理

```python
"""
CUSUM 配置管理

文件：src/infrastructure/monitoring/cusum_config.py
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import yaml


@dataclass
class MetricThresholdConfig:
    """指标阈值配置"""
    k_multiplier: float
    h_multiplier: float
    detection_interval_seconds: int
    confirmation_warning: Dict[str, int]
    confirmation_critical: Dict[str, int]


@dataclass
class CUSUMGlobalConfig:
    """全局配置"""
    baseline_window_days: int = 7
    update_interval_hours: int = 24
    min_baseline_samples: int = 100
    enable_seasonality: bool = True
    enable_auto_update: bool = True


@dataclass
class CUSUMConfig:
    """完整配置"""
    global_config: CUSUMGlobalConfig
    metric_configs: Dict[str, MetricThresholdConfig]
    
    @classmethod
    def from_yaml(cls, path: str) -> "CUSUMConfig":
        """从 YAML 文件加载配置"""
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        global_config = CUSUMGlobalConfig(
            baseline_window_days=data['cusum']['global']['baseline_window_days'],
            update_interval_hours=data['cusum']['global']['update_interval_hours'],
            min_baseline_samples=data['cusum']['global'].get('min_baseline_samples', 100),
            enable_seasonality=data['cusum']['global'].get('enable_seasonality', True),
            enable_auto_update=data['cusum']['global'].get('enable_auto_update', True)
        )
        
        metric_configs = {}
        for category, metrics in data['cusum']['metrics'].items():
            for metric_name, config in metrics.items():
                metric_configs[metric_name] = MetricThresholdConfig(
                    k_multiplier=config['k_multiplier'],
                    h_multiplier=config['h_multiplier'],
                    detection_interval_seconds=config['detection_interval'],
                    confirmation_warning=config['confirmation']['warning'],
                    confirmation_critical=config['confirmation']['critical']
                )
        
        return cls(global_config=global_config, metric_configs=metric_configs)
    
    def get_metric_config(self, metric_name: str) -> Optional[MetricThresholdConfig]:
        """获取指标配置"""
        return self.metric_configs.get(metric_name)


# 配置加载示例
def load_cusum_config() -> CUSUMConfig:
    """加载 CUSUM 配置"""
    config_path = Path(__file__).parent / "config" / "cusum_thresholds.yaml"
    return CUSUMConfig.from_yaml(str(config_path))
```

### 7.3 监控集成

```python
"""
CUSUM 与 Prometheus/Grafana 集成

文件：src/infrastructure/monitoring/cusum_integration.py
"""

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
from typing import Dict, Optional
import asyncio


class CUSUMPrometheusIntegration:
    """CUSUM Prometheus 集成"""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        
        # 漂移检测计数器
        self.drift_detected = Counter(
            'cusum_drift_detected_total',
            'CUSUM 漂移检测次数',
            ['metric_name', 'direction', 'severity'],
            registry=self.registry
        )
        
        # CUSUM 统计量仪表盘
        self.cusum_value = Gauge(
            'cusum_statistic',
            'CUSUM 统计量当前值',
            ['metric_name', 'direction'],
            registry=self.registry
        )
        
        # 基线统计量仪表盘
        self.baseline_mean = Gauge(
            'cusum_baseline_mean',
            '基线均值',
            ['metric_name'],
            registry=self.registry
        )
        
        self.baseline_std = Gauge(
            'cusum_baseline_std',
            '基线标准差',
            ['metric_name'],
            registry=self.registry
        )
        
        # 确认状态
        self.confirmation_count = Gauge(
            'cusum_confirmation_count',
            '确认触发次数',
            ['metric_name'],
            registry=self.registry
        )
    
    def record_drift(self, metric_name: str, direction: str, severity: str):
        """记录漂移事件"""
        self.drift_detected.labels(
            metric_name=metric_name,
            direction=direction,
            severity=severity
        ).inc()
    
    def update_cusum_value(self, metric_name: str, direction: str, value: float):
        """更新 CUSUM 统计量"""
        self.cusum_value.labels(
            metric_name=metric_name,
            direction=direction
        ).set(value)
    
    def update_baseline(self, metric_name: str, mean: float, std: float):
        """更新基线统计量"""
        self.baseline_mean.labels(metric_name=metric_name).set(mean)
        self.baseline_std.labels(metric_name=metric_name).set(std)
    
    def update_confirmation(self, metric_name: str, count: int):
        """更新确认计数"""
        self.confirmation_count.labels(metric_name=metric_name).set(count)


class CUSUMMonitor:
    """CUSUM 监控服务"""
    
    def __init__(self, detector: CUSUMDetector, prometheus: CUSUMPrometheusIntegration):
        self.detector = detector
        self.prometheus = prometheus
        self.running = False
    
    async def start_monitoring(self, metrics_source: MetricsSource):
        """启动监控"""
        self.running = True
        
        while self.running:
            # 获取所有指标当前值
            metrics = await metrics_source.get_all_metrics()
            
            for metric_name, value in metrics.items():
                result = self.detector.detect(metric_name, value)
                
                if result:
                    # 更新 Prometheus 指标
                    self.prometheus.update_cusum_value(
                        metric_name,
                        result.drift_direction,
                        max(result.cusum_high, result.cusum_low)
                    )
                    
                    if result.is_drift:
                        self.prometheus.record_drift(
                            metric_name,
                            result.drift_direction,
                            result.severity
                        )
                        
                        # 触发告警
                        await self._trigger_alert(result)
            
            # 等待下一个检测周期
            await asyncio.sleep(self._get_detection_interval())
    
    async def _trigger_alert(self, result: DriftResult):
        """触发告警"""
        # 实现告警逻辑
        pass
    
    def _get_detection_interval(self) -> int:
        """获取检测间隔"""
        # 返回最小检测间隔
        return 60
    
    def stop_monitoring(self):
        """停止监控"""
        self.running = False
```

### 7.4 完整使用示例

```python
"""
CUSUM 漂移检测完整使用示例

文件：examples/cusum_usage.py
"""

import asyncio
from datetime import datetime, timedelta
from typing import List
import numpy as np

from src.infrastructure.monitoring.cusum_detector import CUSUMDetector, CUSUMConfig, BaselineConfig
from src.infrastructure.monitoring.cusum_integration import CUSUMMonitor, CUSUMPrometheusIntegration


async def main():
    # 1. 创建配置
    cusum_config = CUSUMConfig(
        k_multiplier=0.5,
        h_multiplier=5.0,
        confirmation_n=3,
        confirmation_m=5,
        detection_interval_seconds=300
    )
    
    baseline_config = BaselineConfig(
        window_days=7,
        min_samples=100,
        update_interval_hours=24
    )
    
    # 2. 创建检测器
    detector = CUSUMDetector(cusum_config, baseline_config)
    
    # 3. 生成基线数据（模拟正常运营 7 天）
    np.random.seed(42)
    baseline_data = np.random.normal(loc=500, scale=50, size=1000).tolist()
    
    # 4. 建立基线
    baseline = detector.update_baseline("latency_p95", baseline_data)
    print(f"基线建立完成：均值={baseline.mean:.2f}ms, 标准差={baseline.std:.2f}ms")
    
    # 5. 模拟实时监控
    print("\n开始实时监控...")
    
    # 正常数据（前 20 个点）
    for i in range(20):
        value = np.random.normal(500, 50)
        result = detector.detect("latency_p95", value)
        if result and result.is_drift:
            print(f"[{i}] 漂移检测：{result.severity} - {result.drift_direction}")
        else:
            print(f"[{i}] 正常：{value:.2f}ms")
    
    # 模拟性能漂移（从第 21 个点开始，均值逐渐上升）
    print("\n--- 模拟性能漂移 ---")
    for i in range(20, 50):
        drift = (i - 20) * 10  # 逐渐增加 10ms/点
        value = np.random.normal(500 + drift, 50)
        result = detector.detect("latency_p95", value)
        
        status = "正常"
        if result:
            if result.is_drift:
                status = f"🚨 漂移：{result.severity} - {result.drift_direction}"
            else:
                status = f"⚠️ 检测中：CUSUM={max(result.cusum_high, result.cusum_low):.2f}"
        
        print(f"[{i}] {status} - 当前值：{value:.2f}ms")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. 验收标准

### 8.1 检测准确率

| 指标 | 目标值 | 测量方法 | 验收标准 |
|------|-------|---------|---------|
| **漂移检出率** | ≥95% | 注入已知漂移 / 检出数 | ≥95% |
| **误报率** | ≤5% | 误报数 / 总告警数 | ≤5% |
| **漏报率** | ≤5% | 漏报数 / 实际漂移数 | ≤5% |
| **平均检测延迟** | <5 分钟 | 漂移发生到告警时间 | <5 分钟 |

**测试方法：**
```python
def test_detection_accuracy():
    """检测准确率测试"""
    # 1. 准备测试数据
    normal_data = np.random.normal(500, 50, 1000)
    
    # 2. 注入已知漂移（+2σ, +3σ, +4σ）
    drift_scenarios = [
        {"magnitude": 2, "expected_detect": True},
        {"magnitude": 3, "expected_detect": True},
        {"magnitude": 4, "expected_detect": True},
    ]
    
    # 3. 执行测试
    results = []
    for scenario in drift_scenarios:
        drift_data = np.random.normal(500 + scenario["magnitude"] * 50, 50, 100)
        detected = detector.detect("test_metric", drift_data)
        results.append(detected == scenario["expected_detect"])
    
    # 4. 计算准确率
    accuracy = sum(results) / len(results)
    assert accuracy >= 0.95, f"检出率不足：{accuracy}"
```

### 8.2 误报率

| 场景 | 目标误报率 | 测试方法 |
|------|-----------|---------|
| 正常运营数据 | ≤1% | 7 天正常数据测试 |
| 季节性波动 | ≤2% | 含季节性的 30 天数据 |
| 变更后数据 | ≤5% | 计划内变更窗口测试 |
| 综合误报率 | ≤5% | 混合场景测试 |

### 8.3 响应时间

| 操作 | 目标时间 | 测量方式 |
|------|---------|---------|
| 单次检测 | <10ms | 端到端延迟 |
| 基线更新 | <1 秒 | 1000 样本更新 |
| 告警触发 | <5 秒 | 检测到告警发出 |
| 仪表盘刷新 | <3 秒 | Grafana 加载时间 |

### 8.4 系统资源

| 资源 | 目标使用 | 测量方式 |
|------|---------|---------|
| CPU 使用率 | <5% | 监控进程 CPU |
| 内存使用 | <500MB | 监控进程内存 |
| 存储占用 | <1GB/月 | 基线数据存储 |

### 8.5 验收测试清单

| 测试项 | 测试方法 | 预期结果 | 状态 |
|-------|---------|---------|------|
| 基线建立 | 输入 1000 个正常样本 | 基线有效，CV<0.3 | ☐ |
| 正常检测 | 输入正常波动数据 | 无漂移告警 | ☐ |
| 漂移检测 | 注入+2σ漂移 | 5 分钟内告警 | ☐ |
| 严重漂移 | 注入+4σ漂移 | 2 分钟内严重告警 | ☐ |
| 负向漂移 | 注入 -2σ漂移 | 正确检测负向漂移 | ☐ |
| 季节性调整 | 输入周期性数据 | 无误报 | ☐ |
| 变更豁免 | 注册豁免窗口 | 窗口内不告警 | ☐ |
| N 中 M 确认 | 输入间歇性异常 | 符合确认规则 | ☐ |
| 基线更新 | 输入新数据 | 基线正确更新 | ☐ |
| Prometheus 集成 | 检查指标暴露 | 所有指标可见 | ☐ |
| 告警通知 | 触发漂移 | 收到告警通知 | ☐ |
| 根因分析 | 模拟已知故障 | 正确关联根因 | ☐ |
| 性能测试 | 100 指标并发检测 | 延迟<10ms | ☐ |
| 稳定性测试 | 7 天连续运行 | 无内存泄漏 | ☐ |
| 恢复测试 | 重启后恢复 | 基线和状态恢复 | ☐ |

---

## 附录

### A. 参考文档

1. Page, E. S. (1954). "Continuous Inspection Schemes". Biometrika.
2. Hawkins, D. M., & Olwell, D. H. (1998). "Cumulative Sum Charts and Charting for Quality Improvement".
3. Prometheus 官方文档：https://prometheus.io/docs/
4. Grafana 官方文档：https://grafana.com/docs/

### B. 配置模板

完整 YAML 配置模板见第 3.3.4 节。

### C. 相关架构文档

- 架构设计文档 v6.0.0 第 14 章：质量属性设计
- ADR-012：CUSUM 漂移检测决策记录
- 架构设计文档 v6.0.0 第 26 章：工作流监控与运维

---

**文档版本：** 1.0.0  
**最后更新：** 2026-02-25  
**审核状态：** 已批准  
**下一步：** 实施开发（预计 2 周完成）
