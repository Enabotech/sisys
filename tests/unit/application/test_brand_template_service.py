"""品牌模板服务单元测试（Story 6-11 Task 4——save 编排+校验矩阵+get_render_spec 组装）。

覆盖面：
- save 编排顺序锚：``get_by_name`` 先行（同名取既有 template_id+logo_object_key
  ——保留语义与 L4 键锚定的单源承载位）→ 值域校验+name 前置预检 → logo 校验 →
  [logo_path 在场]L4 store → 实体构造（updated_at 服务侧定时戳）→ repo.save
  （仓储纯 UPSERT 落库——spec Mock await 序断言：get_by_name→store→save）
- 校验矩阵（494×10+242×1+成功×2——与 AC-7「七形态=494 全触发面」分立口径：
  矩阵含 242/成功格；R1-F6 拓宽像素/解析两负例+空文件/不可读伞形补格）：非法
  color key/非法 font key/空 name[242 由实体抛——服务预检透传]/magic bytes 非
  PNG-JPEG/空文件[magic 族输入边界]/超 2MB/路径不存在/不可读伞形[chmod-000+
  getsize 权限]/像素超限/图像体无法解析[magic 合法+垃圾体]/合法全参/4000px
  恰值边界
- 预检先于 L4（非法 name/color+logo 形态 store 零调用——防孤儿 logo 对象）
- 保留语义：已有 logo 模板再存不带 --logo-path → logo_object_key 不变+L4 零新调用
- 孤儿 logo 补偿（R1-F5）：repo.save 失败对**本次新写键** best-effort delete——
  首存两分支[协议外包装/495 透传]均补偿+delete kwargs 锚；修订既有键形态零补偿
  [删除即丢 PG 行引用的既有 logo]；修订无既有 logo 的新写键补偿[朴素首存条件
  判别锚]；补偿 delete 失败仅告警不掩盖原始异常
- get_render_spec：模板存在→预设映射组装 7 键 spec；不存在→494[message 含模板名]；
  logo 缺席→spec.logo=None+retrieve 零调用；L4 异常→495；脏预设键（直写行）→494
- list 透传（repo list → tuple 化）

Mock 工厂（AsyncMock spec=Protocol）+ 真实 BrandTemplate/BrandRenderSpec VO。

Run with:
    poetry run pytest tests/unit/application/test_brand_template_service.py -v
"""

import uuid as uuid_module
from datetime import UTC, datetime
from typing import Any

import pytest

from src.application.ports.pdf_report import BrandRenderSpec
from src.domain.entities.brand_template import BrandTemplate
from src.domain.exceptions import BrandTemplateStorageError, BrandTemplateValidationError, EntityValidationError

#: 品牌 L4 桶类型（服务单源对齐断言期望独立字面——双源漂移即红）
_BRAND_BUCKET_TYPE = "brand-assets"

#: Logo 大小上限（AC-2：2MB——防误传大图渲染 OOM）
_LOGO_MAX_BYTES = 2 * 1024 * 1024


def _make_template(**overrides: Any) -> BrandTemplate:
    """模板实体构造 helper（服务返回值断言用）。"""
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "template_id": uuid_module.uuid4(),
        "name": f"test-{uuid_module.uuid4().hex[:8]}-模板",
        "color_scheme": "corporate-blue",
        "font_preset": "noto-sans-sc",
        "logo_object_key": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return BrandTemplate(**defaults)


def _make_logo_png(path: Any) -> None:
    """Pillow 生成最小合法 PNG（渲染正例可解码前提）。"""
    from PIL import Image

    Image.new("RGB", (32, 32), color=(31, 78, 121)).save(path, format="PNG")


