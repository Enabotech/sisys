from typing import Any

class Tokenizer:
    """BGE-M3 tokenizer 类型存根（仅覆盖项目实际使用的 API）"""

    @staticmethod
    def from_file(path: str) -> "Tokenizer": ...
    def encode(self, text: str) -> Any: ...
    @property
    def ids(self) -> list[int]: ...
