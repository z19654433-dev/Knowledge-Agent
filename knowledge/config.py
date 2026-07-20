"""知识库配置：切片策略、检索参数、模型选择"""

import os


class KnowledgeConfig:
    """所有知识库配置项，可通过环境变量覆盖"""

    # ── 文档目录 ──
    DOCS_DIR: str = os.getenv(
        "KNOWLEDGE_DOCS_DIR",
        os.path.join(os.path.dirname(__file__), "docs"),
    )

    # ── 向量数据库持久化目录 ──
    VECTOR_DB_DIR: str = os.getenv(
        "KNOWLEDGE_VECTOR_DB_DIR",
        os.path.join(os.path.dirname(__file__), "chroma_db"),
    )

    # ── 文本切片 ──
    CHUNK_SIZE: int = int(os.getenv("KNOWLEDGE_CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("KNOWLEDGE_CHUNK_OVERLAP", "50"))

    # ── 检索 ──
    RETRIEVE_TOP_K: int = int(os.getenv("KNOWLEDGE_RETRIEVE_TOP_K", "3"))

    # ── Embedding 模型 ──
    # 可选: "default" (ChromaDB内置) | "sentence-transformers" | "api"
    EMBEDDING_MODEL: str = os.getenv("KNOWLEDGE_EMBEDDING", "default")

    # ── 向量数据库 ──
    # 可选: "chroma" | "faiss" (预留)
    VECTOR_STORE_TYPE: str = os.getenv("KNOWLEDGE_VECTOR_STORE", "chroma")

    # ── Collection 名称 ──
    COLLECTION_NAME: str = "knowledge_base"


# 全局单例
config = KnowledgeConfig()
