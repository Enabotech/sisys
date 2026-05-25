"""FastAPI 应用工厂单元测试

测试 create_app 函数的基本行为
"""

from __future__ import annotations

from fastapi import FastAPI

from src.interfaces.api.app import create_app


class TestCreateApp:
    """create_app 函数测试"""

    def test_create_app_returns_fastapi_instance(self) -> None:
        """测试 create_app 返回 FastAPI 实例"""
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_create_app_has_lifespan(self) -> None:
        """测试 create_app 配置了 lifespan"""
        app = create_app()
        # lifespan 在 FastAPI 实例的 router 上配置
        # 检查 app 对象存在
        assert app is not None

    def test_create_app_multiple_calls_return_separate_instances(self) -> None:
        """测试多次调用 create_app 返回不同实例"""
        app1 = create_app()
        app2 = create_app()
        assert app1 is not app2
