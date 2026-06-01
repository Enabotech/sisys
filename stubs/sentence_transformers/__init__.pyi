"""sentence_transformers 类型存根

为 sentence_transformers 库提供最小化类型定义，覆盖 BGE3EmbeddingService 使用的方法
"""

from typing import Any

import numpy as np
from numpy.typing import NDArray

class SentenceTransformer:
    """SentenceTransformer 类型存根"""

    def __init__(
        self,
        model_name_or_path: str,
        device: str | None = None,
        **kwargs: Any,
    ) -> None: ...
    def encode(
        self,
        sentences: str | list[str],
        normalize_embeddings: bool = False,
        **kwargs: Any,
    ) -> NDArray[np.float32]: ...
    def get_sentence_embedding_dimension(self) -> int: ...
