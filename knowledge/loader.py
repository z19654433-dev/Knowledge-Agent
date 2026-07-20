"""文档加载器：支持 TXT / Markdown / PDF，预留扩展接口"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from utils.logger import get_logger

logger = get_logger(__name__)


class Document:
    """统一文档结构"""

    def __init__(self, content: str, metadata: dict | None = None):
        self.content = content
        self.metadata = metadata or {}


class BaseLoader(ABC):
    """加载器基类"""

    @abstractmethod
    def load(self, file_path: str) -> List[Document]:
        ...


class TextLoader(BaseLoader):
    """TXT 文件加载"""

    def load(self, file_path: str) -> List[Document]:
        path = Path(file_path)
        content = path.read_text(encoding="utf-8", errors="ignore")
        return [Document(
            content=content,
            metadata={"source": str(path), "type": "txt"},
        )]


class MarkdownLoader(BaseLoader):
    """Markdown 文件加载"""

    def load(self, file_path: str) -> List[Document]:
        path = Path(file_path)
        content = path.read_text(encoding="utf-8", errors="ignore")
        return [Document(
            content=content,
            metadata={"source": str(path), "type": "md"},
        )]


class PdfLoader(BaseLoader):
    """PDF 文件加载（骨架，后续接入 PyMuPDF）"""

    def load(self, file_path: str) -> List[Document]:
        # TODO: 接入 PyMuPDF / pdfplumber
        logger.warning("PDF 加载器尚未完整实现: %s", file_path)
        return [Document(
            content=f"[PDF 文件待解析] {file_path}",
            metadata={"source": file_path, "type": "pdf"},
        )]


# ── 工厂 ──

_SUFFIX_MAP = {
    ".txt": TextLoader,
    ".md": MarkdownLoader,
    ".pdf": PdfLoader,
}


def get_loader(file_path: str) -> BaseLoader:
    """根据文件后缀返回对应的加载器"""
    suffix = Path(file_path).suffix.lower()
    loader_cls = _SUFFIX_MAP.get(suffix)
    if loader_cls is None:
        raise ValueError(f"不支持的文件格式: {suffix}，支持: {list(_SUFFIX_MAP.keys())}")
    return loader_cls()


def load_document(file_path: str) -> List[Document]:
    """加载单个文件"""
    loader = get_loader(file_path)
    return loader.load(file_path)


def load_directory(doc_dir: str) -> List[Document]:
    """递归加载目录下所有支持的文档"""
    all_docs = []
    base = Path(doc_dir)
    if not base.exists():
        logger.warning("文档目录不存在: %s", doc_dir)
        return all_docs

    for file_path in base.rglob("*"):
        if file_path.suffix.lower() not in _SUFFIX_MAP:
            continue
        if file_path.name.startswith("."):
            continue
        try:
            docs = load_document(str(file_path))
            all_docs.extend(docs)
            logger.info("已加载: %s", file_path)
        except Exception as e:
            logger.error("加载失败 %s: %s", file_path, e)

    logger.info("共加载 %d 个文档", len(all_docs))
    return all_docs
