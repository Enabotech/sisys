# 自动诊断与修复工具指南

本文档介绍 Sisyphus 系统的自动诊断与修复功能。

## 目录

- [1. 概述](#1-概述)
- [2. 诊断架构](#2-诊断架构)
- [3. 诊断模块](#3-诊断模块)
- [4. 修复策略](#4-修复策略)
- [5. 命令行使用](#5-命令行使用)
- [6. API 接口](#6-api-接口)
- [7. 自定义诊断规则](#7-自定义诊断规则)
- [8. 日志与报告](#8-日志与报告)

---

## 1. 概述

自动诊断与修复工具提供：

- 系统健康检查
- 配置问题检测
- 依赖问题修复
- 服务状态监控
- 一键修复功能
- 详细诊断报告

### 核心功能

```
┌─────────────────────────────────────────────────────────┐
│                   诊断与修复系统                          │
├─────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ 系统检查  │  │ 配置检查  │  │ 服务检查  │  │ 网络检查  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│                         │                                 │
│                         ▼                                 │
│  ┌──────────────────────────────────────────────────┐   │
│  │              问题识别与分类                        │   │
│  └──────────────────────────────────────────────────┘   │
│                         │                                 │
│                         ▼                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ 自动修复  │  │ 建议修复  │  │ 手动修复  │  │ 无法修复  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 诊断架构

### 2.1 核心组件

```python
# app/diagnosis/__init__.py
from .engine import DiagnosisEngine
from .checks import CheckRegistry
from .fixers import FixerRegistry
from .reporter import ReportGenerator

__all__ = ['DiagnosisEngine', 'CheckRegistry', 'FixerRegistry', 'ReportGenerator']
```

```python
# app/diagnosis/engine.py
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class Status(Enum):
    PASSED = "passed"
    FAILED = "failed"
    FIXED = "fixed"
    SKIPPED = "skipped"

@dataclass
class CheckResult:
    """检查结果"""
    check_id: str
    name: str
    severity: Severity
    status: Status
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    fix_available: bool = False
    fix_description: str = ""

@dataclass
class DiagnosisReport:
    """诊断报告"""
    timestamp: str
    total_checks: int
    passed: int
    failed: int
    warnings: int
    critical: int
    results: List[CheckResult]
    summary: str

class DiagnosisEngine:
    """诊断引擎"""

    def __init__(self):
        self.check_registry = CheckRegistry()
        self.fixer_registry = FixerRegistry()
        self.results: List[CheckResult] = []

    async def run_all_checks(self) -> DiagnosisReport:
        """运行所有检查"""
        self.results = []

        checks = self.check_registry.get_all_checks()

        for check in checks:
            try:
                result = await check.run()
                self.results.append(result)

                # 如果检查失败且有可用修复器，尝试自动修复
                if result.status == Status.FAILED and result.fix_available:
                    await self._try_auto_fix(check.check_id)

            except Exception as e:
                self.results.append(CheckResult(
                    check_id=check.check_id,
                    name=check.name,
                    severity=Severity.ERROR,
                    status=Status.FAILED,
                    message=f"检查执行失败：{str(e)}"
                ))

        return self._generate_report()

    async def run_specific_checks(self, check_ids: List[str]) -> DiagnosisReport:
        """运行指定检查"""
        self.results = []

        for check_id in check_ids:
            check = self.check_registry.get_check(check_id)
            if check:
                result = await check.run()
                self.results.append(result)

        return self._generate_report()

    async def _try_auto_fix(self, check_id: str):
        """尝试自动修复"""
        fixer = self.fixer_registry.get_fixer(check_id)
        if fixer:
            try:
                await fixer.run()
                # 更新结果状态
                for result in self.results:
                    if result.check_id == check_id:
                        result.status = Status.FIXED
                        break
            except Exception as e:
                # 修复失败，保持 FAILED 状态
                pass

    def _generate_report(self) -> DiagnosisReport:
        """生成报告"""
        passed = sum(1 for r in self.results if r.status == Status.PASSED)
        failed = sum(1 for r in self.results if r.status == Status.FAILED)
        fixed = sum(1 for r in self.results if r.status == Status.FIXED)
        warnings = sum(1 for r in self.results if r.severity == Severity.WARNING)
        critical = sum(1 for r in self.results if r.severity == Severity.CRITICAL)

        summary = self._generate_summary(passed, failed, fixed, critical)

        return DiagnosisReport(
            timestamp=datetime.now().isoformat(),
            total_checks=len(self.results),
            passed=passed + fixed,
            failed=failed,
            warnings=warnings,
            critical=critical,
            results=self.results,
            summary=summary
        )

    def _generate_summary(self, passed: int, failed: int, fixed: int, critical: int) -> str:
        """生成摘要"""
        if critical > 0:
            return f"发现 {critical} 个严重问题，需要立即处理"
        elif failed > 0:
            return f"发现 {failed} 个问题，其中 {fixed} 个已自动修复"
        elif passed == len(self.results):
            return "所有检查通过，系统运行正常"
        else:
            return "系统存在警告，但不影响正常运行"
```

### 2.2 检查注册表

```python
# app/diagnosis/checks.py
from abc import ABC, abstractmethod
from typing import List, Type

class BaseCheck(ABC):
    """检查基类"""

    check_id: str = ""
    name: str = ""
    description: str = ""
    severity: Severity = Severity.INFO

    @abstractmethod
    async def run(self) -> CheckResult:
        """执行检查"""
        pass

class CheckRegistry:
    """检查注册表"""

    _checks: Dict[str, BaseCheck] = {}

    @classmethod
    def register(cls, check_class: Type[BaseCheck]):
        """注册检查"""
        instance = check_class()
        cls._checks[instance.check_id] = instance
        return check_class

    @classmethod
    def get_check(cls, check_id: str) -> Optional[BaseCheck]:
        """获取检查"""
        return cls._checks.get(check_id)

    @classmethod
    def get_all_checks(cls) -> List[BaseCheck]:
        """获取所有检查"""
        return list(cls._checks.values())

    @classmethod
    def get_checks_by_category(cls, category: str) -> List[BaseCheck]:
        """按类别获取检查"""
        return [c for c in cls._checks.values() if c.check_id.startswith(category)]
```

---

## 3. 诊断模块

### 3.1 系统环境检查

```python
# app/diagnosis/checks/system.py
import os
import shutil
import platform
from . import BaseCheck, CheckRegistry, CheckResult, Severity

@CheckRegistry.register
class PythonVersionCheck(BaseCheck):
    """Python 版本检查"""

    check_id = "system.python_version"
    name = "Python 版本检查"
    description = "检查 Python 版本是否满足要求"
    severity = Severity.CRITICAL

    async def run(self) -> CheckResult:
        import sys

        current = sys.version_info
        required = (3, 10)

        if current[:2] >= required:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.PASSED,
                message=f"Python {current.major}.{current.minor}.{current.micro} 满足要求"
            )
        else:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.FAILED,
                message=f"Python {current.major}.{current.minor} 版本过低，需要 3.10+",
                fix_available=True,
                fix_description="使用 pyenv 或系统包管理器安装 Python 3.10+"
            )

@CheckRegistry.register
class DiskSpaceCheck(BaseCheck):
    """磁盘空间检查"""

    check_id = "system.disk_space"
    name = "磁盘空间检查"
    description = "检查可用磁盘空间"
    severity = Severity.WARNING

    async def run(self) -> CheckResult:
        import psutil

        usage = psutil.disk_usage('/')
        free_gb = usage.free / (1024 ** 3)

        if free_gb >= 10:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.PASSED,
                message=f"可用磁盘空间：{free_gb:.1f} GB"
            )
        elif free_gb >= 5:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.PASSED,
                message=f"可用磁盘空间：{free_gb:.1f} GB（建议清理）",
                fix_available=True,
                fix_description="运行 'docker system prune' 或清理临时文件"
            )
        else:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=Severity.ERROR,
                status=Status.FAILED,
                message=f"可用磁盘空间不足：{free_gb:.1f} GB（至少需要 5GB）",
                fix_available=True,
                fix_description="清理磁盘空间：docker system prune -a"
            )

@CheckRegistry.register
class DockerCheck(BaseCheck):
    """Docker 环境检查"""

    check_id = "system.docker"
    name = "Docker 环境检查"
    description = "检查 Docker 是否安装并运行"
    severity = Severity.CRITICAL

    async def run(self) -> CheckResult:
        import subprocess

        # 检查 Docker 是否安装
        if not shutil.which('docker'):
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.FAILED,
                message="Docker 未安装",
                fix_available=True,
                fix_description="安装 Docker: https://docs.docker.com/get-docker/"
            )

        # 检查 Docker 是否运行
        try:
            result = subprocess.run(
                ['docker', 'info'],
                capture_output=True,
                timeout=10
            )
            if result.returncode != 0:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    severity=self.severity,
                    status=Status.FAILED,
                    message="Docker 未运行或无权限访问",
                    fix_available=True,
                    fix_description="启动 Docker 服务或将用户加入 docker 组"
                )
        except Exception as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.FAILED,
                message=f"Docker 检查失败：{str(e)}",
                fix_available=True,
                fix_description="检查 Docker 服务状态：systemctl status docker"
            )

        return CheckResult(
            check_id=self.check_id,
            name=self.name,
            severity=self.severity,
            status=Status.PASSED,
            message="Docker 已安装并运行"
        )

