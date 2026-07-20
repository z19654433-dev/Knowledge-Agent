"""RAG 完整流程 —— 检索 + DeepSeek 生成自然语言答案

index_documents()  加载 → 切片 → 向量化 → 存储
query()            检索 → Prompt → DeepSeek → 答案
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

from .config import config
from .loader import load_directory
from .chunker import Chunker
from .vector_store import get_vector_store
from .retriever import get_retriever
from utils.logger import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════
#  RAG Prompt 模板
# ═══════════════════════════════════════════

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", (
        "你是一个基于知识库的智能助手。请严格根据以下\"上下文\"中的信息来回答问题。\n"
        "要求：\n"
        "1. 如果上下文中有相关答案，用简洁的中文回答\n"
        "2. 如果上下文中没有相关信息，请明确说\"知识库中没有相关信息\"，不要编造\n"
        "3. 回答时不要提及\"根据上下文\"、\"根据提供的资料\"等字样，直接给出答案"
    )),
    ("human", (
        "上下文：\n"
        "---\n"
        "{context}\n"
        "---\n"
        "请根据以上上下文回答下面的问题：\n"
        "{question}"
    )),
])


# ═══════════════════════════════════════════
#  LangChain Chain：检索 → 生成
# ═══════════════════════════════════════════

def _build_chain():
    """构建 LCEL Chain：retrieve → context → prompt → llm → output"""
    from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=0.3,
    )

    retriever = get_retriever().get_langchain_retriever()

    def _format_context(docs):
        """将检索到的 Document 列表拼接为文本"""
        if not docs:
            return "（知识库中暂未找到相关内容）"
        parts = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "未知")
            parts.append(f"[片段{i} | 来源: {source}]\n{doc.page_content}")
        return "\n\n".join(parts)

    chain = (
        {"context": retriever | _format_context, "question": RunnablePassthrough()}
        | RAG_PROMPT
        | llm
        | StrOutputParser()
    )

    logger.info("RAG 生成链路初始化完成")
    return chain


# ═══════════════════════════════════════════
#  对外接口（不变）
# ═══════════════════════════════════════════

def index_documents(doc_dir: str | None = None) -> int:
    """索引文档：加载 → 切片 → 向量化 → 存储"""
    doc_dir = doc_dir or config.DOCS_DIR
    logger.info("开始索引: %s", doc_dir)

    docs = load_directory(doc_dir)
    if not docs:
        logger.warning("未找到文档")
        return 0

    chunker = Chunker()
    chunks = chunker.split_documents(docs)
    store = get_vector_store()
    store.add_documents(chunks)
    logger.info("索引完成: %d 个切片", len(chunks))
    return len(chunks)


_chain = None


def query(question: str) -> str:
    """RAG 查询：检索 → DeepSeek 生成自然语言答案

    Args:
        question: 用户问题

    Returns:
        基于知识库生成的自然语言回答
    """
    global _chain

    # 首次调用自动索引
    store = get_vector_store()
    if store.count() == 0:
        logger.info("知识库为空，自动索引")
        n = index_documents()
        if n == 0:
            return "知识库中暂无内容，请先往 knowledge/docs/ 目录添加文档"

    # 构建 Chain（首次或 store 重建后）
    if _chain is None:
        _chain = _build_chain()

    try:
        answer = _chain.invoke(question)
        logger.info("RAG 生成完成")
        return answer
    except Exception as e:
        logger.error("RAG 生成失败: %s", e)
        return f"抱歉，处理您的问题时出错了：{e}"