def _make_service(
    *,
    existing: BrandTemplate | None = None,
    repo_rows: list[BrandTemplate] | None = None,
    store_side_effect: Any = None,
    retrieve_side_effect: Any = None,
) -> tuple[Any, dict[str, Any]]:
    """构造被测服务（repo/l4 双 AsyncMock spec）。"""
    from unittest.mock import AsyncMock

    from src.application.services.brand_template_service import BrandTemplateService
    from src.domain.ports.brand_template_repository import BrandTemplateRepositoryProtocol
    from src.domain.ports.l4_object import L4ObjectPort

    repo = AsyncMock(spec=BrandTemplateRepositoryProtocol)
    repo.get_by_name.return_value = existing
    repo.list_templates.return_value = repo_rows if repo_rows is not None else ([existing] if existing else [])

    async def _save(template: BrandTemplate) -> BrandTemplate:
        return template

    repo.save.side_effect = _save
    l4 = AsyncMock(spec=L4ObjectPort)
    if store_side_effect is not None:
        l4.store.side_effect = store_side_effect
    else:
        l4.store.return_value = "version-id"
    if retrieve_side_effect is not None:
        l4.retrieve.side_effect = retrieve_side_effect
    else:

        async def _retrieve(*args: Any, **kwargs: Any) -> Any:
            yield b"\x89PNG\r\n\x1a\nfake-logo-bytes"

        l4.retrieve.side_effect = lambda *a, **kw: _retrieve()
    service = BrandTemplateService(
        brand_template_repository=repo,
        l4_object=l4,
    )
    return service, {"repo": repo, "l4": l4}


class TestSaveOrchestration:
    """save 编排（get_by_name 先行→校验→L4 store→构造→repo.save）。"""

    async def test_save_full_params_first_insert(self, tmp_path: Any) -> None:
        """合法全参首存（INSERT 形态：新 template_id+logo 上传+repo.save 落库）。"""
        logo = tmp_path / "logo.png"
        _make_logo_png(logo)
        service, mocks = _make_service()
        saved = await service.save_brand_template(
            name="商务蓝模板", color_scheme="corporate-blue", font_preset="noto-sans-sc", logo_path=str(logo)
        )
        assert saved.name == "商务蓝模板"
        assert saved.logo_object_key == f"logos/{saved.template_id}"
        assert saved.updated_at is not None and saved.created_at is not None
        mocks["l4"].store.assert_awaited_once()
        store_call = mocks["l4"].store.call_args
        assert store_call.kwargs["bucket_type"] == _BRAND_BUCKET_TYPE
        assert store_call.kwargs["object_key"] == f"logos/{saved.template_id}"
        assert store_call.kwargs["content_type"] == "image/png"
        mocks["repo"].save.assert_awaited_once()

    async def test_save_order_get_by_name_first(self, tmp_path: Any) -> None:
        """编排顺序锚：get_by_name 先行（保留语义与键锚定单源）→ store → save
        （await 序断言——六边形 Mock 纪律；save 殿后由 repo.save 在 store
        返回后才构造实体的编排结构承载）。"""
        logo = tmp_path / "logo.png"
        _make_logo_png(logo)
        service, mocks = _make_service()
        # 跨 mock 对象 await 序采集（side_effect 记录法——固定返回值不回调
        # mock 自身防递归）
        calls: list[str] = []

        async def _record_get(name: str) -> BrandTemplate | None:
            calls.append("get_by_name")
            return None

        async def _record_store(*args: Any, **kwargs: Any) -> str:
            calls.append("store")
            return "version-id"

        async def _record_save(template: BrandTemplate) -> BrandTemplate:
            calls.append("save")
            return template

        mocks["repo"].get_by_name.side_effect = _record_get
        mocks["l4"].store.side_effect = _record_store
        mocks["repo"].save.side_effect = _record_save
        await service.save_brand_template(name="顺序模板", color_scheme="graphite", font_preset="stsong", logo_path=str(logo))
        assert calls == ["get_by_name", "store", "save"], f"编排序漂移: {calls}"

    async def test_save_same_name_preserves_template_id_and_logo(self, tmp_path: Any) -> None:
        """同名再存保留既有 template_id+logo_object_key（修订语义——L4 键
        锚定既有 template_id 实现同键覆盖）。"""
        existing = _make_template(name="修订模板", logo_object_key="logos/existing-id")
        logo = tmp_path / "logo2.png"
        _make_logo_png(logo)
        service, mocks = _make_service(existing=existing)
        saved = await service.save_brand_template(
            name="修订模板",
            color_scheme="burgundy",
            font_preset="stsong",
            logo_path=str(logo),
        )
        assert str(saved.template_id) == str(existing.template_id), "同名再存 template_id 漂移"
        assert saved.created_at == existing.created_at, "修订不动 created_at"
        assert saved.updated_at is not None and saved.updated_at > existing.updated_at, "updated_at 未前进"
        # logo 重传：同键覆盖（既有 template_id 锚定的对象键）
        assert saved.logo_object_key == f"logos/{existing.template_id}"

    async def test_save_without_logo_keeps_existing_key(self) -> None:
        """保留语义：已有 logo 模板再存不带 logo_path → logo_object_key 不变
        +L4 零新调用（缺席≠清除——清除归后续模板管理 Story）。"""
        existing = _make_template(name="保留模板", logo_object_key="logos/keep-me")
        service, mocks = _make_service(existing=existing)
        saved = await service.save_brand_template(name="保留模板", color_scheme="graphite", font_preset="stsong")
        assert saved.logo_object_key == "logos/keep-me"
        mocks["l4"].store.assert_not_awaited()