@CheckRegistry.register
class KubectlCheck(BaseCheck):
    """kubectl 工具检查"""

    check_id = "system.kubectl"
    name = "kubectl 工具检查"
    description = "检查 kubectl 是否安装"
    severity = Severity.WARNING

    async def run(self) -> CheckResult:
        import subprocess

        if not shutil.which('kubectl'):
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.FAILED,
                message="kubectl 未安装",
                fix_available=True,
                fix_description="安装 kubectl: https://kubernetes.io/docs/tasks/tools/"
            )

        try:
            result = subprocess.run(
                ['kubectl', 'version', '--client', '-o', 'json'],
                capture_output=True,
                timeout=10
            )
            import json
            version_info = json.loads(result.stdout)
            version = version_info.get('clientVersion', {}).get('gitVersion', 'unknown')

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.PASSED,
                message=f"kubectl 版本：{version}"
            )
        except Exception as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.FAILED,
                message=f"kubectl 执行失败：{str(e)}"
            )
```

### 3.2 配置检查

```python
# app/diagnosis/checks/config.py
import os
import yaml
from pathlib import Path
from . import BaseCheck, CheckRegistry, CheckResult, Severity

@CheckRegistry.register
class ConfigFileCheck(BaseCheck):
    """配置文件检查"""

    check_id = "config.files"
    name = "配置文件检查"
    description = "检查配置文件是否存在且有效"
    severity = Severity.CRITICAL

    async def run(self) -> CheckResult:
        from app.config import get_config_path

        config_path = get_config_path()

        if not config_path.exists():
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.FAILED,
                message=f"配置文件不存在：{config_path}",
                fix_available=True,
                fix_description="运行 'sisys config init' 创建默认配置"
            )

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)

            # 验证配置结构
            required_keys = ['database', 'server', 'logging']
            missing = [k for k in required_keys if k not in config]

            if missing:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    severity=self.severity,
                    status=Status.FAILED,
                    message=f"配置缺少必需字段：{missing}",
                    fix_available=True,
                    fix_description="更新配置文件添加缺失字段"
                )

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.PASSED,
                message="配置文件有效"
            )
        except yaml.YAMLError as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.FAILED,
                message=f"配置文件格式错误：{str(e)}",
                fix_available=True,
                fix_description="修复配置文件 YAML 语法"
            )

