# 配置向导工具指南

本文档介绍 Sisyphus 系统的配置向导（Config Wizard）工具。

## 目录

- [1. 概述](#1-概述)
- [2. 架构设计](#2-架构设计)
- [3. 配置模式](#3-配置模式)
- [4. 交互式配置](#4-交互式配置)
- [5. 配置模板](#5-配置模板)
- [6. 配置验证](#6-配置验证)
- [7. 配置管理](#7-配置管理)
- [8. API 接口](#8-api-接口)

---

## 1. 概述

配置向导提供：

- 交互式配置生成
- 多环境配置模板
- 配置验证与测试
- 配置导入/导出
- 配置版本管理
- 敏感信息加密

### 核心功能

```
┌─────────────────────────────────────────────────────────┐
│                    配置向导系统                           │
├─────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ 快速配置  │  │ 高级配置  │  │ 模板配置  │  │ 导入导出  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│                         │                                 │
│                         ▼                                 │
│  ┌──────────────────────────────────────────────────┐   │
│  │              配置验证与测试                        │   │
│  └──────────────────────────────────────────────────┘   │
│                         │                                 │
│                         ▼                                 │
│  ┌──────────────────────────────────────────────────┐   │
│  │              配置存储与加密                        │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 架构设计

### 2.1 核心组件

```python
# app/config/wizard/__init__.py
from .engine import ConfigWizard
from .steps import StepRegistry
from .validators import ConfigValidator
from .templates import TemplateManager

__all__ = ['ConfigWizard', 'StepRegistry', 'ConfigValidator', 'TemplateManager']
```

```python
# app/config/wizard/engine.py
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class ConfigStep:
    """配置步骤"""
    id: str
    name: str
    description: str
    required: bool = True
    fields: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class WizardSession:
    """向导会话"""
    session_id: str
    mode: str  # 'quick', 'advanced', 'custom'
    current_step: str
    answers: Dict[str, Any] = field(default_factory=dict)
    completed_steps: List[str] = field(default_factory=list)

class ConfigWizard:
    """配置向导引擎"""

    def __init__(self):
        self.step_registry = StepRegistry()
        self.validator = ConfigValidator()
        self.template_manager = TemplateManager()
        self.sessions: Dict[str, WizardSession] = {}

    def create_session(self, mode: str = 'quick') -> WizardSession:
        """创建新会话"""
        import uuid

        session = WizardSession(
            session_id=str(uuid.uuid4()),
            mode=mode,
            current_step=self._get_first_step(mode)
        )
        self.sessions[session.session_id] = session
        return session

    def get_current_step(self, session_id: str) -> Optional[ConfigStep]:
        """获取当前步骤"""
        session = self.sessions.get(session_id)
        if not session:
            return None

        return self.step_registry.get_step(session.current_step)

    def submit_step(self, session_id: str, answers: Dict[str, Any]) -> Dict[str, Any]:
        """提交步骤答案"""
        session = self.sessions.get(session_id)
        if not session:
            return {'error': 'Session not found'}

        # 验证答案
        step = self.step_registry.get_step(session.current_step)
        validation = self.validator.validate_step(step, answers)

        if not validation['valid']:
            return validation

        # 保存答案
        session.answers.update(answers)
        session.completed_steps.append(session.current_step)

        # 移动到下一步
        session.current_step = self._get_next_step(session.mode, session.current_step)

        if session.current_step is None:
            # 完成所有步骤，生成配置
            config = self._generate_config(session)
            return {
                'complete': True,
                'config': config,
                'session': session
            }

        return {
            'complete': False,
            'next_step': self.get_current_step(session_id)
        }

    def _get_first_step(self, mode: str) -> str:
        """获取第一步"""
        steps = self.step_registry.get_steps_for_mode(mode)
        return steps[0].id if steps else None

    def _get_next_step(self, mode: str, current: str) -> Optional[str]:
        """获取下一步"""
        steps = self.step_registry.get_steps_for_mode(mode)

        for i, step in enumerate(steps):
            if step.id == current:
                if i + 1 < len(steps):
                    return steps[i + 1].id
                return None

        return None

    def _generate_config(self, session: WizardSession) -> Dict[str, Any]:
        """生成配置"""
        config = {}

        # 合并所有步骤的答案
        for step_id in session.completed_steps:
            step = self.step_registry.get_step(step_id)
            step_config = self._build_step_config(step, session.answers)
            config = self._merge_config(config, step_config)

        return config

    def _build_step_config(self, step: ConfigStep, answers: Dict[str, Any]) -> Dict[str, Any]:
        """构建步骤配置"""
        # 根据步骤类型构建配置
        pass

    def _merge_config(self, base: Dict, update: Dict) -> Dict:
        """合并配置"""
        import copy
        result = copy.deepcopy(base)

        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value

        return result
```

### 2.2 步骤注册表

```python
# app/config/wizard/steps.py
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

class BaseStep(ABC):
    """配置步骤基类"""

    step_id: str = ""
    name: str = ""
    description: str = ""
    modes: List[str] = ['quick', 'advanced', 'custom']

    @abstractmethod
    def get_fields(self) -> List[Dict[str, Any]]:
        """获取步骤字段"""
        pass

    @abstractmethod
    def build_config(self, answers: Dict[str, Any]) -> Dict[str, Any]:
        """构建配置"""
        pass

class StepRegistry:
    """步骤注册表"""

    _steps: Dict[str, BaseStep] = {}

    @classmethod
    def register(cls, step_class):
        instance = step_class()
        cls._steps[instance.step_id] = instance
        return step_class

    @classmethod
    def get_step(cls, step_id: str) -> Optional[BaseStep]:
        return cls._steps.get(step_id)

    @classmethod
    def get_steps_for_mode(cls, mode: str) -> List[BaseStep]:
        return [s for s in cls._steps.values() if mode in s.modes]
```

---

## 3. 配置模式

### 3.1 快速配置模式

```python
# app/config/wizard/steps/quick.py
from . import BaseStep, StepRegistry

@StepRegistry.register
class BasicInfoStep(BaseStep):
    """基本信息步骤"""

    step_id = "quick.basic_info"
    name = "基本信息"
    description = "配置基本应用信息"
    modes = ['quick', 'advanced']

    def get_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                'name': 'app_name',
                'label': '应用名称',
                'type': 'text',
                'required': True,
                'default': 'Sisyphus',
                'help': '应用的显示名称'
            },
            {
                'name': 'environment',
                'label': '环境',
                'type': 'select',
                'required': True,
                'options': [
                    {'value': 'development', 'label': '开发环境'},
                    {'value': 'staging', 'label': '测试环境'},
                    {'value': 'production', 'label': '生产环境'}
                ],
                'default': 'development'
            },
            {
                'name': 'port',
                'label': '服务端口',
                'type': 'number',
                'required': True,
                'default': 8080,
                'min': 1024,
                'max': 65535
            }
        ]

    def build_config(self, answers: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'app': {
                'name': answers['app_name'],
                'environment': answers['environment']
            },
            'server': {
                'host': '0.0.0.0',
                'port': answers['port']
            }
        }

@StepRegistry.register
class DatabaseStep(BaseStep):
    """数据库配置步骤"""

    step_id = "quick.database"
    name = "数据库配置"
    description = "配置数据库连接"
    modes = ['quick', 'advanced']

    def get_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                'name': 'db_type',
                'label': '数据库类型',
                'type': 'select',
                'required': True,
                'options': [
                    {'value': 'postgresql', 'label': 'PostgreSQL'},
                    {'value': 'mysql', 'label': 'MySQL'},
                    {'value': 'sqlite', 'label': 'SQLite (仅开发)'}
                ],
                'default': 'postgresql'
            },
            {
                'name': 'db_host',
                'label': '数据库主机',
                'type': 'text',
                'required': True,
                'default': 'localhost'
            },
            {
                'name': 'db_port',
                'label': '数据库端口',
                'type': 'number',
                'required': True,
                'default': 5432
            },
            {
                'name': 'db_name',
                'label': '数据库名称',
                'type': 'text',
                'required': True,
                'default': 'sisys'
            },
            {
                'name': 'db_user',
                'label': '数据库用户',
                'type': 'text',
                'required': True,
                'default': 'sisys'
            },
            {
                'name': 'db_password',
                'label': '数据库密码',
                'type': 'password',
                'required': True,
                'help': '建议使用强密码'
            }
        ]

    def build_config(self, answers: Dict[str, Any]) -> Dict[str, Any]:
        db_type = answers['db_type']
        ports = {'postgresql': 5432, 'mysql': 3306, 'sqlite': None}

        config = {
            'database': {
                'type': db_type,
                'host': answers['db_host'],
                'port': answers.get('db_port', ports.get(db_type, 5432)),
                'name': answers['db_name'],
                'user': answers['db_user'],
                'password': answers['db_password']
            }
        }

        if db_type == 'sqlite':
            config['database']['file'] = answers.get('db_file', 'sisys.db')

        return config

@StepRegistry.register
class HarborStep(BaseStep):
    """Harbor 配置步骤"""

    step_id = "quick.harbor"
    name = "Harbor 配置"
    description = "配置 Harbor 镜像仓库"
    modes = ['quick', 'advanced']

    def get_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                'name': 'harbor_url',
                'label': 'Harbor URL',
                'type': 'url',
                'required': True,
                'default': 'https://harbor.example.com',
                'help': 'Harbor 镜像仓库地址'
            },
            {
                'name': 'harbor_user',
                'label': 'Harbor 用户名',
                'type': 'text',
                'required': True
            },
            {
                'name': 'harbor_password',
                'label': 'Harbor 密码',
                'type': 'password',
                'required': True
            },
            {
                'name': 'harbor_project',
                'label': 'Harbor 项目',
                'type': 'text',
                'required': True,
                'default': 'sisys'
            }
        ]

    def build_config(self, answers: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'harbor': {
                'url': answers['harbor_url'],
                'username': answers['harbor_user'],
                'password': answers['harbor_password'],
                'project': answers['harbor_project']
            }
        }
```

### 3.2 高级配置模式

```python
# app/config/wizard/steps/advanced.py
from . import BaseStep, StepRegistry

@StepRegistry.register
class KubernetesStep(BaseStep):
    """Kubernetes 配置步骤"""

    step_id = "advanced.kubernetes"
    name = "Kubernetes 配置"
    description = "配置 Kubernetes 集群连接"
    modes = ['advanced', 'custom']

    def get_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                'name': 'kube_context',
                'label': 'Kubernetes 上下文',
                'type': 'text',
                'required': False,
                'help': '留空使用当前上下文'
            },
            {
                'name': 'kube_namespace',
                'label': '命名空间',
                'type': 'text',
                'required': True,
                'default': 'sisys'
            },
            {
                'name': 'kube_config_path',
                'label': 'Kubeconfig 路径',
                'type': 'file',
                'required': False,
                'default': '~/.kube/config'
            },
            {
                'name': 'use_in_cluster',
                'label': '集群内运行',
                'type': 'boolean',
                'default': False,
                'help': '如果在集群内运行，使用服务账户'
            }
        ]

    def build_config(self, answers: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'kubernetes': {
                'context': answers.get('kube_context'),
                'namespace': answers['kube_namespace'],
                'config_path': answers.get('kube_config_path'),
                'in_cluster': answers.get('use_in_cluster', False)
            }
        }

