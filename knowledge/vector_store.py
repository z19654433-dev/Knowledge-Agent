"""向量存储 —— 基于 LangChain Chroma 封装"""

from pathlib import Path
from typing import List

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever

from .config import config
from .embeddings import get_embedding
from .embeddings import get_embedding
from utils.logger import get_logger

logger = get_logger(__name__)


class VectorStore:
    """向量数据库封装"""

    def __init__(self):
        persist_dir = Path(config.VECTOR_DB_DIR)
        persist_dir.mkdir(parents=True, exist_ok=True)

        embedding = get_embedding()
        self._store = Chroma(
            collection_name=config.COLLECTION_NAME,
            embedding_function=embedding,
            persist_directory=str(persist_dir),
        )
        self._retriever: VectorStoreRetriever | None = None
        logger.info("向量库初始化完成, 文档数=%d", self._store._collection.count())

    # ── 写入 ──

    def add_documents(self, documents: List[Document]) -> int:
        """批量写入文档"""
        ids = self._store.add_documents(documents)
        logger.info("向量库写入 %d 条", len(documents))
        # 清除缓存检索器
        self._retriever = None
        return len(ids)

    # ── 检索 ──

    def get_retriever(self, k: int | None = None) -> VectorStoreRetriever:
        """获取 LangChain Retriever"""
        if self._retriever is None or k:
            self._retriever = self._store.as_retriever(
                search_kwargs={"k": k or config.RETRIEVE_TOP_K},
            )
        return self._retriever

    def search(self, query: str, k: int | None = None) -> List[Document]:
        """语义检索，返回 Document 列表"""
        retriever = self.get_retriever(k)
        docs = retriever.invoke(query)
        return docs

    # ── 管理 ──

    def count(self) -> int:
        return self._store._collection.count()

    def delete_all(self):
        import gc
        # 删除旧 collection
        self._store.delete_collection()
        self._retriever = None
        # 重建 Chroma 实例
        embedding = get_embedding()
        self._store = Chroma(
            collection_name=config.COLLECTION_NAME,
            embedding_function=embedding,
            persist_directory=str(Path(config.VECTOR_DB_DIR)),
        )
        logger.info("向量库已清空并重建")


_store_instance: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = VectorStore()
    return _store_instance
