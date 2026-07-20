"""文本切片策略：递归切片 / 定长切片"""

from abc import ABC, abstractmethod
from typing import List

from .config import config


class BaseChunker(ABC):
    """切片器基类"""

    @abstractmethod
    def chunk(self, text: str) -> List[str]:
        ...


class RecursiveChunker(BaseChunker):
    """递归切片：按标题 → 段落 → 句子逐级切，尽量保持语义完整"""

    def __init__(self, chunk_size: int | None = None, overlap: int | None = None):
        self.chunk_size = chunk_size or config.CHUNK_SIZE
        self.overlap = overlap or config.CHUNK_OVERLAP

    def chunk(self, text: str) -> List[str]:
        # 第一级：按 Markdown 标题切
        import re
        sections = re.split(r"\n(?=#{1,6}\s)", text.strip())

        chunks = []
        buffer = ""
        for section in sections:
            if len(buffer) + len(section) < self.chunk_size:
                buffer = (buffer + "\n\n" + section).strip()
            else:
                if buffer:
                    chunks.append(buffer)
                # 如果单节超过 chunk_size，按句号切
                if len(section) > self.chunk_size:
                    sentences = [s.strip() for s in re.split(r"[。！？!?]", section) if s.strip()]
                    for sent in sentences:
                        if len(buffer) + len(sent) < self.chunk_size:
                            buffer = (buffer + sent).strip()
                        else:
                            if buffer:
                                chunks.append(buffer)
                            buffer = sent
                else:
                    buffer = section

        if buffer:
            chunks.append(buffer)

        return chunks


class FixedSizeChunker(BaseChunker):
    """定长切片 + 重叠"""

    def __init__(self, chunk_size: int | None = None, overlap: int | None = None):
        self.chunk_size = chunk_size or config.CHUNK_SIZE
        self.overlap = overlap or config.CHUNK_OVERLAP

    def chunk(self, text: str) -> List[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            start += self.chunk_size - self.overlap
        return chunks


def get_chunker(strategy: str = "recursive") -> BaseChunker:
    """工厂方法"""
    if strategy == "fixed":
        return FixedSizeChunker()
    return RecursiveChunker()
