"""联网搜索工具：通过 DuckDuckGo HTML 接口检索网页，无需 API Key"""

from tools import registry
from utils.logger import get_logger
import httpx
import re
import html as _html
import urllib.parse

logger = get_logger(__name__)

_TIMEOUT = 10.0
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_SEARCH_URL = "https://html.duckduckgo.com/html/"


@registry.register(
    description="联网搜索网页内容，获取与问题相关的最新网页结果（标题、摘要、链接）。"
                "当用户需要实时信息、最新新闻、或知识库之外的资料时调用。"
)
def web_search(query: str, num_results: int = 5) -> str:
    """通过 DuckDuckGo 检索网页结果。

    Args:
        query: 搜索关键词，例如 "Python 异步编程 最佳实践"
        num_results: 返回结果条数，默认 5，范围 1-10
    """
    if not query or not query.strip():
        return "请提供搜索关键词"
    query = query.strip()
    num_results = max(1, min(int(num_results), 10))

    headers = {"User-Agent": _USER_AGENT}
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.post(_SEARCH_URL, data={"q": query}, headers=headers)
            resp.raise_for_status()
            page = resp.text
    except httpx.TimeoutException:
        logger.warning("联网搜索超时: %s", query)
        return "搜索超时，请稍后重试"
    except Exception as e:
        logger.error("联网搜索失败: %s", e)
        return "联网搜索失败：" + str(e)

    results = _parse_results(page, num_results)
    if not results:
        return "没有找到相关结果，换个关键词试试"
    return _format_output(query, results)


def _parse_results(page: str, num_results: int) -> list[dict]:
    # 每个结果：标题 + 链接在同一个 <a class="result__a"> 标签中
    pair_pattern = r'class="result__a"\s+href="([^"]+)"[^>]*>(.*?)</a>'
    pairs = re.findall(pair_pattern, page, re.S)
    # 摘要单独提取
    snippet_pattern = r'class="result__snippet"[^>]*>(.*?)</a>'
    snippets = re.findall(snippet_pattern, page, re.S)

    items = []
    for i, (url, title_html) in enumerate(pairs):
        if len(items) >= num_results:
            break
        real_url = _decode_url(url)
        if _is_ad(real_url):          # 跳过赞助/广告结果
            continue
        title = _clean(title_html)
        if not title:
            continue
        snippet = _clean(snippets[i]) if i < len(snippets) else ""
        items.append({
            "title": title,
            "url": real_url,
            "snippet": snippet,
        })
    return items


def _is_ad(url: str) -> bool:
    """过滤 DuckDuckGo 的赞助/广告结果（其链接指向 duckduckgo.com/y.js 追踪页）。"""
    u = url.lower()
    return ("duckduckgo.com/y.js" in u) or ("ad_domain=" in u) or ("ad_provider=" in u)


def _decode_url(ddg_url: str) -> str:
    # DuckDuckGo 把真实链接包裹在 uddg 参数中
    m = re.search(r"uddg=([^&]+)", ddg_url)
    if m:
        return urllib.parse.unquote(m.group(1))
    if ddg_url.startswith("//"):
        return "https:" + ddg_url
    return ddg_url


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)        # 去除 HTML 标签
    text = _html.unescape(text)                # 解码 HTML 实体
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _format_output(query: str, items: list[dict]) -> str:
    lines = ["\U0001f50d 联网搜索「" + query + "」结果（共 " + str(len(items)) + " 条）\n"]
    for i, item in enumerate(items, 1):
        lines.append(str(i) + ". " + item["title"])
        if item["snippet"]:
            lines.append("   \u21b3 " + item["snippet"])
        lines.append("   \u25b8 " + item["url"])
    return "\n".join(lines)
