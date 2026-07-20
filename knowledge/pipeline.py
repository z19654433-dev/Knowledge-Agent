"""RAG 流程编排：文档索引 + 检索生成"""

from typing import List
from pathlib import Path

from .config import config
from .loader import load_directory, Document
from .chunker import RecursiveChunker
from .vector_store import get_vector_store
from .retriever import get_retriever
from utils.logger import get_logger

logger = get_logger(__name__)


def index_documents(doc_dir: str | None = None) -> int:
    """索引文档：加载 → 切片 → 向量化 → 存储

    Args:
        doc_dir: 文档目录，默认使用配置中的 DOCS_DIR

    Returns:
        成功入库的切片数量
    """
    doc_dir = doc_dir or config.DOCS_DIR
    logger.info("开始索引文档: %s", doc_dir)

    # 1. 加载文档
    docs = load_directory(doc_dir)
    if not docs:
        logger.warning("未找到可索引的文档")
        return 0

    # 2. 切片
    chunker = RecursiveChunker()
    store = get_vector_store()

    all_ids = []
    all_docs = []
    all_metas = []
    counter = 0

    for doc in docs:
        chunks = chunker.chunk(doc.content)
        for chunk in chunks:
            all_ids.append(f"doc_{counter}")
            all_docs.append(chunk)
            all_metas.append(doc.metadata or {})
            counter += 1

    # 3. 向量化 + 存储
    store.add(ids=all_ids, documents=all_docs, metadatas=all_metas)
    logger.info("文档索引完成: %d 个切片入库", len(all_ids))
    return len(all_ids)


def query(question: str, top_k: int | None = None) -> str:
    """RAG 查询：检索 → 生成回答

    Args:
        question: 用户问题
        top_k: 检索返回的片段数量

    Returns:
        检索到的相关内容（供 LLM 生成最终回答）
        如知识库为空则返回提示信息
    """
    store = get_vector_store()
    if store.count() == 0:
        logger.info("知识库为空，尝试自动索引")
        n = index_documents()
        if n == 0:
            return "知识库中暂无内容，请先往 knowledge/docs/ 目录添加文档"

    retriever = get_retriever()
    results = retriever.search(question, k=top_k)
    context = retriever.format_context(results)

    if not context:
        return "知识库中没有找到相关内容"

    return context
