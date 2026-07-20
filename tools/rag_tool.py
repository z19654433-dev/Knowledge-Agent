"""RAG 知识库检索工具 —— 接入 Agent 的 tool_registry"""

from tools import registry
from knowledge.pipeline import query as rag_query
from utils.logger import get_logger

logger = get_logger(__name__)


@registry.register(
    description="在个人知识库中检索信息来回答专业问题。"
                "当用户询问知识库中的内容（如项目文档、公司流程、学习笔记等）时调用此工具。"
                "普通闲聊、查天气、做计算请使用其他对应工具。"
)
def knowledge_search(query: str) -> str:
    """从知识库中检索并生成答案。

    Args:
        query: 用户的问题或查询关键词
    """
    logger.info("RAG 工具被调用: %s", query)
    return rag_query(query)
