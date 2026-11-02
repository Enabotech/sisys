"""领域层检查点快照实体模块

定义会话状态快照领域实体，用于中断恢复和时间旅行调试
遵循系统公理二（外部化记忆）：LLM 上下文 = 缓存，磁盘记忆 = 真相来源

Story 6-3 完整形态扩展：新四字段（persistent_note_ref/checksum/
snapshot_metadata/checkpoint_no）+ SHA-256 checksum 计算/验证两方法
（OD-11 参与字段集钦定：身份五字段 + state_data 规范化序列化）。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.domain.exceptions import CheckpointIntegrityError


@dataclass(frozen=True)
class CheckpointSnapshot:
    """会话状态快照领域实体

    创建后不可变。序列化/反序列化由基础设施层适配器负责。

    完整形态（Story 6-3）：checkpoint_no 非空即进入完整形态——构造守卫
    强制 persistent_note_ref 非空（系统公理二：禁止产出无持久化引用的
    完整形态快照——AC-2）；legacy 形态（6-1/6-2/5-10 全默认构造，
    checkpoint_no 为空）守卫不触发（R2A-11 双条件限定防误触发）。

    Attributes:
        snapshot_id: Unique identifier for this snapshot
        session_id: Session this snapshot belongs to
        stage_id: Current execution stage (e.g., "planning", "execution")
        state_version: Version number for optimistic locking
        state_data: The actual state as key-value pairs
        timestamp: When this snapshot was created
        ttl_seconds: Time-to-live in seconds (24h-30d range: 86400-2592000)
        persistent_note_ref: 持久化笔记引用（UUID 字符串——系统公理二强制关联）
        checksum: SHA-256 hexdigest（编排服务在④步构造时显式计算写入，
            不在构造器自动算——6-1/6-2/5-10 既有构造零扰动；修正后服务层重算替换）
        snapshot_metadata: 压缩元数据键族（compression_ratio/quality_score/
            token_count/original_token_count/rerun_count——与 state_data 同源填充，
            读侧以 state_data 为权威——R2A-10 双位分工）
        checkpoint_no: Checkpoint 编号标识（"CP-1".."CP-8"——全局恢复点编号，
            非空即完整形态；stage_number 由其派生——R7-1）

    Note:
        可哈希性：dict 字段（state_data/snapshot_metadata）使 frozen dataclass
        的 hash() 抛 TypeError（既有形态维持——消费方按字段相等性比较）。
    """

    snapshot_id: uuid.UUID = field(default_factory=uuid.uuid4)
    session_id: str = ""
    stage_id: str = ""
    state_version: int = 0
    state_data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    ttl_seconds: int = 86400  # Default 24 hours
    persistent_note_ref: str = ""
    checksum: str = ""
    snapshot_metadata: dict[str, Any] = field(default_factory=dict)
    checkpoint_no: str = ""

    def __post_init__(self) -> None:
        """构造守卫：完整形态强制持久化笔记引用（AC-2 系统公理二）。

        触发条件（双条件限定）：checkpoint_no 非空（进入完整形态）且
        persistent_note_ref 为空 → 抛 484。legacy 形态（checkpoint_no 空）
        不触发——6-1/6-2/5-10 既有全默认构造零扰动（R2A-11）。

        Raises:
            CheckpointIntegrityError: 完整形态快照缺失持久化引用时抛出（484）。
        """
        if self.checkpoint_no and not self.persistent_note_ref:
            raise CheckpointIntegrityError(
                session_id=self.session_id,
                checkpoint_no=self.checkpoint_no,
                reason="empty_persistent_note_ref",
                message="完整形态快照必须携带持久化笔记引用（系统公理二：压缩前必须持久化）",
            )

    def calculate_checksum(self) -> str:
        """计算 SHA-256 checksum（OD-11 参与字段集钦定）。

        公开方法（R1 审查 FR-7：AC-3 钦定「编排服务在④步构造时显式计算
        写入」——本方法即实体的指定外部服务面，公开为契约正形；原名
        _calculate_checksum 的私有性与该钦定形实不符）。

        参与字段：身份五字段 session_id/stage_id/state_version/checkpoint_no/
        persistent_note_ref + state_data 规范化序列化（sort_keys=True 使
        键序无关——完整性保护扩展至恢复载荷 13 键）。snapshot_id 不参与
        （每次更新轮换——身份与版本由 session_id+state_version 承载）。

        Returns:
            SHA-256 hexdigest（64 位十六进制字符串）。
        """
        payload = json.dumps(self.state_data, sort_keys=True, ensure_ascii=False)
        material = "|".join(
            (
                self.session_id,
                self.stage_id,
                str(self.state_version),
                self.checkpoint_no,
                self.persistent_note_ref,
                payload,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """完整性验证（纯判定——重算比对，无副作用不抛异常）。

        缺失 persistent_note_ref 或 checksum（含 legacy 形态空 checksum）
        返回 False；checksum 与重算值不匹配（篡改/损坏）返回 False。
        484 抛出点在恢复编排调用方（checkpoint_service.recover——签名与
        行为一致，AC-3）。

        Returns:
            完整性成立返回 True，否则 False。
        """
        if not self.persistent_note_ref or not self.checksum:
            return False
        return self.calculate_checksum() == self.checksum

    def with_updated_state(self, state_data: dict[str, Any], new_version: int | None = None) -> CheckpointSnapshot:
        """创建包含更新状态数据的新快照

        新四字段透传（R2A-3——修正通道防丢字段）：persistent_note_ref/
        snapshot_metadata/checkpoint_no 透传保留；checksum 不透传（重置
        空串——由服务层重算写入，AC-3 重算点钦定）。

        Args:
            state_data: 要合并的新状态数据
            new_version: 可选的新版本号（默认 state_version + 1）

        Returns:
            合并状态后的新 CheckpointSnapshot
        """
        merged_state = {**self.state_data, **state_data}
        return CheckpointSnapshot(
            snapshot_id=uuid.uuid4(),  # New snapshot ID
            session_id=self.session_id,
            stage_id=self.stage_id,
            state_version=new_version if new_version is not None else self.state_version + 1,
            state_data=merged_state,
            timestamp=datetime.now(UTC),
            ttl_seconds=self.ttl_seconds,
            persistent_note_ref=self.persistent_note_ref,
            checksum="",
            snapshot_metadata=self.snapshot_metadata,
            checkpoint_no=self.checkpoint_no,
        )
