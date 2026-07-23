"""RAG 完整流程 —— 检索 + DeepSeek 生成自然语言答案

index_documents()  加载 → 切片 → 向量化 → 存储
query()            检索 → Prompt → DeepSeek → 答案
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

import hashlib
import threading
from pathlib import Path
from .config import config
from .loader import load_directory, is_path_excluded
from .chunker import Chunker
from .vector_store import get_vector_store
from .retriever import get_retriever
from config import OBSIDIAN_VAULT_DIR, OBSIDIAN_COLLECTION, OBSIDIAN_EXCLUDE
from utils.logger import get_logger

logger = get_logger(__name__)

# 索引与查询共享同一 Chroma collection，加锁避免并发读写冲突
# （文件监视器在后台线程触发重索引，可能与主请求的 RAG 查询并发）
_obsidian_index_lock = threading.Lock()


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

def _format_context(docs):
    """将检索到的 Document 列表拼接为文本（供 knowledge 与 obsidian 共用）"""
    if not docs:
        return "（知识库中暂未找到相关内容）"
    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "未知")
        parts.append(f"[片段{i} | 来源: {source}]\n{doc.page_content}")
    return "\n\n".join(parts)


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


# ═══════════════════════════════════════════
#  Obsidian 知识库：独立 collection，与 knowledge/docs 隔离
# ═══════════════════════════════════════════

def index_obsidian(force: bool = False) -> dict:
    """公共入口：加锁后调用实际索引逻辑，避免与查询并发读写 Chroma 冲突。"""
    with _obsidian_index_lock:
        return _index_obsidian_impl(force)


def _index_obsidian_impl(force: bool = False) -> dict:
    """增量索引 Obsidian vault 到独立 collection。

    - 排除 OBSIDIAN_EXCLUDE 清单中的文件/文件夹（如存放 API Key 的 API.md），
      这些文件永不被向量化，保证隐私不外泄。
    - 按文件 mtime + 确定性 id 实现增量：未变更的文件跳过，变更/新增的更新，
      已删除的文件从向量库移除。force=True 时清空后全量重建。

    Returns:
        dict: {status, indexed_files, chunks, updated, deleted, skipped_excluded}
    """
    vault = OBSIDIAN_VAULT_DIR
    if not vault or not Path(vault).exists():
        return {"status": "error", "message": f"Obsidian vault 未配置或不存在: {vault}"}

    logger.info("开始索引 Obsidian: %s", vault)
    docs = load_directory(vault)

    # 排除隐私文件
    skipped = 0
    kept = []
    vault_path = Path(vault).resolve()
    for d in docs:
        try:
            rel = str(Path(d.metadata["source"]).resolve().relative_to(vault_path))
        except Exception:
            rel = Path(d.metadata["source"]).name
        if is_path_excluded(rel, OBSIDIAN_EXCLUDE):
            skipped += 1
            continue
        kept.append(d)
    docs = kept

    if not docs:
        return {
            "status": "error",
            "message": "vault 内无可索引的笔记（可能全部被排除清单过滤）",
            "skipped_excluded": skipped,
        }

    chunker = Chunker()
    chunks = chunker.split_documents(docs)

    # 为每块生成确定性 id（文件哈希 + 序号）并记录 mtime，支撑增量更新
    store = get_vector_store(OBSIDIAN_COLLECTION)
    desired: dict[str, dict] = {}
    for d in chunks:
        src = Path(d.metadata["source"]).resolve()
        rel = str(src.relative_to(vault_path))
        file_hash = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:16]
        mtime = src.stat().st_mtime
        d.metadata["doc_id"] = file_hash
        d.metadata["rel_path"] = rel
        d.metadata["mtime"] = mtime
        info = desired.setdefault(file_hash, {"ids": [], "docs": [], "mtime": mtime})
        idx = len(info["ids"])
        info["ids"].append(f"{file_hash}_{idx}")
        info["docs"].append(d)

    stats = {
        "indexed_files": 0,
        "chunks": 0,
        "updated": 0,
        "deleted": 0,
        "skipped_excluded": skipped,
    }

    if force:
        store.delete_all()
        for info in desired.values():
            store.add_documents_with_ids(info["docs"], info["ids"])
            stats["indexed_files"] += 1
            stats["chunks"] += len(info["ids"])
        stats["status"] = "success"
        logger.info("Obsidian 全量索引完成: %d 文件 / %d 切片", stats["indexed_files"], stats["chunks"])
        return stats

    # 增量：对比已有 mtime
    try:
        existing = store.get(include=["metadatas"]) or {}
    except Exception:
        existing = {}
    exist_ids = existing.get("ids", []) or []
    exist_meta = existing.get("metadatas", []) or []
    old_by_doc: dict[str, list] = {}
    old_mtime: dict[str, float] = {}
    for _id, meta in zip(exist_ids, exist_meta):
        doc_id = meta.get("doc_id")
        if not doc_id:
            continue
        old_by_doc.setdefault(doc_id, []).append(_id)
        old_mtime[doc_id] = meta.get("mtime", 0)

    # 删除已不存在的文件
    for doc_id, ids in old_by_doc.items():
        if doc_id not in desired:
            store.delete(ids)
            stats["deleted"] += 1

    # 新增 / 更新
    for doc_id, info in desired.items():
        if doc_id in old_by_doc and old_mtime.get(doc_id) == info["mtime"]:
            # 未变更，跳过
            stats["indexed_files"] += 1
            stats["chunks"] += len(info["ids"])
            continue
        if doc_id in old_by_doc:
            store.delete(old_by_doc[doc_id])
            stats["updated"] += 1
        store.add_documents_with_ids(info["docs"], info["ids"])
        stats["indexed_files"] += 1
        stats["chunks"] += len(info["ids"])

    stats["status"] = "success"
    logger.info(
        "Obsidian 增量索引完成: 新增/更新 %d, 删除 %d, 跳过排除 %d",
        stats["updated"], stats["deleted"], stats["skipped_excluded"],
    )
    return stats


def query_obsidian(question: str) -> str:
    """在 Obsidian 独立 collection 上做 RAG 语义检索并生成答案。

    注意：被排除清单过滤的文件不会进入向量库，因此检索到的内容均不含隐私文件。
    """
    from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

    store = get_vector_store(OBSIDIAN_COLLECTION)
    if store.count() == 0:
        return "Obsidian 知识库尚未索引，请先调用 POST /obsidian/index 进行索引。"

    docs = store.search(question, k=config.RETRIEVE_TOP_K)
    if not docs:
        return "（Obsidian 中未找到相关内容）"

    context = _format_context(docs)
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=0.3,
    )
    try:
        answer = (RAG_PROMPT | llm | StrOutputParser()).invoke(
            {"context": context, "question": question}
        )
        return answer
    except Exception as e:
        logger.error("Obsidian RAG 生成失败: %s", e)
        return f"抱歉，处理您的问题时出错了：{e}"