class TestValidationMatrix:
    """校验矩阵七格（494×5+242×1+成功×1）。"""

    async def test_invalid_color_scheme_key_494(self) -> None:
        """非法配色键 → 494（消息含合法键清单——调用方可理解性）。"""
        service, mocks = _make_service()
        with pytest.raises(BrandTemplateValidationError) as exc_info:
            await service.save_brand_template(name="x", color_scheme="neon-pink", font_preset="stsong")
        assert exc_info.value.code == "EXCEPTION_494"
        assert "corporate-blue" in exc_info.value.message
        mocks["l4"].store.assert_not_awaited()

    async def test_invalid_font_preset_key_494(self) -> None:
        """非法字体键 → 494。"""
        service, _ = _make_service()
        with pytest.raises(BrandTemplateValidationError) as exc_info:
            await service.save_brand_template(name="x", color_scheme="graphite", font_preset="comic-sans")
        assert exc_info.value.code == "EXCEPTION_494"

    async def test_empty_name_242_passthrough(self, tmp_path: Any) -> None:
        """空 name → 242（服务预检透传实体守卫——L4 零调用防孤儿对象）。"""
        logo = tmp_path / "logo.png"
        _make_logo_png(logo)
        service, mocks = _make_service()
        with pytest.raises(EntityValidationError) as exc_info:
            await service.save_brand_template(name="", color_scheme="graphite", font_preset="stsong", logo_path=str(logo))
        assert exc_info.value.code == "EXCEPTION_242"
        mocks["l4"].store.assert_not_awaited()

    async def test_logo_text_file_494(self, tmp_path: Any) -> None:
        """magic bytes 负例（文本文件）→ 494 且 L4 零调用。"""
        fake = tmp_path / "fake.txt"
        fake.write_bytes("plain text not an image".encode("utf-8"))
        service, mocks = _make_service()
        with pytest.raises(BrandTemplateValidationError) as exc_info:
            await service.save_brand_template(name="x", color_scheme="graphite", font_preset="stsong", logo_path=str(fake))
        assert exc_info.value.code == "EXCEPTION_494"
        assert "PNG" in exc_info.value.message or "JPEG" in exc_info.value.message
        mocks["l4"].store.assert_not_awaited()

    async def test_logo_oversize_494(self, tmp_path: Any) -> None:
        """大小上限负例（>2MB 带 PNG magic——过 magic 后撞上限）→ 494。"""
        big = tmp_path / "big.png"
        big.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * (_LOGO_MAX_BYTES + 1))
        service, _ = _make_service()
        with pytest.raises(BrandTemplateValidationError) as exc_info:
            await service.save_brand_template(name="x", color_scheme="graphite", font_preset="stsong", logo_path=str(big))
        assert exc_info.value.code == "EXCEPTION_494"
        assert "2" in exc_info.value.message

    async def test_logo_missing_path_494(self) -> None:
        """路径不存在 → 494（文件不可读伞形）。"""
        service, _ = _make_service()
        with pytest.raises(BrandTemplateValidationError) as exc_info:
            await service.save_brand_template(
                name="x", color_scheme="graphite", font_preset="stsong", logo_path="/nonexistent/logo.png"
            )
        assert exc_info.value.code == "EXCEPTION_494"

    async def test_jpeg_magic_accepted(self, tmp_path: Any) -> None:
        """JPEG 正例（Pillow 真生成——R1-F6 深校验后假体 magic+零填充形态必拒）。"""
        from PIL import Image

        jpeg = tmp_path / "logo.jpg"
        Image.new("RGB", (32, 32), color=(120, 30, 40)).save(jpeg, format="JPEG")
        service, mocks = _make_service()
        saved = await service.save_brand_template(
            name="JPEG 模板", color_scheme="graphite", font_preset="stsong", logo_path=str(jpeg)
        )
        assert saved.logo_object_key is not None
        assert mocks["l4"].store.call_args.kwargs["content_type"] == "image/jpeg"

    async def test_logo_empty_file_494(self, tmp_path: Any) -> None:
        """空文件（b""）→ 494（magic 族输入边界——head 空字节两判定均否）。"""
        empty = tmp_path / "empty.png"
        empty.write_bytes(b"")
        service, mocks = _make_service()
        with pytest.raises(BrandTemplateValidationError) as exc_info:
            await service.save_brand_template(name="x", color_scheme="graphite", font_preset="stsong", logo_path=str(empty))
        assert exc_info.value.code == "EXCEPTION_494"
        assert "PNG" in exc_info.value.message or "JPEG" in exc_info.value.message
        mocks["l4"].store.assert_not_awaited()

    async def test_logo_unreadable_chmod_000_494(self, tmp_path: Any) -> None:
        """不可读伞形（chmod 000 真文件——stat 可过而 open 抛 PermissionError）→ 494。

        真实语义链锚：isfile/getsize 走 os.stat（父目录 +x 即可）→ open 才触
        权限错误——「文件不可读」包装落在 open 位（R1-F3 主格）。
        """
        import os as os_module

        if os_module.geteuid() == 0:
            pytest.skip("root 忽略 mode 位——chmod 形态不可达")
        logo = tmp_path / "locked.png"
        _make_logo_png(logo)
        logo.chmod(0o000)
        service, _ = _make_service()
        with pytest.raises(BrandTemplateValidationError) as exc_info:
            await service.save_brand_template(name="x", color_scheme="graphite", font_preset="stsong", logo_path=str(logo))
        assert exc_info.value.code == "EXCEPTION_494"
        assert "不可读" in exc_info.value.message

    async def test_logo_getsize_permission_error_494(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        """getsize 权限异常（TOCTOU 窄道补充格——stat 成功后 getsize 抛）→ 494。"""
        logo = tmp_path / "logo.png"
        _make_logo_png(logo)

        def _raise_permission_error(path: str) -> int:
            raise PermissionError(13, "Permission denied", path)

        monkeypatch.setattr("os.path.getsize", _raise_permission_error)
        service, _ = _make_service()
        with pytest.raises(BrandTemplateValidationError) as exc_info:
            await service.save_brand_template(name="x", color_scheme="graphite", font_preset="stsong", logo_path=str(logo))
        assert exc_info.value.code == "EXCEPTION_494"
        assert "不可读" in exc_info.value.message

    async def test_logo_dimension_over_limit_494(self, tmp_path: Any) -> None:
        """像素维度超限（1×4001 平坦 PNG——KB 级字节过 2MB 关）→ 494（R1-F6）。"""
        from PIL import Image

        tall = tmp_path / "tall.png"
        Image.new("RGB", (1, 4001), color=(31, 78, 121)).save(tall, format="PNG")
        service, mocks = _make_service()
        with pytest.raises(BrandTemplateValidationError) as exc_info:
            await service.save_brand_template(name="x", color_scheme="graphite", font_preset="stsong", logo_path=str(tall))
        assert exc_info.value.code == "EXCEPTION_494"
        assert "像素" in exc_info.value.message
        mocks["l4"].store.assert_not_awaited()

    async def test_logo_png_magic_with_garbage_494(self, tmp_path: Any) -> None:
        """图像体无法解析（PNG magic 合法+垃圾体——过 magic 关后被 PIL 拒）→ 494。

        消息锚与 magic 格分立（「无法解析」vs「非 PNG/JPEG 格式」——浅校验
        绕过根除的判别锚）。
        """
        fake = tmp_path / "fake.png"
        fake.write_bytes(b"\x89PNG\r\n\x1a\n" + b"garbage-body" * 8)
        service, mocks = _make_service()
        with pytest.raises(BrandTemplateValidationError) as exc_info:
            await service.save_brand_template(name="x", color_scheme="graphite", font_preset="stsong", logo_path=str(fake))
        assert exc_info.value.code == "EXCEPTION_494"
        assert "无法解析" in exc_info.value.message
        mocks["l4"].store.assert_not_awaited()

    async def test_logo_dimension_boundary_4000_accepted(self, tmp_path: Any) -> None:
        """像素恰值边界（4000×4000 == 上限——`>` 严格不等判别锚）保存成功。"""
        from PIL import Image

        boundary = tmp_path / "boundary.png"
        Image.new("RGB", (4000, 4000), color=(31, 78, 121)).save(boundary, format="PNG")
        service, _ = _make_service()
        saved = await service.save_brand_template(
            name="边界模板", color_scheme="graphite", font_preset="stsong", logo_path=str(boundary)
        )
        assert saved.logo_object_key is not None


class TestOrphanLogoCompensation:
    """孤儿 logo 补偿（R1-F5——repo.save 失败对本次新写键 best-effort delete）。"""

    @staticmethod
    def _make_logo_path(tmp_path: Any) -> str:
        """构造合法 logo 文件路径（Pillow 真生成）。"""
        logo = tmp_path / "logo.png"
        _make_logo_png(logo)
        return str(logo)

    async def test_first_insert_save_failure_compensates_delete(self, tmp_path: Any) -> None:
        """首存+repo.save 协议外异常 → 495 包装+本次新写键补偿 delete（bucket/key kwargs 锚）。"""
        logo_path = self._make_logo_path(tmp_path)
        service, mocks = _make_service()
        mocks["repo"].save.side_effect = RuntimeError("PG connection lost")
        with pytest.raises(BrandTemplateStorageError) as exc_info:
            await service.save_brand_template(
                name="补偿模板", color_scheme="graphite", font_preset="stsong", logo_path=logo_path
            )
        assert exc_info.value.code == "EXCEPTION_495"
        mocks["l4"].delete.assert_awaited_once()
        delete_call = mocks["l4"].delete.call_args
        assert delete_call.kwargs["bucket_type"] == _BRAND_BUCKET_TYPE
        assert delete_call.kwargs["object_key"].startswith("logos/")

    async def test_first_insert_save_495_passthrough_compensates_delete(self, tmp_path: Any) -> None:
        """首存+repo.save 已抛 495 → 原异常透传不双重包装+补偿 delete 仍执行（双分支锚）。"""
        logo_path = self._make_logo_path(tmp_path)
        service, mocks = _make_service()
        injected = BrandTemplateStorageError(layer="l2", message="落库失败注入")
        mocks["repo"].save.side_effect = injected
        with pytest.raises(BrandTemplateStorageError) as exc_info:
            await service.save_brand_template(
                name="495 模板", color_scheme="graphite", font_preset="stsong", logo_path=logo_path
            )
        assert exc_info.value is injected, "已包装 495 应透传而非双重包装"
        mocks["l4"].delete.assert_awaited_once()

    async def test_revision_existing_key_no_compensation(self, tmp_path: Any) -> None:
        """修订既有键形态 save 失败 → 零补偿（删除即丢 PG 行仍引用的既有 logo）。"""
        logo_path = self._make_logo_path(tmp_path)
        template_id = uuid_module.uuid4()
        existing = _make_template(name="修订模板", template_id=template_id, logo_object_key=f"logos/{template_id}")
        service, mocks = _make_service(existing=existing)
        mocks["repo"].save.side_effect = RuntimeError("PG connection lost")
        with pytest.raises(BrandTemplateStorageError):
            await service.save_brand_template(
                name="修订模板", color_scheme="graphite", font_preset="stsong", logo_path=logo_path
            )
        mocks["l4"].delete.assert_not_awaited()

    async def test_revision_without_existing_logo_compensates(self, tmp_path: Any) -> None:
        """修订无既有 logo+新 logo_path+save 失败 → 补偿执行（朴素 `existing is None`
        条件的判别锚——正确条件是「本次新写键：object_key != existing_logo_key」）。"""
        logo_path = self._make_logo_path(tmp_path)
        existing = _make_template(name="无图修订模板", logo_object_key=None)
        service, mocks = _make_service(existing=existing)
        mocks["repo"].save.side_effect = RuntimeError("PG connection lost")
        with pytest.raises(BrandTemplateStorageError):
            await service.save_brand_template(
                name="无图修订模板", color_scheme="graphite", font_preset="stsong", logo_path=logo_path
            )
        mocks["l4"].delete.assert_awaited_once()
        assert mocks["l4"].delete.call_args.kwargs["object_key"] == f"logos/{existing.template_id}"

    async def test_compensation_delete_failure_does_not_mask(self, tmp_path: Any, caplog: pytest.LogCaptureFixture) -> None:
        """补偿 delete 自身失败 → 仅告警不掩盖原始异常（Saga 补偿形态锚）。"""
        logo_path = self._make_logo_path(tmp_path)
        service, mocks = _make_service()
        pg_down = RuntimeError("PG connection lost")
        mocks["repo"].save.side_effect = pg_down
        mocks["l4"].delete.side_effect = RuntimeError("minio unreachable")
        with pytest.raises(BrandTemplateStorageError) as exc_info:
            await service.save_brand_template(
                name="掩盖模板", color_scheme="graphite", font_preset="stsong", logo_path=logo_path
            )
        assert exc_info.value.cause is pg_down, "原始异常应保留（不被补偿失败顶替）"
        assert "补偿删除失败" in caplog.text


class TestGetRenderSpec:
    """get_render_spec 组装（预设映射+L4 logo 读回）。"""

    async def test_existing_template_assembles_spec(self) -> None:
        """模板存在 → 预设映射五色+font_name+logo bytes 组装 7 键 spec。"""
        template = _make_template(
            name="石墨套模板", color_scheme="graphite", font_preset="noto-sans-sc", logo_object_key="logos/t1"
        )
        service, _ = _make_service(existing=template)
        spec = await service.get_render_spec("石墨套模板")
        assert isinstance(spec, BrandRenderSpec)
        assert spec.font_name == "NotoSansSC"
        assert spec.title_color == "#37474F"
        assert spec.header_bg_color == "#ECEFF1"
        assert spec.grid_color == "#B0BEC5"
        assert spec.callout_bg_color == "#F5F7F8"
        assert spec.callout_text_color == "#455A64"
        assert spec.logo == b"\x89PNG\r\n\x1a\nfake-logo-bytes"

    async def test_missing_template_494_with_name(self) -> None:
        """模板不存在 → 494（message 含模板名——404 等价语义）。"""
        service, _ = _make_service()
        with pytest.raises(BrandTemplateValidationError) as exc_info:
            await service.get_render_spec("ghost-template")
        assert exc_info.value.code == "EXCEPTION_494"
        assert "ghost-template" in exc_info.value.message

    async def test_no_logo_template_spec_logo_none_and_zero_retrieve(self) -> None:
        """logo 缺席模板 → spec.logo=None+L4 读回零调用。"""
        template = _make_template(name="无 Logo", color_scheme="burgundy", font_preset="stsong")
        service, mocks = _make_service(existing=template)
        spec = await service.get_render_spec("无 Logo")
        assert spec.logo is None
        assert spec.font_name == "STSong-Light"
        mocks["l4"].retrieve.assert_not_called()

    async def test_l4_retrieve_failure_495(self) -> None:
        """L4 logo 读回异常 → 495 包装（layer="l4"）。"""
        template = _make_template(logo_object_key="logos/broken")
        service, _ = _make_service(existing=template, retrieve_side_effect=RuntimeError("MinIO 不可达"))
        with pytest.raises(BrandTemplateStorageError) as exc_info:
            await service.get_render_spec("test")
        assert exc_info.value.code == "EXCEPTION_495"
        assert exc_info.value.layer == "l4"

    async def test_dirty_preset_key_494(self) -> None:
        """脏预设键（直写行绕过服务校验）→ 494（KeyError 防御包装——校验
        失败族而非 500）。"""
        template = _make_template(name="脏行", color_scheme="neon-pink-dirty")
        service, _ = _make_service(existing=template)
        with pytest.raises(BrandTemplateValidationError) as exc_info:
            await service.get_render_spec("脏行")
        assert exc_info.value.code == "EXCEPTION_494"


class TestListTemplates:
    """list 透传（repo list → tuple 化）。"""

    async def test_list_returns_tuple(self) -> None:
        """list 透传 tuple 化（Port 返回契约 tuple[BrandTemplate, ...]）。"""
        rows = [_make_template(name="A"), _make_template(name="B")]
        service, _ = _make_service(repo_rows=rows)
        listed = await service.list_brand_templates()
        assert isinstance(listed, tuple)
        assert len(listed) == 2


class TestStorageErrorWrapping:
    """存储异常包装防御（L4 store 失败/repo.save 协议外异常——495 包装路径）。"""

    async def test_l4_store_failure_wraps_495(self, tmp_path: Any) -> None:
        """L4 store 异常 → 495 包装（layer="l4"——logo 上传失败面）。"""
        logo = tmp_path / "logo.png"
        _make_logo_png(logo)
        service, _ = _make_service(store_side_effect=RuntimeError("MinIO put 失败"))
        with pytest.raises(BrandTemplateStorageError) as exc_info:
            await service.save_brand_template(name="x", color_scheme="graphite", font_preset="stsong", logo_path=str(logo))
        assert exc_info.value.code == "EXCEPTION_495"
        assert exc_info.value.layer == "l4"

    async def test_repo_save_unexpected_wraps_495(self) -> None:
        """repo.save 协议外异常 → 495 包装（layer="l2"——防御义务归服务的包装面）。"""
        from unittest.mock import AsyncMock

        service, mocks = _make_service()
        mocks["repo"].save = AsyncMock(side_effect=RuntimeError("连接意外断开"))
        with pytest.raises(BrandTemplateStorageError) as exc_info:
            await service.save_brand_template(name="x", color_scheme="graphite", font_preset="stsong")
        assert exc_info.value.code == "EXCEPTION_495"
        assert exc_info.value.layer == "l2"

    async def test_repo_save_495_passthrough(self) -> None:
        """repo.save 已抛 495 → 原样透传（不双重包装——re-raise 分支）。"""
        from unittest.mock import AsyncMock

        service, mocks = _make_service()
        mocks["repo"].save = AsyncMock(side_effect=BrandTemplateStorageError(layer="l2", message="行落库失败"))
        with pytest.raises(BrandTemplateStorageError) as exc_info:
            await service.save_brand_template(name="x", color_scheme="graphite", font_preset="stsong")
        assert exc_info.value.message == "行落库失败", "495 应原样透传不双重包装"