@StepRegistry.register
class ArgoCDStep(BaseStep):
    """ArgoCD 配置步骤"""

    step_id = "advanced.argocd"
    name = "ArgoCD 配置"
    description = "配置 ArgoCD GitOps"
    modes = ['advanced', 'custom']

    def get_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                'name': 'argocd_url',
                'label': 'ArgoCD URL',
                'type': 'url',
                'required': True,
                'default': 'https://argocd.example.com'
            },
            {
                'name': 'argocd_token',
                'label': 'ArgoCD API Token',
                'type': 'password',
                'required': True,
                'help': '在 ArgoCD UI 中生成'
            },
            {
                'name': 'argocd_insecure',
                'label': '跳过 TLS 验证',
                'type': 'boolean',
                'default': False
            },
            {
                'name': 'git_repo',
                'label': 'GitOps 仓库',
                'type': 'text',
                'required': True,
                'help': '存放 Kubernetes 配置的 Git 仓库'
            },
            {
                'name': 'git_branch',
                'label': 'Git 分支',
                'type': 'text',
                'default': 'main'
            }
        ]

    def build_config(self, answers: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'argocd': {
                'url': answers['argocd_url'],
                'token': answers['argocd_token'],
                'insecure_skip_verify': answers.get('argocd_insecure', False)
            },
            'gitops': {
                'repository': answers['git_repo'],
                'branch': answers.get('git_branch', 'main')
            }
        }