@CheckRegistry.register
class SecretsCheck(BaseCheck):
    """密钥配置检查"""

    check_id = "config.secrets"
    name = "密钥配置检查"
    description = "检查敏感配置是否已设置"
    severity = Severity.CRITICAL

    async def run(self) -> CheckResult:
        from app.config import get_config

        config = get_config()

        missing_secrets = []

        # 检查数据库密码
        if not config.database.get('password'):
            missing_secrets.append('database.password')

        # 检查 API 密钥
        if not config.server.get('api_key'):
            missing_secrets.append('server.api_key')

        if missing_secrets:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.FAILED,
                message=f"缺少必需的配置：{missing_secrets}",
                fix_available=True,
                fix_description="运行 'sisys config wizard' 配置密钥"
            )

        return CheckResult(
            check_id=self.check_id,
            name=self.name,
            severity=self.severity,
            status=Status.PASSED,
            message="所有必需配置已设置"
        )
```

### 3.3 服务健康检查

```python
# app/diagnosis/checks/services.py
import asyncio
import aiohttp
from . import BaseCheck, CheckRegistry, CheckResult, Severity, Status

@CheckRegistry.register
class APIHealthCheck(BaseCheck):
    """API 健康检查"""

    check_id = "services.api_health"
    name = "API 健康检查"
    description = "检查 API 服务是否响应"
    severity = Severity.CRITICAL

    async def run(self) -> CheckResult:
        from app.config import get_config

        config = get_config()
        base_url = f"http://{config.server.host}:{config.server.port}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url}/health", timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return CheckResult(
                            check_id=self.check_id,
                            name=self.name,
                            severity=self.severity,
                            status=Status.PASSED,
                            message=f"API 健康：{data.get('status', 'unknown')}"
                        )
        except asyncio.TimeoutError:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.FAILED,
                message="API 响应超时",
                fix_available=True,
                fix_description="检查 API 服务状态：sisys service status"
            )
        except Exception as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.FAILED,
                message=f"API 连接失败：{str(e)}",
                fix_available=True,
                fix_description="启动 API 服务：sisys service start"
            )

@CheckRegistry.register
class DatabaseCheck(BaseCheck):
    """数据库连接检查"""

    check_id = "services.database"
    name = "数据库连接检查"
    description = "检查数据库连接是否正常"
    severity = Severity.CRITICAL

    async def run(self) -> CheckResult:
        from app.config import get_config
        from app.db import get_connection

        try:
            conn = await get_connection()
            await conn.execute('SELECT 1')
            await conn.close()

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.PASSED,
                message="数据库连接正常"
            )
        except Exception as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.FAILED,
                message=f"数据库连接失败：{str(e)}",
                fix_available=True,
                fix_description="检查数据库服务并运行 'sisys db migrate'"
            )

