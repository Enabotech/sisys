"""Story 3.8 高保真溯源 API 契约测试

验证 API 端点的路由、请求/响应 Schema 和认证中间件。
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.domain.ports.traceability import TraceabilityResult
from src.domain.value_objects.citation import Citation


class TestTraceAPIEndpoint:
    """POST /api/v1/search/trace 端点测试"""

    def _make_app(self) -> FastAPI:
        """创建 FastAPI 应用并注册溯源路由"""
        from src.interfaces.api.traceability import create_trace_router

        app = FastAPI()
        router = create_trace_router(
            trace_service=MockTraceService(),
            get_current_user_override=lambda: "test-user",
        )
        app.include_router(router)
        return app

    def test_post_trace_returns_200(self) -> None:
        """POST /api/v1/search/trace 返回 200"""
        client = TestClient(self._make_app(), raise_server_exceptions=False)
        response = client.post(
            "/api/v1/search/trace",
            json={"claim": "测试结论文本"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_post_trace_response_structure(self) -> None:
        """POST /api/v1/search/trace 响应体结构完整"""
        client = TestClient(self._make_app(), raise_server_exceptions=False)
        response = client.post(
            "/api/v1/search/trace",
            json={"claim": "测试结论文本"},
            headers={"Authorization": "Bearer test-token"},
        )
        data = response.json()
        assert "claim" in data
        assert "citations" in data
        assert "citation_count" in data
        assert "highest_confidence" in data
        assert "has_bbox_support" in data

    def test_post_trace_missing_claim_returns_422(self) -> None:
        """缺少 claim 字段返回 422"""
        client = TestClient(self._make_app(), raise_server_exceptions=False)
        response = client.post(
            "/api/v1/search/trace",
            json={},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_post_trace_empty_claim_returns_422(self) -> None:
        """空 claim 字段返回 422"""
        client = TestClient(self._make_app(), raise_server_exceptions=False)
        response = client.post(
            "/api/v1/search/trace",
            json={"claim": ""},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_post_trace_with_optional_params(self) -> None:
        """POST /api/v1/search/trace 接受可选参数"""
        client = TestClient(self._make_app(), raise_server_exceptions=False)
        response = client.post(
            "/api/v1/search/trace",
            json={"claim": "测试结论", "top_k": 5, "min_confidence": 0.8},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == status.HTTP_200_OK


class TestTraceByDocumentAPIEndpoint:
    """GET /api/v1/search/trace/{document_id} 端点测试"""

    def _make_app(self) -> FastAPI:
        """创建 FastAPI 应用并注册溯源路由"""
        from src.interfaces.api.traceability import create_trace_router

        app = FastAPI()
        router = create_trace_router(
            trace_service=MockTraceService(),
            get_current_user_override=lambda: "test-user",
        )
        app.include_router(router)
        return app

    def test_get_trace_by_document_returns_200(self) -> None:
        """GET /api/v1/search/trace/{document_id} 返回 200"""
        client = TestClient(self._make_app(), raise_server_exceptions=False)
        doc_id = str(uuid.uuid4())
        response = client.get(
            f"/api/v1/search/trace/{doc_id}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_get_trace_by_document_response_structure(self) -> None:
        """GET /api/v1/search/trace/{document_id} 响应体结构完整"""
        client = TestClient(self._make_app(), raise_server_exceptions=False)
        doc_id = str(uuid.uuid4())
        response = client.get(
            f"/api/v1/search/trace/{doc_id}",
            headers={"Authorization": "Bearer test-token"},
        )
        data = response.json()
        assert "document_id" in data
        assert "citations" in data
        assert "citation_count" in data


class TestTraceAuthentication:
    """认证中间件测试"""

    def _make_app(self) -> FastAPI:
        """创建 FastAPI 应用"""
        from src.interfaces.api.traceability import create_trace_router

        app = FastAPI()
        router = create_trace_router(
            trace_service=MockTraceService(),
        )
        app.include_router(router)
        return app

    def test_post_trace_without_auth_returns_401(self) -> None:
        """无认证请求返回 401"""
        client = TestClient(self._make_app(), raise_server_exceptions=False)
        response = client.post(
            "/api/v1/search/trace",
            json={"claim": "测试结论"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class MockTraceService:
    """用于 API 端点测试的 Mock TraceabilityService"""

    async def trace(
        self,
        claim: str,
        top_k: int = 10,
        min_confidence: float = 0.7,
    ) -> TraceabilityResult:
        from src.domain.value_objects.parsed_document import BoundingBox

        return TraceabilityResult(
            claim=claim,
            citations=[
                Citation(
                    citation_id="citation-001",
                    document_id=uuid.uuid4(),
                    chunk_id="chunk-001",
                    text="公司2024年营收同比增长15%。",
                    start_offset=0,
                    end_offset=15,
                    page_number=3,
                    bbox=BoundingBox(x=100.5, y=200.3, width=400.0, height=50.0, page=3),
                    confidence=0.92,
                ),
            ],
            citation_count=1,
            highest_confidence=0.92,
            has_bbox_support=True,
        )

    async def get_citation_detail(self, citation_id: str) -> Citation:
        raise NotImplementedError("API 契约测试不需要实现此方法")

    async def get_citation_by_document(self, document_id: uuid.UUID) -> list:
        from src.domain.value_objects.citation import Citation
        from src.domain.value_objects.parsed_document import BoundingBox

        return [
            Citation(
                citation_id="citation-001",
                document_id=document_id,
                chunk_id="chunk-001",
                text="公司2024年营收同比增长15%。",
                start_offset=0,
                end_offset=15,
                page_number=3,
                bbox=BoundingBox(x=100.5, y=200.3, width=400.0, height=50.0, page=3),
                confidence=0.92,
            ),
        ]