@StepRegistry.register
class SecurityStep(BaseStep):
    """安全配置步骤"""

    step_id = "advanced.security"
    name = "安全配置"
    description = "配置安全选项"
    modes = ['advanced', 'custom']

    def get_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                'name': 'jwt_secret',
                'label': 'JWT 密钥',
                'type': 'password',
                'required': True,
                'generate': True,
                'help': '留空自动生成'
            },
            {
                'name': 'jwt_expiry',
                'label': 'JWT 过期时间',
                'type': 'text',
                'default': '24h',
                'help': '例如：1h, 24h, 7d'
            },
            {
                'name': 'enable_https',
                'label': '启用 HTTPS',
                'type': 'boolean',
                'default': True
            },
            {
                'name': 'ssl_cert_path',
                'label': 'SSL 证书路径',
                'type': 'file',
                'required_if': {'enable_https': True}
            },
            {
                'name': 'ssl_key_path',
                'label': 'SSL 密钥路径',
                'type': 'file',
                'required_if': {'enable_https': True}
            },
            {
                'name': 'cors_origins',
                'label': 'CORS 允许的来源',
                'type': 'text',
                'multiple': True,
                'default': ['http://localhost:3000'],
                'help': '每行一个 URL'
            }
        ]

    def build_config(self, answers: Dict[str, Any]) -> Dict[str, Any]:
        import secrets

        jwt_secret = answers.get('jwt_secret')
        if not jwt_secret or answers.get('generate'):
            jwt_secret = secrets.token_urlsafe(32)

        return {
            'security': {
                'jwt': {
                    'secret': jwt_secret,
                    'expiry': answers.get('jwt_expiry', '24h')
                },
                'https': {
                    'enabled': answers.get('enable_https', True),
                    'cert': answers.get('ssl_cert_path'),
                    'key': answers.get('ssl_key_path')
                },
                'cors': {
                    'allow_origins': answers.get('cors_origins', [])
                }
            }
        }