@CheckRegistry.register
class HarborCheck(BaseCheck):
    """Harbor 连接检查"""

    check_id = "services.harbor"
    name = "Harbor 连接检查"
    description = "检查 Harbor 镜像仓库连接"
    severity = Severity.WARNING

    async def run(self) -> CheckResult:
        from app.config import get_config

        config = get_config()
        harbor_url = config.harbor.url

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{harbor_url}/api/v2.0/systeminfo", timeout=10) as resp:
                    if resp.status == 200:
                        return CheckResult(
                            check_id=self.check_id,
                            name=self.name,
                            severity=self.severity,
                            status=Status.PASSED,
                            message="Harbor 连接正常"
                        )
        except Exception as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.FAILED,
                message=f"Harbor 连接失败：{str(e)}",
                fix_available=False
            )
```

### 3.4 网络检查

```python
# app/diagnosis/checks/network.py
import socket
import asyncio
from . import BaseCheck, CheckRegistry, CheckResult, Severity, Status

@CheckRegistry.register
class DNSCheck(BaseCheck):
    """DNS 解析检查"""

    check_id = "network.dns"
    name = "DNS 解析检查"
    description = "检查 DNS 解析是否正常"
    severity = Severity.WARNING

    async def run(self) -> CheckResult:
        test_domains = ['google.com', 'github.com', 'docker.io']
        failed = []

        for domain in test_domains:
            try:
                socket.gethostbyname(domain)
            except socket.gaierror:
                failed.append(domain)

        if failed:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=Severity.ERROR,
                status=Status.FAILED,
                message=f"DNS 解析失败：{failed}",
                fix_available=True,
                fix_description="检查 /etc/resolv.conf 或联系网络管理员"
            )

        return CheckResult(
            check_id=self.check_id,
            name=self.name,
            severity=self.severity,
            status=Status.PASSED,
            message="DNS 解析正常"
        )

@CheckRegistry.register
class PortAvailabilityCheck(BaseCheck):
    """端口可用性检查"""

    check_id = "network.ports"
    name = "端口可用性检查"
    description = "检查必需端口是否可用"
    severity = Severity.ERROR

    async def run(self) -> CheckResult:
        from app.config import get_config

        config = get_config()
        required_ports = [
            config.server.port,
            config.database.port,
        ]

        unavailable = []
        for port in required_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()

            if result != 0:
                unavailable.append(port)

        if unavailable:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                severity=self.severity,
                status=Status.FAILED,
                message=f"端口不可用：{unavailable}",
                fix_available=True,
                fix_description="检查服务是否运行或更改配置端口"
            )

        return CheckResult(
            check_id=self.check_id,
            name=self.name,
            severity=self.severity,
            status=Status.PASSED,
            message="所有必需端口可用"
        )
```

---

## 4. 修复策略

### 4.1 修复器基类

```python
# app/diagnosis/fixers.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class FixResult:
    """修复结果"""
    success: bool
    message: str
    details: Dict[str, Any] = None

class BaseFixer(ABC):
    """修复器基类"""

    fixer_id: str = ""
    name: str = ""
    description: str = ""
    requires_restart: bool = False

    @abstractmethod
    async def run(self) -> FixResult:
        """执行修复"""
        pass

    @abstractmethod
    async def dry_run(self) -> FixResult:
        """模拟修复（不实际执行）"""
        pass

class FixerRegistry:
    """修复器注册表"""

    _fixers: Dict[str, BaseFixer] = {}

    @classmethod
    def register(cls, fixer_class):
        instance = fixer_class()
        cls._fixers[instance.fixer_id] = instance
        return fixer_class

    @classmethod
    def get_fixer(cls, check_id: str) -> Optional[BaseFixer]:
        return cls._fixers.get(check_id)
```

### 4.2 自动修复实现

```python
# app/diagnosis/fixers/auto.py
import subprocess
import shutil
from pathlib import Path
from . import BaseFixer, FixerRegistry, FixResult

