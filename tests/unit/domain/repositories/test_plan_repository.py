"""
sisys - Plan Repository Tests.

测试仓储层接口定义。
"""


from src.domain.repositories.plan_repository import PlanRepository


class TestPlanRepositoryProtocol:
    """测试 PlanRepository 协议接口"""

    def test_protocol_exists(self):
        """Given PlanRepository 协议，When 导入，Then 存在"""
        assert PlanRepository is not None

    def test_protocol_has_required_methods(self):
        """Given PlanRepository 协议，When 检查，Then 包含所有必需方法"""
        required_methods = ["get_by_id", "find_all", "add", "update", "delete"]
        for method in required_methods:
            assert hasattr(PlanRepository, method)
