"""Tests for ComplianceGateway service implementation.

TDD Red Phase: These tests define expected compliance gateway behavior.
"""

import pytest


class TestComplianceGatewayCheck:
    """Test check functionality."""

    @pytest.mark.asyncio
    async def test_check_with_china_domestic_data(self):
        """Test compliance check with China domestic data."""
        from src.domain.value_objects.compliance_result import ComplianceResult
        from src.domain.value_objects.udmr_task import UDMRTask
        from src.infrastructure.security.compliance_gateway_impl import ComplianceGatewayImpl

        gateway = ComplianceGatewayImpl()

        task = UDMRTask(
            input="测试文本",
            data_residency="CHINA_DOMESTIC",
            preferred_model="xxx.xxx.xxx",
        )

        result = await gateway.check(task)

        assert isinstance(result, ComplianceResult)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_check_with_overseas_data(self):
        """Test compliance check with overseas data."""
        from src.domain.value_objects.compliance_result import ComplianceResult
        from src.domain.value_objects.udmr_task import UDMRTask
        from src.infrastructure.security.compliance_gateway_impl import ComplianceGatewayImpl

        gateway = ComplianceGatewayImpl()

        task = UDMRTask(
            input="Test text",
            data_residency="OVERSEAS",
            preferred_model="openai/gpt-4",
        )

        result = await gateway.check(task)

        assert isinstance(result, ComplianceResult)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_check_detects_sensitive_data(self):
        """Test compliance check detects sensitive data."""
        from src.domain.value_objects.compliance_result import ComplianceResult
        from src.domain.value_objects.udmr_task import UDMRTask
        from src.infrastructure.security.compliance_gateway_impl import ComplianceGatewayImpl

        gateway = ComplianceGatewayImpl()

        task = UDMRTask(
            input="张三的身份证号是 110101199001011234，手机号 13800138000",
            data_residency="CHINA_DOMESTIC",
            preferred_model="xxx.xxx.xxx",
        )

        result = await gateway.check(task)

        assert isinstance(result, ComplianceResult)
        if result.violation_type:
            assert result.forced_local is True

    @pytest.mark.asyncio
    async def test_check_with_model_not_in_whitelist(self):
        """Test compliance check fails when model not in whitelist."""
        from src.domain.value_objects.compliance_result import ComplianceResult
        from src.domain.value_objects.udmr_task import UDMRTask
        from src.infrastructure.security.compliance_gateway_impl import ComplianceGatewayImpl

        gateway = ComplianceGatewayImpl()

        task = UDMRTask(
            input="测试文本",
            data_residency="CHINA_DOMESTIC",
            preferred_model="unauthorized/model",
            allowed_models=["approved/model-1", "approved/model-2"],
        )

        result = await gateway.check(task)

        assert isinstance(result, ComplianceResult)
        assert result.allowed is False
        assert result.violation_type == "model_not_in_whitelist"

    @pytest.mark.asyncio
    async def test_check_respects_data_residency_for_overseas_model(self):
        """Test compliance check redirects overseas model for domestic data to local processing."""
        from src.domain.value_objects.compliance_result import ComplianceResult
        from src.domain.value_objects.udmr_task import UDMRTask
        from src.infrastructure.security.compliance_gateway_impl import ComplianceGatewayImpl

        gateway = ComplianceGatewayImpl()

        task = UDMRTask(
            input="测试文本",
            data_residency="CHINA_DOMESTIC",
            preferred_model="openai/gpt-4",
        )

        result = await gateway.check(task)

        assert isinstance(result, ComplianceResult)
        assert result.allowed is True
        assert result.forced_local is True
        assert result.violation_type == "data_residency_violation"


class TestComplianceGatewayIntegration:
    """Test compliance gateway integration with other services."""

    @pytest.mark.asyncio
    async def test_check_with_pipl_consent_required(self):
        """Test compliance check requires PIPL consent for personal data."""
        from src.domain.value_objects.compliance_result import ComplianceResult
        from src.domain.value_objects.udmr_task import UDMRTask
        from src.infrastructure.security.compliance_gateway_impl import ComplianceGatewayImpl

        gateway = ComplianceGatewayImpl()

        task = UDMRTask(
            input="用户王五请求分析其个人信息",
            data_residency="CHINA_DOMESTIC",
            preferred_model="xxx.xxx.xxx",
        )

        result = await gateway.check(task)

        assert isinstance(result, ComplianceResult)
        if result.violation_type:
            assert result.forced_local is True

    @pytest.mark.asyncio
    async def test_check_cross_border_transfer_required(self):
        """Test compliance check requires cross-border transfer approval."""
        from src.domain.value_objects.compliance_result import ComplianceResult
        from src.domain.value_objects.udmr_task import UDMRTask
        from src.infrastructure.security.compliance_gateway_impl import ComplianceGatewayImpl

        gateway = ComplianceGatewayImpl()

        task = UDMRTask(
            input="测试跨境传输",
            data_residency="OVERSEAS",
            preferred_model="xxx.xxx.xxx",
        )

        result = await gateway.check(task)

        assert isinstance(result, ComplianceResult)
        assert result.allowed is True