@FixerRegistry.register
class DockerPruneFixer(BaseFixer):
    """Docker 清理修复器"""

    fixer_id = "system.disk_space"
    name = "Docker 清理"
    description = "清理未使用的 Docker 资源"
    requires_restart = False

    async def run(self) -> FixResult:
        try:
            # 清理未使用的容器、网络、镜像
            result = subprocess.run(
                ['docker', 'system', 'prune', '-a', '-f'],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                return FixResult(
                    success=True,
                    message="Docker 清理完成",
                    details={'output': result.stdout}
                )
            else:
                return FixResult(
                    success=False,
                    message=f"Docker 清理失败：{result.stderr}"
                )
        except subprocess.TimeoutExpired:
            return FixResult(
                success=False,
                message="Docker 清理超时"
            )
        except Exception as e:
            return FixResult(
                success=False,
                message=f"Docker 清理错误：{str(e)}"
            )

    async def dry_run(self) -> FixResult:
        # 计算可清理的空间
        result = subprocess.run(
            ['docker', 'system', 'df'],
            capture_output=True,
            text=True
        )

        return FixResult(
            success=True,
            message="将清理以下 Docker 资源",
            details={'output': result.stdout}
        )

@FixerRegistry.register
class ConfigInitFixer(BaseFixer):
    """配置初始化修复器"""

    fixer_id = "config.files"
    name = "配置初始化"
    description = "创建默认配置文件"
    requires_restart = True

    async def run(self) -> FixResult:
        from app.config import get_config_path, DEFAULT_CONFIG

        config_path = get_config_path()

        try:
            # 创建配置目录
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入默认配置
            import yaml
            with open(config_path, 'w') as f:
                yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)

            return FixResult(
                success=True,
                message=f"配置文件已创建：{config_path}",
                details={'path': str(config_path)}
            )
        except Exception as e:
            return FixResult(
                success=False,
                message=f"创建配置失败：{str(e)}"
            )

    async def dry_run(self) -> FixResult:
        from app.config import get_config_path

        config_path = get_config_path()

        return FixResult(
            success=True,
            message=f"将在 {config_path} 创建配置文件",
            details={'path': str(config_path)}
        )

@FixerRegistry.register
class ServiceRestartFixer(BaseFixer):
    """服务重启修复器"""

    fixer_id = "services.api_health"
    name = "服务重启"
    description = "重启 API 服务"
    requires_restart = False

    async def run(self) -> FixResult:
        try:
            # 停止服务
            subprocess.run(['sisys', 'service', 'stop'], timeout=30)

            # 等待
            await asyncio.sleep(2)

            # 启动服务
            subprocess.run(['sisys', 'service', 'start'], timeout=30)

            # 等待服务启动
            await asyncio.sleep(5)

            return FixResult(
                success=True,
                message="服务已重启"
            )
        except Exception as e:
            return FixResult(
                success=False,
                message=f"服务重启失败：{str(e)}"
            )

    async def dry_run(self) -> FixResult:
        return FixResult(
            success=True,
            message="将重启 API 服务"
        )
```

---

## 5. 命令行使用

### 5.1 诊断命令

```python
# app/cli/diagnosis.py
import click
import asyncio
import json
from typing import Optional

@click.group()
def diagnosis():
    """诊断与修复工具"""
    pass

@diagnosis.command()
@click.option('--check', '-c', multiple=True, help='运行指定检查')
@click.option('--category', help='运行指定类别的检查')
@click.option('--output', '-o', type=click.Choice(['text', 'json', 'html']), default='text')
@click.option('--output-file', help='输出到文件')
@click.pass_context
def check(ctx, check, category, output, output_file):
    """运行诊断检查"""
    from app.diagnosis import DiagnosisEngine

    async def run():
        engine = DiagnosisEngine()

        if check:
            report = await engine.run_specific_checks(list(check))
        elif category:
            checks = engine.check_registry.get_checks_by_category(category)
            report = await engine.run_specific_checks([c.check_id for c in checks])
        else:
            report = await engine.run_all_checks()

        # 输出报告
        if output == 'json':
            content = json.dumps(report.__dict__, indent=2, default=str)
        elif output == 'html':
            from app.diagnosis.reporter import ReportGenerator
            content = ReportGenerator.generate_html(report)
        else:
            content = ReportGenerator.generate_text(report)

        if output_file:
            with open(output_file, 'w') as f:
                f.write(content)
            click.echo(f"报告已保存到：{output_file}")
        else:
            click.echo(content)

    asyncio.run(run())

@diagnosis.command()
@click.argument('check_id')
@click.option('--dry-run', is_flag=True, help='模拟修复')
@click.option('--auto', is_flag=True, help='自动确认')
def fix(check_id, dry_run, auto):
    """运行修复"""
    from app.diagnosis import FixerRegistry

    async def run():
        fixer = FixerRegistry.get_fixer(check_id)

        if not fixer:
            click.echo(f"未找到修复器：{check_id}")
            return

        click.echo(f"修复器：{fixer.name}")
        click.echo(f"描述：{fixer.description}")

        if dry_run:
            result = await fixer.dry_run()
        else:
            if not auto:
                if not click.confirm('确认执行修复？'):
                    return

            result = await fixer.run()

        status = "✓" if result.success else "✗"
        click.echo(f"{status} {result.message}")

        if result.details:
            click.echo(f"详情：{result.details}")

    asyncio.run(run())

