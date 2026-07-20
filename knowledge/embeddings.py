"""Embedding 管理：统一接口，支持切换模型后端"""

from abc import ABC, abstractmethod
from typing import List

from .config import config
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseEmbedding(ABC):
    """Embedding 基类"""

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        ...

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        ...


class DefaultEmbedding(BaseEmbedding):
    """使用 ChromaDB 内置的 all-MiniLM-L6-v2"""

    def __init__(self):
        self._embedding_function = None

    def _get_fn(self):
        if self._embedding_function is None:
            try:
                import chromadb.utils.embedding_functions as ef
                self._embedding_function = ef.DefaultEmbeddingFunction()
                logger.info("Embedding: ChromaDB 内置模型")
            except Exception as e:
                logger.error("加载内置 Embedding 失败: %s", e)
                raise
        return self._embedding_function

    def embed_query(self, text: str) -> List[float]:
        fn = self._get_fn()
        return fn([text])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        fn = self._get_fn()
        return fn(texts)


# ── 预留：sentence-transformers 本地模型 ──
# class SentenceTransformerEmbedding(BaseEmbedding):
#     def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
#         from sentence_transformers import SentenceTransformer
#         self.model = SentenceTransformer(model_name)
#
#     def embed_query(self, text: str) -> List[float]:
#         return self.model.encode(text).tolist()
#
#     def embed_documents(self, texts: List[str]) -> List[List[float]]:
#         return self.model.encode(texts).tolist()


def get_embedding() -> BaseEmbedding:
    """工厂方法"""
    model_type = config.EMBEDDING_MODEL
    if model_type == "default":
        return DefaultEmbedding()
    # elif model_type == "sentence-transformers":
    #     return SentenceTransformerEmbedding()
    raise ValueError(f"不支持的 Embedding 类型: {model_type}")
