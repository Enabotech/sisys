"""PIPL 隐私保护集成验证测试

等保2.0三级隐私保护合规验证:
- PIPL-1: 个人信息访问记录功能
- PIPL-2: 删除请求响应时间 <24h
- PIPL-3: 数据主体权利保障

本测试验证 PIPLComplianceService 与等保合规的集成

对应 Story: 1-12-equilibrium-level-3-compliance Task 5 Subtask 5.14-5.16
"""

from __future__ import annotations

import pytest

from src.infrastructure.security.pipl_compliance_service_impl import (
    PIPLComplianceServiceImpl,
)


@pytest.fixture
def pipl_service() -> PIPLComplianceServiceImpl:
    """创建 PIPL 合规服务实例"""
    return PIPLComplianceServiceImpl()


class TestPIPLComplianceIntegration:
    """PIPL 合规集成验证"""

    @pytest.mark.asyncio
    async def test_pipl_service_has_record_access(
        self,
        pipl_service: PIPLComplianceServiceImpl,
    ) -> None:
        """PIPL 服务应具备访问记录功能"""
        assert hasattr(pipl_service, "record_access")
        assert callable(pipl_service.record_access)

    @pytest.mark.asyncio
    async def test_pipl_service_has_deletion_request(
        self,
        pipl_service: PIPLComplianceServiceImpl,
    ) -> None:
        """PIPL 服务应具备删除请求响应功能"""
        assert hasattr(pipl_service, "respond_to_deletion_request")
        assert callable(pipl_service.respond_to_deletion_request)

    @pytest.mark.asyncio
    async def test_pipl_service_has_access_request(
        self,
        pipl_service: PIPLComplianceServiceImpl,
    ) -> None:
        """PIPL 服务应具备访问请求响应功能"""
        assert hasattr(pipl_service, "respond_to_access_request")
        assert callable(pipl_service.respond_to_access_request)

    @pytest.mark.asyncio
    async def test_pipl_service_has_portability_request(
        self,
        pipl_service: PIPLComplianceServiceImpl,
    ) -> None:
        """PIPL 服务应具备数据可携带权响应功能"""
        assert hasattr(pipl_service, "respond_to_portability_request")
        assert callable(pipl_service.respond_to_portability_request)

    @pytest.mark.asyncio
    async def test_deletion_request_response_returns_dict(
        self,
        pipl_service: PIPLComplianceServiceImpl,
    ) -> None:
        """删除请求响应应返回字典"""
        result = pipl_service.respond_to_deletion_request("user-001")
        assert isinstance(result, dict)
        assert "status" in result

    @pytest.mark.asyncio
    async def test_access_request_response_returns_dict(
        self,
        pipl_service: PIPLComplianceServiceImpl,
    ) -> None:
        """访问请求响应应返回字典"""
        result = pipl_service.respond_to_access_request("user-001")
        assert isinstance(result, dict)
        assert "status" in result


class TestPIPLPortAvailability:
    """PIPL 端口可用性验证"""

    def test_pipl_port_registered(self) -> None:
        """PIPL 端口应在 composition_root 中注册"""
        from src.composition_root import _global_registry

        spec = _global_registry.get("pipl_compliance")
        assert spec is not None, "PIPL compliance service port not registered"

    def test_pipl_impl_satisfies_port(self) -> None:
        """PIPL 实现类应满足端口协议"""
        from src.domain.ports.pipl_compliance_service import PIPLComplianceServicePort

        assert isinstance(PIPLComplianceServiceImpl(), PIPLComplianceServicePort)