@diagnosis.command()
@click.option('--all', is_flag=True, help='修复所有可修复的问题')
@click.pass_context
def auto_fix(ctx, all):
    """自动修复所有可修复的问题"""
    from app.diagnosis import DiagnosisEngine

    async def run():
        engine = DiagnosisEngine()
        report = await engine.run_all_checks()

        fixed = 0
        failed = 0

        for result in report.results:
            if result.status == Status.FAILED and result.fix_available:
                if all or click.confirm(f"修复：{result.name}?"):
                    fix_result = await engine._try_auto_fix(result.check_id)
                    if fix_result.success:
                        fixed += 1
                    else:
                        failed += 1

        click.echo(f"\n修复完成：{fixed} 成功，{failed} 失败")

    asyncio.run(run())

@diagnosis.command()
def list_checks():
    """列出所有可用检查"""
    from app.diagnosis import CheckRegistry

    checks = CheckRegistry.get_all_checks()

    click.echo(f"{'ID':<30} {'名称':<25} {'严重性':<10}")
    click.echo("-" * 65)

    for check in checks:
        click.echo(f"{check.check_id:<30} {check.name:<25} {check.severity.value:<10}")

@diagnosis.command()
def list_fixers():
    """列出所有可用修复器"""
    from app.diagnosis import FixerRegistry

    fixers = list(FixerRegistry._fixers.values())

    click.echo(f"{'ID':<30} {'名称':<25} {'需重启':<10}")
    click.echo("-" * 65)

    for fixer in fixers:
        restart = "是" if fixer.requires_restart else "否"
        click.echo(f"{fixer.fixer_id:<30} {fixer.name:<25} {restart:<10}")
```

### 5.2 使用示例

```bash
# 运行所有检查
sisys diagnosis check

# 运行指定检查
sisys diagnosis check -c system.docker -c system.python_version

# 运行指定类别检查
sisys diagnosis check --category system

# 输出 JSON 报告
sisys diagnosis check --output json -o report.json

# 输出 HTML 报告
sisys diagnosis check --output html -o report.html

# 运行修复
sisys diagnosis fix system.disk_space

# 模拟修复
sisys diagnosis fix system.disk_space --dry-run

# 自动修复所有
sisys diagnosis auto-fix --all

# 列出所有检查
sisys diagnosis list-checks

# 列出所有修复器
sisys diagnosis list-fixers
```

---

## 6. API 接口

### 6.1 REST API

```python
# app/api/diagnosis.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/v1/diagnosis", tags=["diagnosis"])

class CheckRequest(BaseModel):
    check_ids: Optional[List[str]] = None
    category: Optional[str] = None

class CheckResponse(BaseModel):
    timestamp: str
    total_checks: int
    passed: int
    failed: int
    results: List[dict]
    summary: str

class FixRequest(BaseModel):
    check_id: str
    dry_run: bool = False

class FixResponse(BaseModel):
    success: bool
    message: str
    details: Optional[dict] = None

@router.post("/check", response_model=CheckResponse)
async def run_check(request: CheckRequest):
    """运行诊断检查"""
    from app.diagnosis import DiagnosisEngine

    engine = DiagnosisEngine()

    if request.check_ids:
        report = await engine.run_specific_checks(request.check_ids)
    elif request.category:
        checks = engine.check_registry.get_checks_by_category(request.category)
        report = await engine.run_specific_checks([c.check_id for c in checks])
    else:
        report = await engine.run_all_checks()

    return CheckResponse(
        timestamp=report.timestamp,
        total_checks=report.total_checks,
        passed=report.passed,
        failed=report.failed,
        results=[r.__dict__ for r in report.results],
        summary=report.summary
    )

@router.post("/fix", response_model=FixResponse)
async def run_fix(request: FixRequest):
    """运行修复"""
    from app.diagnosis import FixerRegistry

    fixer = FixerRegistry.get_fixer(request.check_id)

    if not fixer:
        raise HTTPException(status_code=404, detail=f"Fixer not found: {request.check_id}")

    if request.dry_run:
        result = await fixer.dry_run()
    else:
        result = await fixer.run()

    return FixResponse(
        success=result.success,
        message=result.message,
        details=result.details
    )

@router.get("/checks")
async def list_checks():
    """列出所有检查"""
    from app.diagnosis import CheckRegistry

    checks = CheckRegistry.get_all_checks()
    return [
        {
            "check_id": c.check_id,
            "name": c.name,
            "description": c.description,
            "severity": c.severity.value
        }
        for c in checks
    ]