```

### 3.3 自定义配置模式

```python
# app/config/wizard/steps/custom.py
from . import BaseStep, StepRegistry

@StepRegistry.register
class CustomServicesStep(BaseStep):
    """自定义服务配置"""

    step_id = "custom.services"
    name = "服务配置"
    description = "配置自定义服务"
    modes = ['custom']

    def get_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                'name': 'services',
                'label': '服务列表',
                'type': 'list',
                'item_type': 'object',
                'fields': [
                    {'name': 'name', 'label': '名称', 'type': 'text'},
                    {'name': 'port', 'label': '端口', 'type': 'number'},
                    {'name': 'replicas', 'label': '副本数', 'type': 'number', 'default': 1},
                    {'name': 'resources', 'label': '资源配置', 'type': 'json'}
                ]
            }
        ]

    def build_config(self, answers: Dict[str, Any]) -> Dict[str, Any]:
        return {'services': answers.get('services', [])}
```

---

## 4. 交互式配置

### 4.1 命令行交互

```python
# app/config/wizard/cli.py
import click
from typing import Any, Dict
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt, FloatPrompt
from rich.table import Table

console = Console()

class InteractiveWizard:
    """交互式向导"""

    def __init__(self, wizard: ConfigWizard):
        self.wizard = wizard
        self.session = None

    def run(self, mode: str = 'quick'):
        """运行向导"""
        console.print("\n[bold blue]Sisyphus 配置向导[/bold blue]\n")

        self.session = self.wizard.create_session(mode)

        while True:
            step = self.wizard.get_current_step(self.session.session_id)
            if not step:
                break

            console.print(f"\n[bold green]{step.name}[/bold green]")
            console.print(f"[dim]{step.description}[/dim]\n")

            answers = self._collect_step_answers(step)
            result = self.wizard.submit_step(self.session.session_id, answers)

            if result.get('error'):
                console.print(f"[red]错误：{result['error']}[/red]")
                continue

            if result.get('complete'):
                console.print("\n[bold green]✓ 配置完成![/bold green]\n")
                return result['config']

        return None

    def _collect_step_answers(self, step) -> Dict[str, Any]:
        """收集步骤答案"""
        answers = {}

        for field in step.get_fields():
            value = self._prompt_for_field(field)
            answers[field['name']] = value

        return answers

    def _prompt_for_field(self, field: Dict[str, Any]) -> Any:
        """为字段提示输入"""
        field_type = field.get('type', 'text')
        label = field.get('label', field['name'])
        default = field.get('default')
        required = field.get('required', False)
        help_text = field.get('help', '')

        # 显示帮助
        if help_text:
            console.print(f"  [dim]{help_text}[/dim]")

        # 根据类型提示输入
        if field_type == 'text':
            return Prompt.ask(
                f"  {label}",
                default=str(default) if default else None
            )

        elif field_type == 'password':
            if field.get('generate'):
                import secrets
                generated = secrets.token_urlsafe(32)
                console.print(f"  [dim]已生成：{generated[:10]}...[/dim]")
                if Confirm.ask("  使用生成的值？", default=True):
                    return generated
            return Prompt.ask(f"  {label}", password=True)

        elif field_type == 'number':
            return IntPrompt.ask(
                f"  {label}",
                default=int(default) if default else None
            )

        elif field_type == 'select':
            options = field.get('options', [])
            choices = [f"{o['value']} ({o['label']})" for o in options]

            console.print("  选项:")
            for i, opt in enumerate(options):
                default_mark = " [green](默认)[/green]" if opt['value'] == default else ""
                console.print(f"    {i + 1}. {opt['label']}{default_mark}")

            choice = IntPrompt.ask("  选择", default=1)
            return options[choice - 1]['value']

        elif field_type == 'boolean':
            return Confirm.ask(f"  {label}", default=bool(default) if default is not None else False)

        elif field_type == 'file':
            path = Prompt.ask(
                f"  {label}",
                default=str(default) if default else None
            )
            if path:
                path = Path(path).expanduser()
                if not path.exists():
                    if Confirm.ask(f"  文件不存在，创建？", default=False):
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.touch()
            return str(path)

        elif field_type == 'url':
            url = Prompt.ask(
                f"  {label}",
                default=str(default) if default else None
            )
            # 验证 URL
            if url and not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            return url

        elif field_type == 'list':
            console.print("  输入多个值，空行结束:")
            values = []
            while True:
                value = Prompt.ask(f"    值 #{len(values) + 1}")
                if not value:
                    break
                values.append(value)
            return values

        else:
            return Prompt.ask(f"  {label}", default=str(default) if default else None)
