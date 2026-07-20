"""检索策略：语义检索，预留混合检索扩展点"""

from typing import List, Dict, Any

from .vector_store import get_vector_store, BaseVectorStore
from .config import config
from utils.logger import get_logger

logger = get_logger(__name__)


class Retriever:
    """检索器：封装检索逻辑"""

    def __init__(self, store: BaseVectorStore | None = None):
        self.store = store or get_vector_store()

    def search(self, query: str, k: int | None = None) -> List[Dict[str, Any]]:
        """语义检索，返回相关文档片段"""
        top_k = k or config.RETRIEVE_TOP_K
        results = self.store.search(query, k=top_k)
        logger.info("检索 \"%s\" → %d 条结果", query, len(results))
        return results

    def format_context(self, results: List[Dict[str, Any]]) -> str:
        """将检索结果格式化为 LLM 能用的上下文文本"""
        if not results:
            return ""

        lines = ["以下是知识库中与问题相关的内容：\n"]
        for i, r in enumerate(results, 1):
            source = r.get("metadata", {}).get("source", "未知来源")
            lines.append(f"[{i}] 来源: {source}")
            lines.append(r["content"][:300])
            lines.append("")
        return "\n".join(lines)


# 全局单例
_retriever = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever
