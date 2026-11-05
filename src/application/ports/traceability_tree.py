"""溯源树端口契约（Story 6-7——四层追溯聚合查询面）

五 VO（全部 frozen dataclass，应用层读侧 DTO——树 VO 是读侧 DTO 非领域实体；
CheckpointSummaryView 先例——6-6 应用层 VO 落 ports 文件）+ TraceabilityTreePort
单方法 Protocol。

序列化契约区（Task 0.1 冻结唯一版本——键集 exact set 断言锚在单测）：
    - TraceabilityTree 7 键：plan_id/root/adopted_archives/total_archives/
      degraded_stages/build_degraded/generated_at
    - ConclusionNode 5 键：plan_id/title/summary/stage_count/children
    - StageNode 9 键：stage/display_name/summary/degraded/degrade_reason/
      tools_used/reflection_excerpt/evidence_count/children
    - ChunkNode 6 键：chunk_id/content_excerpt/page_start/page_end/status/children
    - DocumentNode 9 键：document_id/filename/version/page/object_key/bucket/
      bbox/status/jump_ready

树形嵌套语义：
    - chunk 在不同 stage 下重复出现（每条 stage→chunk 路径独立——6-5b 引文去重
      保序是 flat 表语义，树形不做跨 stage 去重）；文档查询去重仅指 find 调用
      次数（服务内缓存），节点形态仍嵌套
    - synthesis 行不产生 StageNode（结论层即其呈现位——conclusions 联展即根
      summary，分析层七 stage 值域=STAGE_VALUE_DOMAIN 八值去 synthesis）

jump_ready 派生说明（DR1-23）：读侧派生布尔非持久面——跳转载荷六键齐备判定
（object_key 非空且 page 非 None）；「30 秒溯源」可达性的节点级观测面。半跳转
语义由 object_key 非 None 直接判别（文档级）——不建 partial 三值枚举：对已暴露
六键的消费方而言 partial 是冗余派生（YAGNI）。

bbox frozen 纪律例外（DR1-23）：dict 是 frozen 逃逸口——__post_init__ 以
MappingProxyType 包裹防原地突变（类型注解用 Mapping 兼容两种形态）。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class DocumentNode:
    """原始文档层节点（第四层——页码级跳转载荷承载面）

    跳转载荷六键= document_id/filename/version/page/object_key/bucket——「30 秒内
    从结论跳转至原始文档坐标点」（prd L243）的数据面：page（页码级定位——PG
    metadata["chunks"] 匹配通道）+ object_key/bucket（MinIO 原始文件直取——6-8
    Web 阅读器消费面）。bbox 键恒在（payload 透传——现状生产恒 None，四元组写入
    归 6-8，OD-8）。
    """

    document_id: str
    filename: str
    version: int
    page: int | None
    object_key: str | None
    bucket: str = "raw-documents"
    bbox: Mapping[str, Any] | None = None
    status: str = "resolved"
    jump_ready: bool = False

    def __post_init__(self) -> None:
        """frozen 纪律例外显式化：dict bbox 包裹为 MappingProxyType 防原地突变."""
        if isinstance(self.bbox, dict):
            object.__setattr__(self, "bbox", MappingProxyType(self.bbox))


@dataclass(frozen=True)
class ChunkNode:
    """数据切片层节点（第三层）

    页码两键取 Qdrant payload 扩键 page_start/page_end 通道（Task 1——6.5b-DF1
    半边清偿）；point_missing 态两键为 None。status 值域 {"resolved",
    "point_missing"}——CitationEntry.VALID_STATUSES 三值中去掉 document_missing
    （该态归 DocumentNode——链路三态两层承载）。
    """

    chunk_id: str
    content_excerpt: str
    page_start: int | None
    page_end: int | None
    status: str
    children: tuple[DocumentNode, ...] = ()


@dataclass(frozen=True)
class StageNode:
    """分析层节点（第二层——七 stage 值域=STAGE_VALUE_DOMAIN 八值去 synthesis）

    「数据来源→计算逻辑→中间结论」三元组承载（or.md L344 经 OD-4 适配论证落位
    分析层——切片/文档层无「计算逻辑」可示）：evidence_count（来源）/
    tools_used+reflection_excerpt（计算逻辑）/ summary（中间结论）。
    """

    stage: str
    display_name: str
    summary: str
    degraded: bool
    degrade_reason: str
    tools_used: tuple[str, ...]
    reflection_excerpt: str
    evidence_count: int
    children: tuple[ChunkNode, ...] = ()


@dataclass(frozen=True)
class ConclusionNode:
    """结论层节点（第一层——synthesis 行的呈现位）

    title 恒「BLM 战略规划溯源」固定文案；summary 优先取 market_insight_synthesis
    行 chain.final_answer JSON 的 conclusions 联展（"\n".join 保序——DR3-8；非
    list/空/解析失败降空串）；stage_count=分析层 StageNode 节点数（全 run=7——
    synthesis 不入分析层，DR1-13）。
    """

    plan_id: str
    title: str
    summary: str
    stage_count: int
    children: tuple[StageNode, ...] = ()


@dataclass(frozen=True)
class TraceabilityTree:
    """溯源树根（读侧聚合结果 VO——7 键）

    - adopted_archives：判 run 后采纳行数（stage 分组 last-write-wins）
    - total_archives：kind 过滤后思维链候选行数（对照信号纯化为 run 压制单现象）
    - degraded_stages：含 ≥1 非 resolved 后代节点的采纳 stage 值元组（升序去重
      ——stage 级降级上卷，正常空元组）
    - build_degraded：query_archive 顶层异常降级标记——空树与真空树分立哨兵
      （空结果必须自我解释是「没有数据」还是「拿不到数据」——读模型诚实性）
    - generated_at：服务层 datetime→isoformat 转换（6-6 CheckpointSummaryView.
      timestamp 同款转换纪律）
    """

    plan_id: str
    root: ConclusionNode
    adopted_archives: int
    total_archives: int
    degraded_stages: tuple[str, ...] = ()
    build_degraded: bool = False
    generated_at: str = ""


@runtime_checkable
class TraceabilityTreePort(Protocol):
    """溯源树聚合查询端口（v1.0.0）——按 plan_id 遍历既有引用链的树查询语义.

    与 3-8 TraceabilityPort.trace(claim) 语义正交（按文本重检索断言面 vs 引用链
    遍历——两端口并立非同义重复，6-5b OD-6 裁定延续）。

    depth 值域 {1,2,3,4} 默认 4（懒加载分层：1=仅结论层/2=+分析层/3=+切片层/
    4=+文档层）；越域守卫归用例层 242（服务层不重复守卫——6-6 list_checkpoints
    先例一致）。单标识查找直接参数形态（端口查询参数决策规则）；async 钦定——
    三依赖 query_archive/get_point/find 全 async（DR1-10）。
    """

    async def build_trace_tree(self, *, plan_id: str, depth: int = 4) -> TraceabilityTree:
        """按 plan_id 构建四层溯源树（depth 懒加载）.

        Args:
            plan_id: 战略规划 ID（UUID 字符串）。
            depth: 展开深度 {1,2,3,4}，默认 4（全树）。

        Returns:
            TraceabilityTree——树整体不因单点依赖失效失败（节点 status 降级承载）；
            query_archive 顶层异常时空树降级（build_degraded=True 分立哨兵）。

        Raises:
            本方法不抛业务异常（空计划幂等读返回空树；畸形输入与越域守卫归用例层）。
        """
        ...
