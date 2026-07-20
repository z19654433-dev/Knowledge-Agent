"""向量数据库：抽象接口 + ChromaDB 实现"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pathlib import Path

import chromadb

from .config import config
from .embeddings import get_embedding
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseVectorStore(ABC):
    """向量数据库抽象接口"""

    @abstractmethod
    def add(self, ids: List[str], documents: List[str], metadatas: List[Dict] | None = None):
        ...

    @abstractmethod
    def search(self, query: str, k: int | None = None) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def count(self) -> int:
        ...

    @abstractmethod
    def delete_collection(self):
        ...


class ChromaStore(BaseVectorStore):
    """ChromaDB 实现"""

    def __init__(self):
        persist_dir = Path(config.VECTOR_DB_DIR)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._embedding_fn = get_embedding()._get_fn()

        self._collection = self._client.get_or_create_collection(
            name=config.COLLECTION_NAME,
            embedding_function=self._embedding_fn,
        )
        logger.info("ChromaDB 初始化完成, 文档数=%d", self._collection.count())

    def add(self, ids: List[str], documents: List[str], metadatas: List[Dict] | None = None):
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            end = i + batch_size
            self._collection.add(
                ids=ids[i:end],
                documents=documents[i:end],
                metadatas=metadatas[i:end] if metadatas else None,
            )

    def search(self, query: str, k: int | None = None) -> List[Dict[str, Any]]:
        top_k = k or config.RETRIEVE_TOP_K
        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
        )
        items = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                items.append({
                    "content": doc,
                    "metadata": (results["metadatas"][0][i] if results["metadatas"] else {}),
                    "score": results["distances"][0][i] if results.get("distances") else 0,
                })
        return items

    def count(self) -> int:
        return self._collection.count()

    def delete_collection(self):
        self._client.delete_collection(config.COLLECTION_NAME)
        self._collection = self._client.create_collection(
            name=config.COLLECTION_NAME,
            embedding_function=self._embedding_fn,
        )
        logger.info("知识库已清空")


# ── 工厂 ──

_store_instance = None


def get_vector_store() -> BaseVectorStore:
    """全局单例：获取向量数据库实例"""
    global _store_instance
    if _store_instance is None:
        _store_instance = ChromaStore()
    return _store_instance