@router.get("/health")
async def health_check():
    """快速健康检查"""
    from app.diagnosis import DiagnosisEngine

    engine = DiagnosisEngine()
    critical_checks = ["services.api_health", "services.database"]
    report = await engine.run_specific_checks(critical_checks)

    if report.critical > 0 or report.failed > 0:
        return {"status": "unhealthy", "details": report.summary}
    else:
        return {"status": "healthy", "details": report.summary}
```

### 6.2 WebSocket 实时诊断

```python
# app/api/diagnosis_ws.py
from fastapi import WebSocket
import json

async def diagnosis_websocket(websocket: WebSocket):
    """WebSocket 实时诊断"""
    from app.diagnosis import DiagnosisEngine

    await websocket.accept()

    engine = DiagnosisEngine()

    # 发送开始消息
    await websocket.send_json({"type": "start", "message": "开始诊断..."})

    # 运行检查并实时推送结果
    checks = engine.check_registry.get_all_checks()

    for i, check in enumerate(checks):
        await websocket.send_json({
            "type": "progress",
            "current": i + 1,
            "total": len(checks),
            "check": check.name
        })

        result = await check.run()

        await websocket.send_json({
            "type": "result",
            "check_id": result.check_id,
            "name": result.name,
            "status": result.status.value,
            "severity": result.severity.value,
            "message": result.message
        })

    # 发送完成消息
    report = engine._generate_report()
    await websocket.send_json({
        "type": "complete",
        "report": {
            "summary": report.summary,
            "total": report.total_checks,
            "passed": report.passed,
            "failed": report.failed
        }
    })

    await websocket.close()
```

---

## 7. 自定义诊断规则

### 7.1 创建自定义检查

```python
# plugins/diagnosis/custom_checks.py
from app.diagnosis import BaseCheck, CheckRegistry, CheckResult, Severity, Status

@CheckRegistry.register
class CustomApplicationCheck(BaseCheck):
    """自定义应用检查"""

    check_id = "custom.my_app"
    name = "我的应用检查"
    description = "检查我的应用状态"
    severity = Severity.WARNING

    async def run(self) -> CheckResult:
        # 实现检查逻辑
        # ...

        return CheckResult(
            check_id=self.check_id,
            name=self.name,
            severity=self.severity,
            status=Status.PASSED,
            message="检查通过"
        )
```

### 7.2 创建自定义修复器

```python
# plugins/diagnosis/custom_fixers.py
from app.diagnosis import BaseFixer, FixerRegistry, FixResult

@FixerRegistry.register
class CustomApplicationFixer(BaseFixer):
    """自定义应用修复器"""

    fixer_id = "custom.my_app"
    name = "我的应用修复"
    description = "修复我的应用问题"
    requires_restart = True

    async def run(self) -> FixResult:
        # 实现修复逻辑
        # ...

        return FixResult(
            success=True,
            message="修复成功"
        )

    async def dry_run(self) -> FixResult:
        return FixResult(
            success=True,
            message="将执行修复操作"
        )
```

### 7.3 配置自定义检查

```yaml
# configs/diagnosis.yaml
diagnosis:
  # 启用的检查类别
  enabled_categories:
    - system
    - config
    - services
    - network

  # 禁用的检查
  disabled_checks:
    - network.dns  # 在某些环境中不需要

  # 自定义检查配置
  custom_checks:
    - module: plugins.diagnosis.custom_checks
      class: CustomApplicationCheck

  # 自定义修复器配置
  custom_fixers:
    - module: plugins.diagnosis.custom_fixers
      class: CustomApplicationFixer

  # 自动修复配置
  auto_fix:
    enabled: true
    exclude:
      - system.python_version  # 不自动修复 Python 版本问题
    confirm_required:
      - services.database  # 数据库修复需要确认
```

---

## 8. 日志与报告

### 8.1 文本报告

```
================================================================================
                         Sisyphus 诊断报告
================================================================================
生成时间：2026-03-11 14:30:00

摘要：发现 2 个问题，其中 1 个已自动修复

--------------------------------------------------------------------------------
检查结果汇总
--------------------------------------------------------------------------------
  总检查数：12
  通过：10
  失败：1
  已修复：1
  警告：2
  严重：0

--------------------------------------------------------------------------------
详细结果
--------------------------------------------------------------------------------

[✓] Python 版本检查
    严重性：CRITICAL
    消息：Python 3.12.1 满足要求

[✓] Docker 环境检查
    严重性：CRITICAL
    消息：Docker 已安装并运行 (24.0.7)

[!] 磁盘空间检查
    严重性：WARNING
    状态：已修复
    消息：可用磁盘空间：4.2 GB（建议清理）
    修复：运行 'docker system prune -a' 清理了 2.5 GB

[✓] 配置文件检查
    严重性：CRITICAL
    消息：配置文件有效