```

### 4.2 TUI 界面

```python
# app/config/wizard/tui.py
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Input, Button, Select, Label
from textual.binding import Binding
from textual.containers import Container

class ConfigWizardApp(App):
    """配置向导 TUI 应用"""

    CSS = """
    Screen {
        align: center middle;
    }

    Container {
        width: 80;
        height: 30;
        border: solid blue;
        padding: 1 2;
    }

    #step-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    #step-description {
        color: $text-muted;
        margin-bottom: 2;
    }

    .field-label {
        margin: 1 0;
    }

    #next-button {
        margin-top: 2;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("n", "next", "下一步"),
    ]

    def __init__(self, wizard: ConfigWizard, mode: str = 'quick'):
        super().__init__()
        self.wizard = wizard
        self.mode = mode
        self.session = None
        self.current_answers = {}

    def on_mount(self) -> None:
        self.session = self.wizard.create_session(self.mode)
        self._refresh_step()

    def _refresh_step(self):
        """刷新当前步骤"""
        step = self.wizard.get_current_step(self.session.session_id)
        if step:
            self.push_screen(StepScreen(step, self.current_answers))
        else:
            self._complete()

    def _complete(self):
        """完成配置"""
        self.exit(self.wizard.sessions[self.session.session_id].answers)

    def action_next(self):
        self._refresh_step()

class StepScreen(Screen):
    """步骤屏幕"""

    def __init__(self, step, answers: dict):
        super().__init__()
        self.step = step
        self.answers = answers

    def compose(self) -> ComposeResult:
        yield Header()

        yield Container(
            Static(f"[bold]{self.step.name}[/bold]", id="step-title"),
            Static(self.step.description, id="step-description"),
            id="step-container"
        )

        # 为每个字段创建输入
        for field in self.step.get_fields():
            yield Label(field['label'], classes="field-label")

            if field['type'] == 'select':
                options = [(o['label'], o['value']) for o in field.get('options', [])]
                yield Select(options, id=f"field-{field['name']}")
            else:
                yield Input(
                    placeholder=field.get('help', ''),
                    id=f"field-{field['name']}"
                )

        yield Button("下一步", id="next-button", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next-button":
            # 收集答案
            answers = {}
            for field in self.step.get_fields():
                widget = self.query_one(f"#field-{field['name']}")
                if isinstance(widget, Select):
                    answers[field['name']] = widget.value
                elif isinstance(widget, Input):
                    answers[field['name']] = widget.value
            self.dismiss(answers)
```

---

## 5. 配置模板

### 5.1 模板管理

```python
# app/config/wizard/templates.py
from pathlib import Path
from typing import Dict, Any, List
import yaml

class TemplateManager:
    """配置模板管理器"""

    def __init__(self, template_dir: Path = None):
        self.template_dir = template_dir or Path(__file__).parent / 'templates'
        self.templates: Dict[str, Dict[str, Any]] = {}
        self._load_templates()

    def _load_templates(self):
        """加载模板"""
        if not self.template_dir.exists():
            return

        for template_file in self.template_dir.glob('*.yaml'):
            with open(template_file) as f:
                template = yaml.safe_load(f)
                self.templates[template_file.stem] = template

    def list_templates(self) -> List[Dict[str, Any]]:
        """列出所有模板"""
        return [
            {
                'id': tid,
                'name': t.get('name', tid),
                'description': t.get('description', ''),
                'category': t.get('category', 'general')
            }
            for tid, t in self.templates.items()
        ]

    def get_template(self, template_id: str) -> Dict[str, Any]:
        """获取模板"""
        return self.templates.get(template_id, {})

    def apply_template(self, template_id: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """应用模板"""
        import copy
        template = copy.deepcopy(self.get_template(template_id))

        # 替换变量
        def replace_vars(obj):
            if isinstance(obj, dict):
                return {k: replace_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_vars(v) for v in obj]
            elif isinstance(obj, str):
                for key, value in variables.items():
                    obj = obj.replace(f'{{{{{key}}}}}', str(value))
                return obj
            return obj

        return replace_vars(template)

    def save_as_template(self, config: Dict[str, Any], name: str, description: str = ''):
        """保存为模板"""
        template = {
            'name': name,
            'description': description,
            'config': config
        }

        template_file = self.template_dir / f"{name.lower().replace(' ', '_')}.yaml"
        with open(template_file, 'w') as f:
            yaml.dump(template, f, default_flow_style=False)
```

### 5.2 预定义模板

```yaml
# templates/development.yaml
name: 开发环境
description: 本地开发环境配置
category: environment

config:
  app:
    name: Sisyphus
    environment: development
    debug: true

  server:
    host: 0.0.0.0
    port: 8080
    reload: true

  database:
    type: postgresql
    host: localhost
    port: 5432
    name: sisys_dev
    user: sisys
    pool_size: 5

  logging:
    level: DEBUG
    format: detailed

  cache:
    type: memory
    ttl: 300
```

```yaml
# templates/production.yaml
name: 生产环境
description: 生产环境配置
category: environment

config:
  app:
    name: Sisyphus
    environment: production
    debug: false

  server:
    host: 0.0.0.0
    port: 8080
    workers: 4
    reload: false

  database:
    type: postgresql
    host: {{DB_HOST}}
    port: 5432
    name: {{DB_NAME}}
    user: {{DB_USER}}
    password: {{DB_PASSWORD}}
    pool_size: 20
    max_overflow: 10

  logging:
    level: INFO
    format: json

  cache:
    type: redis
    host: {{REDIS_HOST}}
    port: 6379
    ttl: 3600

  security:
    https:
      enabled: true
    cors:
      allow_origins:
        - https://app.example.com
```

```yaml
# templates/kubernetes.yaml
name: Kubernetes 部署
description: Kubernetes 集群配置
category: deployment

config:
  kubernetes:
    namespace: sisys
    in_cluster: true

  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 1000m
      memory: 1Gi

  replicas: 3

  health_check:
    liveness:
      path: /health
      interval: 30
    readiness:
      path: /ready
      interval: 10

  ingress:
    enabled: true
    host: sisys.example.com
    tls: true
```

---

## 6. 配置验证

### 6.1 验证器

```python
# app/config/wizard/validators.py
from typing import Dict, Any, List, Tuple
import re

class ConfigValidator:
    """配置验证器"""

    def __init__(self):
        self.validators = {
            'text': self._validate_text,
            'number': self._validate_number,
            'boolean': self._validate_boolean,
            'email': self._validate_email,
            'url': self._validate_url,
            'file': self._validate_file,
            'port': self._validate_port,
        }

    def validate_step(self, step, answers: Dict[str, Any]) -> Dict[str, Any]:
        """验证步骤答案"""
        errors = []

        for field in step.get_fields():
            name = field['name']
            value = answers.get(name)

            # 检查必填字段
            if field.get('required') and not value:
                errors.append(f"{field['label']} 是必填的")
                continue

            if value:
                # 类型验证
                validator = self.validators.get(field.get('type', 'text'))
                if validator:
                    is_valid, message = validator(value, field)
                    if not is_valid:
                        errors.append(f"{field['label']}: {message}")

        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """验证完整配置"""
        from jsonschema import validate, ValidationError

        schema = self._get_config_schema()

        try:
            validate(instance=config, schema=schema)
            return {'valid': True, 'errors': []}
        except ValidationError as e:
            return {'valid': False, 'errors': [e.message]}

    def test_connection(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """测试连接"""
        results = {}

        # 测试数据库连接
        if 'database' in config:
            results['database'] = self._test_database(config['database'])

        # 测试 Harbor 连接
        if 'harbor' in config:
            results['harbor'] = self._test_harbor(config['harbor'])

        # 测试 Kubernetes 连接
        if 'kubernetes' in config:
            results['kubernetes'] = self._test_kubernetes(config['kubernetes'])

        return results

    def _validate_text(self, value, field) -> Tuple[bool, str]:
        if not isinstance(value, str):
            return False, "必须是文本"
        if 'min_length' in field and len(value) < field['min_length']:
            return False, f"最少 {field['min_length']} 个字符"
        if 'max_length' in field and len(value) > field['max_length']:
            return False, f"最多 {field['max_length']} 个字符"
        return True, ""

    def _validate_number(self, value, field) -> Tuple[bool, str]:
        try:
            num = int(value)
            if 'min' in field and num < field['min']:
                return False, f"最小值为 {field['min']}"
            if 'max' in field and num > field['max']:
                return False, f"最大值为 {field['max']}"
            return True, ""
        except (ValueError, TypeError):
            return False, "必须是数字"

    def _validate_port(self, value, field) -> Tuple[bool, str]:
        try:
            port = int(value)
            if port < 1 or port > 65535:
                return False, "端口必须在 1-65535 之间"
            return True, ""
        except (ValueError, TypeError):
            return False, "必须是有效端口号"

    def _validate_url(self, value, field) -> Tuple[bool, str]:
        pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(pattern, value):
            return False, "必须是有效的 URL"
        return True, ""

    def _validate_email(self, value, field) -> Tuple[bool, str]:
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(pattern, value):
            return False, "必须是有效的邮箱地址"
        return True, ""

    def _validate_file(self, value, field) -> Tuple[bool, str]:
        from pathlib import Path
        path = Path(value).expanduser()
        if field.get('must_exist') and not path.exists():
            return False, "文件不存在"
        if field.get('must_be_dir') and not path.is_dir():
            return False, "必须是目录"
        return True, ""

    def _validate_boolean(self, value, field) -> Tuple[bool, str]:
        if not isinstance(value, bool):
            return False, "必须是布尔值"
        return True, ""

    def _test_database(self, db_config: Dict[str, Any]) -> Dict[str, Any]:
        """测试数据库连接"""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=db_config.get('host', 'localhost'),
                port=db_config.get('port', 5432),
                database=db_config.get('name'),
                user=db_config.get('user'),
                password=db_config.get('password'),
                connect_timeout=5
            )
            conn.close()
            return {'success': True, 'message': '连接成功'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def _test_harbor(self, harbor_config: Dict[str, Any]) -> Dict[str, Any]:
        """测试 Harbor 连接"""
        import requests
        try:
            response = requests.get(
                f"{harbor_config['url']}/api/v2.0/systeminfo",
                auth=(harbor_config['username'], harbor_config['password']),
                timeout=10,
                verify=not harbor_config.get('insecure', False)
            )
            if response.status_code == 200:
                return {'success': True, 'message': '连接成功'}
            else:
                return {'success': False, 'message': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def _test_kubernetes(self, kube_config: Dict[str, Any]) -> Dict[str, Any]:
        """测试 Kubernetes 连接"""
        try:
            from kubernetes import client, config

            if kube_config.get('in_cluster'):
                config.load_incluster_config()
            else:
                config_path = kube_config.get('config_path', '~/.kube/config')
                config.load_kube_config(path=Path(config_path).expanduser())

            v1 = client.CoreV1Api()
            v1.list_namespace(timeout_seconds=5)

            return {'success': True, 'message': '连接成功'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def _get_config_schema(self) -> Dict[str, Any]:
        """获取配置 JSON Schema"""
        return {
            'type': 'object',
            'required': ['app', 'server', 'database'],
            'properties': {
                'app': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string'},
                        'environment': {'type': 'string', 'enum': ['development', 'staging', 'production']}
                    }
                },
                'server': {
                    'type': 'object',
                    'properties': {
                        'host': {'type': 'string'},
                        'port': {'type': 'integer', 'minimum': 1, 'maximum': 65535}
                    }
                },
                'database': {
                    'type': 'object',
                    'properties': {
                        'type': {'type': 'string'},
                        'host': {'type': 'string'},
                        'port': {'type': 'integer'},
                        'name': {'type': 'string'},
                        'user': {'type': 'string'},
                        'password': {'type': 'string'}
                    }
                }
            }
        }
```

---

## 7. 配置管理

### 7.1 命令行接口

```python
# app/cli/config.py
import click
import json
from pathlib import Path

@click.group()
def config():
    """配置管理"""
    pass

@config.command()
@click.option('--mode', '-m', type=click.Choice(['quick', 'advanced', 'custom']), default='quick')
@click.option('--output', '-o', type=click.Path(), help='输出文件路径')
def wizard(mode, output):
    """启动配置向导"""
    from app.config.wizard import ConfigWizard
    from app.config.wizard.cli import InteractiveWizard

    wizard = ConfigWizard()
    interactive = InteractiveWizard(wizard)

    config = interactive.run(mode)

    if config:
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            import yaml
            with open(output_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)

            click.echo(f"配置已保存到：{output_path}")
        else:
            click.echo("\n生成的配置:")
            click.echo(json.dumps(config, indent=2))

@config.command()
@click.option('--template', '-t', help='使用模板')
@click.option('--output', '-o', type=click.Path(), help='输出文件路径')
@click.argument('variables', nargs=-1)
def from_template(template, output, variables):
    """从模板创建配置"""
    from app.config.wizard import TemplateManager

    manager = TemplateManager()

    # 解析变量
    var_dict = {}
    for var in variables:
        if '=' in var:
            key, value = var.split('=', 1)
            var_dict[key] = value

    config = manager.apply_template(template, var_dict)

    if output:
        output_path = Path(output)
        import yaml
        with open(output_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        click.echo(f"配置已保存到：{output_path}")
    else:
        click.echo(json.dumps(config, indent=2))

@config.command()
@click.argument('config_file', type=click.Path(exists=True))
def validate(config_file):
    """验证配置"""
    from app.config.wizard import ConfigValidator
    import yaml

    with open(config_file) as f:
        config = yaml.safe_load(f)

    validator = ConfigValidator()

    # 验证结构
    result = validator.validate_config(config)
    if not result['valid']:
        click.echo("配置验证失败:")
        for error in result['errors']:
            click.echo(f"  - {error}")
        return

    click.echo("✓ 配置结构有效")

    # 测试连接
    click.echo("\n测试连接...")
    test_results = validator.test_connection(config)

    for service, result in test_results.items():
        icon = "✓" if result['success'] else "✗"
        click.echo(f"  {icon} {service}: {result['message']}")

@config.command()
@click.argument('config_file', type=click.Path(exists=True))
def encrypt(config_file):
    """加密敏感配置"""
    from app.utils.crypto import ConfigEncryptor
    import yaml

    with open(config_file) as f:
        config = yaml.safe_load(f)

    encryptor = ConfigEncryptor()
    encrypted = encryptor.encrypt_sensitive_fields(config)

    # 输出加密后的配置
    click.echo(yaml.dump(encrypted, default_flow_style=False))

@config.command()
@click.argument('config_file', type=click.Path(exists=True))
def decrypt(config_file):
    """解密配置"""
    from app.utils.crypto import ConfigEncryptor
    import yaml

    with open(config_file) as f:
        config = yaml.safe_load(f)

    encryptor = ConfigEncryptor()
    decrypted = encryptor.decrypt_sensitive_fields(config)

    click.echo(yaml.dump(decrypted, default_flow_style=False))

@config.command()
def templates():
    """列出可用模板"""
    from app.config.wizard import TemplateManager

    manager = TemplateManager()
    templates = manager.list_templates()

    click.echo(f"{'ID':<20} {'名称':<20} {'类别':<15}")
    click.echo("-" * 55)

    for t in templates:
        click.echo(f"{t['id']:<20} {t['name']:<20} {t['category']:<15}")
```

### 7.2 使用示例

```bash
# 启动交互式配置向导
sisys config wizard

# 快速模式
sisys config wizard --mode quick

# 高级模式
sisys config wizard --mode advanced

# 保存到文件
sisys config wizard --mode quick --output configs/production.yaml

# 从模板创建
sisys config from-template production \
    --output configs/prod.yaml \
    DB_HOST=db.example.com \
    DB_NAME=sisys_prod \
    DB_USER=admin

# 验证配置
sisys config validate configs/production.yaml

# 加密敏感配置
sisys config encrypt configs/production.yaml > configs/production.enc.yaml

# 列出模板
sisys config templates
```

---

## 8. API 接口

### 8.1 REST API

```python
# app/api/config.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

router = APIRouter(prefix="/api/v1/config", tags=["config"])

class WizardStartRequest(BaseModel):
    mode: str = 'quick'

class WizardStepSubmitRequest(BaseModel):
    session_id: str
    answers: Dict[str, Any]

class ConfigValidateRequest(BaseModel):
    config: Dict[str, Any]

class TemplateApplyRequest(BaseModel):
    template_id: str
    variables: Dict[str, Any] = {}

@router.post("/wizard/start")
async def start_wizard(request: WizardStartRequest):
    """启动配置向导"""
    from app.config.wizard import ConfigWizard

    wizard = ConfigWizard()
    session = wizard.create_session(request.mode)

    return {
        'session_id': session.session_id,
        'current_step': wizard.get_current_step(session.session_id)
    }

@router.post("/wizard/submit")
async def submit_wizard_step(request: WizardStepSubmitRequest):
    """提交向导步骤"""
    from app.config.wizard import ConfigWizard

    wizard = ConfigWizard()
    result = wizard.submit_step(request.session_id, request.answers)

    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])

    return result

@router.post("/validate")
async def validate_config(request: ConfigValidateRequest):
    """验证配置"""
    from app.config.wizard import ConfigValidator

    validator = ConfigValidator()
    result = validator.validate_config(request.config)

    return result

@router.post("/test-connection")
async def test_connection(request: ConfigValidateRequest):
    """测试配置连接"""
    from app.config.wizard import ConfigValidator

    validator = ConfigValidator()
    results = validator.test_connection(request.config)

    return results

@router.get("/templates")
async def list_templates():
    """列出模板"""
    from app.config.wizard import TemplateManager

    manager = TemplateManager()
    return manager.list_templates()

@router.post("/templates/apply")
async def apply_template(request: TemplateApplyRequest):
    """应用模板"""
    from app.config.wizard import TemplateManager

    manager = TemplateManager()
    config = manager.apply_template(request.template_id, request.variables)

    return config
```

---

## 附录：配置示例

```yaml
# 完整配置示例
app:
  name: Sisyphus
  environment: production
  debug: false

server:
  host: 0.0.0.0
  port: 8080
  workers: 4
  reload: false

database:
  type: postgresql
  host: db.example.com
  port: 5432
  name: sisys_prod
  user: sisys
  password: ENC[AES256_GCM,data:xxx,tag:yyy,iv:zzz]
  pool_size: 20

harbor:
  url: https://harbor.example.com
  username: sisys
  password: ENC[AES256_GCM,data:aaa,tag:bbb,iv:ccc]
  project: sisys

kubernetes:
  namespace: sisys-prod
  in_cluster: true

argocd:
  url: https://argocd.example.com
  token: ENC[AES256_GCM,data:ddd,tag:eee,iv:fff]
  insecure_skip_verify: false

logging:
  level: INFO
  format: json
  outputs:
    - type: console
    - type: file
      path: /var/log/sisys/app.log

security:
  jwt:
    secret: ENC[AES256_GCM,data:ggg,tag:hhh,iv:iii]
    expiry: 24h
  https:
    enabled: true
    cert: /etc/ssl/sisys.crt
    key: /etc/ssl/sisys.key
  cors:
    allow_origins:
      - https://app.example.com
```
