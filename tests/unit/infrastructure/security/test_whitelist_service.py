"""Tests for WhitelistService service implementation.

TDD Red Phase: These tests define expected whitelist management behavior.
"""

from datetime import UTC, timedelta


class TestWhitelistServiceIsAllowed:
    """Test is_allowed functionality."""

    def test_is_allowed_verified_and_valid(self):
        """Test is_allowed returns True for verified and valid entry."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel
        from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

        service = WhitelistServiceImpl()

        # Add a verified, valid entry
        entry = ExternalAPIWhitelist(
            endpoint="https://api.domestic.cn",
            provider="DomesticProvider",
            region="CHINA_DOMESTIC",
            is_verified=True,
            risk_level=RiskLevel.LOW,
            valid_from=datetime.now(UTC) - timedelta(days=1),
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )
        service.add_to_whitelist(entry)

        result = service.is_allowed("https://api.domestic.cn")
        assert result is True

    def test_is_allowed_not_verified(self):
        """Test is_allowed returns False for unverified entry."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel
        from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

        service = WhitelistServiceImpl()

        entry = ExternalAPIWhitelist(
            endpoint="https://api.unverified.com",
            is_verified=False,
            risk_level=RiskLevel.MEDIUM,
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )
        service.add_to_whitelist(entry)

        result = service.is_allowed("https://api.unverified.com")
        assert result is False

    def test_is_allowed_expired(self):
        """Test is_allowed returns False for expired entry."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel
        from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

        service = WhitelistServiceImpl()

        entry = ExternalAPIWhitelist(
            endpoint="https://api.expired.com",
            is_verified=True,
            risk_level=RiskLevel.LOW,
            valid_from=datetime.now(UTC) - timedelta(days=60),
            valid_until=datetime.now(UTC) - timedelta(days=1),
        )
        service.add_to_whitelist(entry)

        result = service.is_allowed("https://api.expired.com")
        assert result is False

    def test_is_allowed_not_in_whitelist(self):
        """Test is_allowed returns False for endpoint not in whitelist."""
        from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

        service = WhitelistServiceImpl()
        result = service.is_allowed("https://api.unknown.com")
        assert result is False


class TestWhitelistServiceCRUD:
    """Test whitelist CRUD operations."""

    def test_add_to_whitelist(self):
        """Test adding entry to whitelist."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel
        from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

        service = WhitelistServiceImpl()

        entry = ExternalAPIWhitelist(
            endpoint="https://api.new.com",
            provider="NewProvider",
            region="CHINA_DOMESTIC",
            is_verified=True,
            risk_level=RiskLevel.LOW,
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )

        service.add_to_whitelist(entry)

        # Verify it's in the whitelist
        result = service.is_allowed("https://api.new.com")
        assert result is True

    def test_whitelist_stores_multiple_entries(self):
        """Test whitelist can store multiple entries."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel
        from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

        service = WhitelistServiceImpl()

        entry1 = ExternalAPIWhitelist(
            endpoint="https://api.first.com",
            is_verified=True,
            risk_level=RiskLevel.LOW,
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )
        entry2 = ExternalAPIWhitelist(
            endpoint="https://api.second.com",
            is_verified=True,
            risk_level=RiskLevel.MEDIUM,
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )

        service.add_to_whitelist(entry1)
        service.add_to_whitelist(entry2)

        assert service.is_allowed("https://api.first.com") is True
        assert service.is_allowed("https://api.second.com") is True
        assert service.is_allowed("https://api.third.com") is False


class TestWhitelistServiceHighRisk:
    """Test high-risk API handling."""

    def test_high_risk_requires_dpo_approval(self):
        """Test high-risk API identification."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel
        from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

        service = WhitelistServiceImpl()

        entry = ExternalAPIWhitelist(
            endpoint="https://api.highrisk.com",
            is_verified=True,
            risk_level=RiskLevel.HIGH,
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )
        service.add_to_whitelist(entry)

        # High risk should still be valid (DPO approval is a separate process)
        result = service.is_allowed("https://api.highrisk.com")
        assert result is True

    def test_medium_risk_auto_approved(self):
        """Test medium risk API is auto-approved."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel
        from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

        service = WhitelistServiceImpl()

        entry = ExternalAPIWhitelist(
            endpoint="https://api.medium.com",
            is_verified=True,
            risk_level=RiskLevel.MEDIUM,
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )
        service.add_to_whitelist(entry)

        result = service.is_allowed("https://api.medium.com")
        assert result is True


class TestWhitelistServiceGetEntry:
    """Test get_whitelist_entry."""

    def test_get_existing_entry(self):
        """获取已存在的白名单条目."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel
        from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

        service = WhitelistServiceImpl()
        entry = ExternalAPIWhitelist(
            endpoint="https://api.test.com",
            is_verified=True,
            risk_level=RiskLevel.LOW,
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )
        service.add_to_whitelist(entry)

        result = service.get_whitelist_entry("https://api.test.com")
        assert result is not None
        assert result.endpoint == "https://api.test.com"

    def test_get_nonexistent_entry_returns_none(self):
        """获取不存在的条目应返回 None."""
        from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

        service = WhitelistServiceImpl()
        result = service.get_whitelist_entry("https://api.nonexistent.com")
        assert result is None


class TestWhitelistServiceRemove:
    """Test remove_from_whitelist."""

    def test_remove_existing_entry(self):
        """移除已存在的条目应返回 True."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel
        from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

        service = WhitelistServiceImpl()
        entry = ExternalAPIWhitelist(
            endpoint="https://api.to-remove.com",
            is_verified=True,
            risk_level=RiskLevel.LOW,
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )
        service.add_to_whitelist(entry)

        result = service.remove_from_whitelist("https://api.to-remove.com")
        assert result is True
        assert service.is_allowed("https://api.to-remove.com") is False

    def test_remove_nonexistent_entry_returns_false(self):
        """移除不存在的条目应返回 False."""
        from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

        service = WhitelistServiceImpl()
        result = service.remove_from_whitelist("https://api.nonexistent.com")
        assert result is False


class TestWhitelistServiceListEndpoints:
    """Test list_all_endpoints."""

    def test_list_empty(self):
        """空白名单应返回空列表."""
        from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

        service = WhitelistServiceImpl()
        result = service.list_all_endpoints()
        assert result == []

    def test_list_all_endpoints(self):
        """应返回所有已添加的端点."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel
        from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

        service = WhitelistServiceImpl()
        entry1 = ExternalAPIWhitelist(
            endpoint="https://api.one.com",
            is_verified=True,
            risk_level=RiskLevel.LOW,
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )
        entry2 = ExternalAPIWhitelist(
            endpoint="https://api.two.com",
            is_verified=True,
            risk_level=RiskLevel.MEDIUM,
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )
        service.add_to_whitelist(entry1)
        service.add_to_whitelist(entry2)

        endpoints = service.list_all_endpoints()
        assert sorted(endpoints) == sorted(["https://api.one.com", "https://api.two.com"])
