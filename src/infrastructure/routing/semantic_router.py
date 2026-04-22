"""SemanticRouter — semantic similarity-based routing using bge-m3 embeddings."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol


class EmbeddingModelProtocol(Protocol):
    """Protocol for embedding model (implemented by infrastructure)."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (each vector is a list of floats)
        """
        ...


@dataclass
class Candidate:
    """Represents a routing candidate (Agent or tool)."""

    candidate_id: str
    name: str
    description: str
    embedding: list[float]


class SemanticRouter:
    """Semantic router using bge-m3 embeddings for task-to-target matching.

    Computes cosine similarity between task context embedding and candidate embeddings
    to find the best matching target.

    Requires:
    - EmbeddingModelProtocol: For computing task context embedding (optional)
    """

    # Default embedding dimension for bge-m3
    DEFAULT_EMBEDDING_DIM: int = 1024

    # Max cache size to prevent memory issues
    MAX_CACHE_SIZE: int = 10000

    def __init__(
        self,
        candidates: Sequence[Candidate] | None = None,
        embedding_model: EmbeddingModelProtocol | None = None,
        cache_ttl_seconds: int = 86400,  # 24 hours (used for cache size limit, not expiry)
    ):
        """Initialize SemanticRouter.

        Args:
            candidates: Initial list of routing candidates (Agents/tools). None creates empty router.
            embedding_model: Embedding model port for computing task embeddings (optional).
            cache_ttl_seconds: TTL for in-memory cache (default: 24 hours, used for size limit).
        """
        self._candidates = {c.candidate_id: c for c in candidates} if candidates else {}
        self._embedding_model = embedding_model
        self._cache_ttl = cache_ttl_seconds
        self._embedding_cache: dict[str, list[float]] = {}  # Simple in-memory cache

    def add_candidate(self, candidate: Candidate) -> None:
        """Add a routing candidate.

        Args:
            candidate: Candidate to add (Agent or tool)
        """
        self._candidates[candidate.candidate_id] = candidate

    def remove_candidate(self, candidate_id: str) -> None:
        """Remove a routing candidate.

        Args:
            candidate_id: ID of candidate to remove
        """
        self._candidates.pop(candidate_id, None)

    async def route(self, task_context: dict[str, Any]) -> tuple[str, float]:
        """Route a task to the best matching candidate based on semantic similarity.

        Args:
            task_context: Task context dictionary with at least 'task_type' or 'description' field

        Returns:
            Tuple of (candidate_id, similarity_score)
            Returns ("", 0.0) if no candidates available.
        """
        if not self._candidates:
            return "", 0.0

        # Extract task description from context
        task_description = self._extract_task_description(task_context)
        if not task_description:
            return "", 0.0

        # Get task embedding
        task_embedding = await self._get_task_embedding(task_description)

        # Compute similarity with all candidates
        best_candidate_id = ""
        best_score = 0.0

        for candidate_id, candidate in self._candidates.items():
            score = self._cosine_similarity(task_embedding, candidate.embedding)
            if score > best_score:
                best_score = score
                best_candidate_id = candidate_id

        # If all scores are 0 (no embedding model or no match), return first candidate
        if not best_candidate_id and self._candidates:
            first_candidate_id = next(iter(self._candidates))
            return first_candidate_id, 0.0

        return best_candidate_id, best_score

    def _extract_task_description(self, task_context: dict[str, Any]) -> str:
        """Extract a description string from task context.

        Args:
            task_context: Task context dictionary

        Returns:
            Description string, or empty string if no description found
        """
        # Priority order for description fields
        for key in ("description", "task_description", "task_type", "name", "prompt"):
            if key in task_context and task_context[key]:
                value = task_context[key]
                if isinstance(value, str):
                    return value
                if isinstance(value, list | dict):
                    # For complex types, stringify
                    return str(value)
        return ""

    async def _get_task_embedding(self, text: str) -> list[float]:
        """Get embedding for task text, with in-memory caching.

        Args:
            text: Task text to embed

        Returns:
            Embedding vector
        """
        # Check in-memory cache first
        if text in self._embedding_cache:
            return self._embedding_cache[text]

        # Compute embedding
        if self._embedding_model is None:
            # No embedding model, return zeros (will result in 0 similarity)
            embedding = [0.0] * self.DEFAULT_EMBEDDING_DIM
        else:
            embeddings = await self._embedding_model.embed([text])
            embedding = embeddings[0] if embeddings else [0.0] * self.DEFAULT_EMBEDDING_DIM

        # Cache the result (simple LRU-like eviction if cache is full)
        if len(self._embedding_cache) < self.MAX_CACHE_SIZE:
            self._embedding_cache[text] = embedding

        return embedding

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            a: First vector
            b: Second vector

        Returns:
            Similarity score between -1 and 1 (0 if vectors have zero magnitude)
        """
        if not a or not b:
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = math.sqrt(sum(x * x for x in a))
        magnitude_b = math.sqrt(sum(x * x for x in b))

        if magnitude_a == 0.0 or magnitude_b == 0.0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)

    @property
    def candidate_count(self) -> int:
        """Return the number of candidates."""
        return len(self._candidates)
