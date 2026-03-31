"""
sisys - Not Found Error Tests.

测试领域层未找到错误异常。
"""


from src.domain.exceptions.not_found_error import NotFoundError


class TestNotFoundError:
    """测试 NotFoundError 异常类"""

    def test_init_with_entity_type_and_id(self):
        """Given 实体类型和 ID，When 创建异常，Then 使用默认消息格式"""
        error = NotFoundError(entity_type="PlanRepository", entity_id="123")

        assert error.entity_type == "PlanRepository"
        assert error.entity_id == "123"
        assert "PlanRepository" in str(error)
        assert "123" in str(error)
        assert error.code == "NOT_FOUND"

    def test_init_with_custom_message(self):
        """Given 自定义消息，When 创建异常，Then 使用自定义消息"""
        custom_msg = "PlanRepository with id 123 not found"
        error = NotFoundError(message=custom_msg)

        assert str(error) == custom_msg
        assert error.code == "NOT_FOUND"
        # 即使使用自定义消息，属性也应存在
        assert error.entity_type == "Unknown"
        assert error.entity_id == "Unknown"

    def test_init_with_no_args(self):
        """Given 无参数，When 创建异常，Then 使用默认消息"""
        error = NotFoundError()

        assert str(error) == "Resource not found"
        assert error.code == "NOT_FOUND"
        assert error.entity_type == "Unknown"
        assert error.entity_id == "Unknown"

    def test_init_with_only_entity_type(self):
        """Given 只有实体类型，When 创建异常，Then 使用默认消息"""
        error = NotFoundError(entity_type="PlanRepository")

        assert str(error) == "Resource not found"
        assert error.entity_type == "Unknown"
        assert error.entity_id == "Unknown"

    def test_init_with_only_entity_id(self):
        """Given 只有实体 ID，When 创建异常，Then 使用默认消息"""
        error = NotFoundError(entity_id="123")

        assert str(error) == "Resource not found"
        assert error.entity_type == "Unknown"
        assert error.entity_id == "Unknown"

    def test_entity_type_property(self):
        """Given 实体类型属性，When 访问，Then 返回正确值"""
        error = NotFoundError(entity_type="StrategicPlan", entity_id="456")

        assert error.entity_type == "StrategicPlan"

    def test_entity_id_property(self):
        """Given 实体 ID 属性，When 访问，Then 返回正确值"""
        error = NotFoundError(entity_type="StrategicPlan", entity_id="456")

        assert error.entity_id == "456"

    def test_inherits_from_domain_error(self):
        """Given NotFoundError，When 检查继承，Then 继承自 DomainError"""
        from src.domain.exceptions.base import DomainError

        error = NotFoundError(entity_type="Test", entity_id="1")

        assert isinstance(error, DomainError)
        assert isinstance(error, Exception)

    def test_str_representation(self):
        """Given 异常实例，When 转换为字符串，Then 返回消息"""
        error = NotFoundError(entity_type="Plan", entity_id="999")

        assert str(error) == "Plan 未找到 (ID: 999)"

    def test_custom_message_takes_precedence(self):
        """Given 自定义消息和实体信息，When 创建异常，Then 优先使用自定义消息"""
        error = NotFoundError(
            entity_type="IgnoredType",
            entity_id="999",
            message="Custom error message",
        )

        assert str(error) == "Custom error message"
        # 实体属性仍应设置为提供的值
        assert error.entity_type == "IgnoredType"
        assert error.entity_id == "999"
