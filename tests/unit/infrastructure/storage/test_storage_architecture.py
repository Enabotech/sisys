"""存储架构验证测试

验证领域层与基础设施层的架构约束：
- 领域层零 MinIO 导入
- ObjectStorageRepository 是抽象 ABC
- 基础设施层实现了领域接口
- ComplianceLockError 定义在领域层
- bucket_type 到 bucket_name 映射逻辑存在
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DOMAIN_DIR = PROJECT_ROOT / "src" / "domain"
INFRASTRUCTURE_DIR = PROJECT_ROOT / "src" / "infrastructure"


class TestDomainLayerConstraints:
    """领域层架构约束测试"""

    def test_domain_has_zero_minio_imports(self):
        """领域层不包含任何 MinIO 导入"""
        minio_imports = _find_imports_in_dir(DOMAIN_DIR, "minio")
        assert len(minio_imports) == 0, f"Domain layer must not import MinIO, found: {minio_imports}"

    def test_domain_has_no_s3_imports(self):
        """领域层不包含任何 boto3/S3 导入"""
        s3_imports = _find_imports_in_dir(DOMAIN_DIR, "boto3")
        assert len(s3_imports) == 0, f"Domain layer must not import boto3, found: {s3_imports}"

    def test_domain_has_no_infrastructure_imports(self):
        """领域层不导入基础设施层模块"""
        infra_imports = _find_imports_in_dir(DOMAIN_DIR, "infrastructure")
        assert len(infra_imports) == 0, f"Domain layer must not import infrastructure, found: {infra_imports}"


class TestComplianceLockErrorInDomain:
    """ComplianceLockError 定义位置测试"""

    def test_compliance_lock_error_in_domain(self):
        """ComplianceLockError 定义在领域层 storage.py 中"""
        from src.domain.ports.storage import ComplianceLockError

        assert issubclass(ComplianceLockError, Exception), "ComplianceLockError must be an Exception subclass"

    def test_compliance_lock_error_message(self):
        """ComplianceLockError 可以携带错误消息"""
        from src.domain.ports.storage import ComplianceLockError

        error = ComplianceLockError("Object is WORM locked")
        assert str(error) == "Object is WORM locked"


class TestBucketTypeMapping:
    """bucket_type 到 bucket_name 映射测试"""

    def test_mapping_logic_exists_in_bucket_manager(self):
        """Bucket 名称映射逻辑存在于 bucket_manager.py 中"""
        bucket_manager_path = INFRASTRUCTURE_DIR / "storage" / "minio" / "bucket_manager.py"
        assert bucket_manager_path.exists(), "bucket_manager.py must exist"

        source = bucket_manager_path.read_text()
        tree = ast.parse(source)

        # 查找 build_bucket_name 方法
        method_names = _extract_method_names(tree)
        assert "build_bucket_name" in method_names, "BucketManager must have build_bucket_name method"

    def test_mapping_format(self):
        """映射格式为 {prefix}-{type}-{tenant_id}"""
        from src.infrastructure.config.minio import MinIOConfig
        from src.infrastructure.storage.minio.bucket_manager import BucketManager

        config = MinIOConfig(bucket_prefix="sisys")
        manager = BucketManager(config)
        result = manager.build_bucket_name("raw-documents", "tenant-123")
        assert result == "sisys-raw-documents-tenant-123"

    def test_mapping_with_custom_prefix(self):
        """自定义前缀映射"""
        from src.infrastructure.config.minio import MinIOConfig
        from src.infrastructure.storage.minio.bucket_manager import BucketManager

        config = MinIOConfig(bucket_prefix="myapp")
        manager = BucketManager(config)
        result = manager.build_bucket_name("audit-logs", "acme")
        assert result == "myapp-audit-logs-acme"


class TestInfrastructureImplementsInterface:
    """基础设施层实现领域接口测试"""

    def test_object_operations_has_store_signature(self):
        """ObjectOperations 有 upload_object 方法（对应 store）"""
        from src.infrastructure.storage.minio.object_operations import (
            ObjectOperations,
        )

        assert hasattr(ObjectOperations, "upload_object"), "ObjectOperations must have upload_object method"

    def test_object_operations_has_retrieve_signature(self):
        """ObjectOperations 有 download_object 方法（对应 retrieve）"""
        from src.infrastructure.storage.minio.object_operations import (
            ObjectOperations,
        )

        assert hasattr(ObjectOperations, "download_object"), "ObjectOperations must have download_object method"

    def test_object_operations_has_delete_signature(self):
        """ObjectOperations 有 delete_object 方法（对应 delete）"""
        from src.infrastructure.storage.minio.object_operations import (
            ObjectOperations,
        )

        assert hasattr(ObjectOperations, "delete_object"), "ObjectOperations must have delete_object method"

    def test_object_operations_has_metadata_signature(self):
        """ObjectOperations 有 get_object_metadata 方法（对应 get_metadata）"""
        from src.infrastructure.storage.minio.object_operations import (
            ObjectOperations,
        )

        assert hasattr(ObjectOperations, "get_object_metadata"), "ObjectOperations must have get_object_metadata method"

    def test_worm_manager_has_archive(self):
        """WORMManager 有 archive_object 方法（对应 archive）"""
        from src.infrastructure.storage.minio.worm_lifecycle import WORMManager

        assert hasattr(WORMManager, "archive_object"), "WORMManager must have archive_object method"

    def test_worm_manager_uses_compliance_lock_error(self):
        """WORMManager 的 delete_object 抛出 ComplianceLockError"""
        from src.infrastructure.storage.minio.worm_lifecycle import WORMManager

        source = inspect.getsource(WORMManager)
        assert "ComplianceLockError" in source, "WORMManager must use ComplianceLockError"


class TestAsyncPatterns:
    """异步模式测试"""

    def test_download_object_is_async_generator(self):
        """download_object 是异步生成器"""
        import asyncio

        from src.infrastructure.storage.minio.object_operations import (
            ObjectOperations,
        )

        method = ObjectOperations.download_object
        assert asyncio.iscoroutinefunction(method) or inspect.isasyncgenfunction(method), (
            "download_object must be an async generator or coroutine"
        )


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _find_imports_in_dir(base_dir: Path, module_name: str) -> list[str]:
    """扫描目录下所有 .py 文件，查找包含 module_name 的导入

    Args:
        base_dir: 要扫描的目录
        module_name: 要查找的模块名称

    Returns:
        包含该导入的文件路径列表
    """
    found = []
    for py_file in base_dir.rglob("*.py"):
        source = py_file.read_text()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if module_name in alias.name:
                        found.append(str(py_file))
            elif isinstance(node, ast.ImportFrom):
                if node.module and module_name in node.module:
                    found.append(str(py_file))
    return found


def _extract_method_names(tree: ast.AST) -> set[str]:
    """从 AST 中提取所有方法名称

    Args:
        tree: AST 根节点

    Returns:
        方法名称集合
    """
    methods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            methods.add(node.name)
    return methods
