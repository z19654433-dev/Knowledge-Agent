"""Obsidian 知识库工具 —— 检索与读取用户个人笔记（只读，遵守排除清单）"""

from tools import registry
from pathlib import Path
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_RESULT_LENGTH = 2000
MAX_NOTE_LENGTH = 4000


def _resolve_note(note: str) -> Path | None:
    """将笔记名/路径解析为 vault 内的绝对路径。

    解析顺序：
      1. 绝对路径且文件存在
      2. 相对 vault 根的路径存在
      3. 按文件名（stem）在 vault 内递归查找 .md
    """
    from config import OBSIDIAN_VAULT_DIR

    vault = OBSIDIAN_VAULT_DIR
    if not vault:
        return None
    vault_path = Path(vault).resolve()
    p = Path(note)

    # 1. 绝对路径
    if p.is_absolute() and p.exists():
        return p
    # 2. 相对 vault 的路径
    rp = vault_path / note
    if rp.exists():
        return rp
    # 3. 按文件名查找
    target = p.stem if p.suffix else note
    matches = [
        f for f in vault_path.rglob("*.md")
        if f.stem == target and not f.name.startswith(".")
    ]
    if matches:
        return matches[0]
    return None


@registry.register(
    description="在用户的 Obsidian 个人知识库中检索并回答关于其笔记内容的问题"
                "（如学习方法、项目笔记、读书摘抄、个人资料等）。"
                "当用户询问自己的笔记、个人知识、或 vault 中的主题时使用。"
                "它与 knowledge_search 是两套独立的知识库，不要混用。"
)
def search_obsidian_notes(query: str) -> str:
    """在 Obsidian 知识库中语义检索并生成答案。

    Args:
        query: 用户的问题或查询关键词
    """
    logger.info("Obsidian 检索工具被调用: %s", query)
    from knowledge.pipeline import query_obsidian

    result = query_obsidian(query)
    if len(result) > MAX_RESULT_LENGTH:
        result = result[:MAX_RESULT_LENGTH] + "\n\n[回答过长已截断]"
    return result


@registry.register(
    description="读取某篇具体 Obsidian 笔记的原文内容。"
                "当用户明确提到某篇笔记名称（如「python之路」「prompt」）"
                "并想查看其具体内容时调用。"
                "注意：被排除清单保护的隐私文件（如存放 API Key 的文件）无法读取。"
)
def read_obsidian_note(note: str) -> str:
    """读取指定 Obsidian 笔记的原文。

    Args:
        note: 笔记名称或路径，例如 "python之路" 或 "外语学习/单词表.md"
    """
    logger.info("Obsidian 读取工具被调用: %s", note)
    from config import OBSIDIAN_VAULT_DIR, OBSIDIAN_EXCLUDE
    from knowledge.loader import is_path_excluded

    vault = OBSIDIAN_VAULT_DIR
    if not vault:
        return "Obsidian vault 未配置（请设置 OBSIDIAN_VAULT_DIR）。"

    candidate = _resolve_note(note)
    if candidate is None:
        return f"未找到笔记: {note}（检查名称或路径是否正确）"

    vault_path = Path(vault).resolve()
    try:
        rel = str(candidate.resolve().relative_to(vault_path))
    except Exception:
        rel = candidate.name
    if is_path_excluded(rel, OBSIDIAN_EXCLUDE):
        return "该文件被排除清单保护，无法读取（可能含敏感信息）。"

    try:
        content = candidate.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"读取笔记失败: {e}"
    if len(content) > MAX_NOTE_LENGTH:
        content = content[:MAX_NOTE_LENGTH] + "\n\n[笔记过长已截断]"
    return f"# {candidate.name}\n\n{content}"
