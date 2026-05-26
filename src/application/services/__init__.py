"""应用层服务包

Public API:
- UnifiedStorageGateway: L0-L5 六层统一存储网关
"""

from src.application.services.unified_storage_gateway import UnifiedStorageGateway

__all__ = [
    "UnifiedStorageGateway",
]