[✗] Harbor 连接检查
    严重性：WARNING
    消息：Harbor 连接超时
    建议：检查网络连接和 Harbor 服务状态

================================================================================
```

### 8.2 HTML 报告

```python
# app/diagnosis/reporter.py

class ReportGenerator:
    @staticmethod
    def generate_html(report: DiagnosisReport) -> str:
        """生成 HTML 报告"""

        status_icons = {
            Status.PASSED: '✓',
            Status.FAILED: '✗',
            Status.FIXED: '⚡',
            Status.SKIPPED: '○'
        }

        severity_colors = {
            Severity.INFO: '#17a2b8',
            Severity.WARNING: '#ffc107',
            Severity.ERROR: '#dc3545',
            Severity.CRITICAL: '#721c24'
        }

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Sisyphus 诊断报告</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #f8f9fa; padding: 20px; border-radius: 5px; }}
                .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
                .summary-item {{
                    padding: 15px;
                    border-radius: 5px;
                    text-align: center;
                    min-width: 100px;
                }}
                .passed {{ background: #d4edda; color: #155724; }}
                .failed {{ background: #f8d7da; color: #721c24; }}
                .fixed {{ background: #d1ecf1; color: #0c5460; }}
                .warning {{ background: #fff3cd; color: #856404; }}
                .check-item {{
                    border: 1px solid #dee2e6;
                    padding: 15px;
                    margin: 10px 0;
                    border-radius: 5px;
                }}
                .check-passed {{ border-left: 4px solid #28a745; }}
                .check-failed {{ border-left: 4px solid #dc3545; }}
                .check-fixed {{ border-left: 4px solid #17a2b8; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Sisyphus 诊断报告</h1>
                <p>生成时间：{report.timestamp}</p>
                <p><strong>摘要：</strong>{report.summary}</p>
            </div>

            <div class="summary">
                <div class="summary-item passed">
                    <h3>{report.passed}</h3>
                    <p>通过</p>
                </div>
                <div class="summary-item failed">
                    <h3>{report.failed}</h3>
                    <p>失败</p>
                </div>
                <div class="summary-item fixed">
                    <h3>{sum(1 for r in report.results if r.status == Status.FIXED)}</h3>
                    <p>已修复</p>
                </div>
                <div class="summary-item warning">
                    <h3>{report.warnings}</h3>
                    <p>警告</p>
                </div>
            </div>

            <h2>详细结果</h2>
        """

        for result in report.results:
            icon = status_icons.get(result.status, '?')
            html += f"""
            <div class="check-item check-{result.status.value}">
                <h3>{icon} {result.name}</h3>
                <p><strong>严重性：</strong>
                    <span style="color: {severity_colors[result.severity]}">
                        {result.severity.value.upper()}
                    </span>
                </p>
                <p><strong>消息：</strong>{result.message}</p>
            """

            if result.fix_description:
                html += f"<p><strong>修复建议：</strong>{result.fix_description}</p>"

            html += "</div>"

        html += """
        </body>
        </html>
        """

        return html
```

### 8.3 日志配置

```yaml
# configs/logging.yaml
logging:
  diagnosis:
    level: INFO
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    handlers:
      console:
        class: logging.StreamHandler
        level: INFO
      file:
        class: logging.FileHandler
        filename: logs/diagnosis.log
        level: DEBUG
      report:
        class: logging.FileHandler
        filename: logs/diagnosis-reports/
        level: INFO
        formatter: json

    # 诊断报告保留策略
    report_retention:
      days: 30
      max_reports: 100
```

---

## 附录：完整诊断流程示例

```bash
# 完整诊断流程脚本
#!/bin/bash
# full-diagnosis.sh

echo "=========================================="
echo "  Sisyphus 完整诊断流程"
echo "=========================================="

# 1. 运行所有检查
echo ""
echo "[1/3] 运行诊断检查..."
sisys diagnosis check --output json -o /tmp/diagnosis.json

# 2. 解析结果
echo ""
echo "[2/3] 分析结果..."
FAILED=$(cat /tmp/diagnosis.json | jq '.failed')
FIXABLE=$(cat /tmp/diagnosis.json | jq '[.results[] | select(.fix_available == true)] | length')

echo "失败检查数：$FAILED"
echo "可修复数：$FIXABLE"

# 3. 自动修复
if [ "$FAILED" -gt 0 ] && [ "$FIXABLE" -gt 0 ]; then
    echo ""
    echo "[3/3] 执行自动修复..."
    sisys diagnosis auto-fix --all
fi

# 4. 生成报告
echo ""
echo "生成 HTML 报告..."
sisys diagnosis check --output html -o diagnosis-report.html

echo ""
echo "=========================================="
echo "  诊断完成！"
echo "  报告：diagnosis-report.html"
echo "=========================================="
```
