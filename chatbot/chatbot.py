"""LLM 适配器：支持多模型动态切换"""

from openai import OpenAI
from abc import ABC, abstractmethod
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL_NAME,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseLLM(ABC):
    """LLM 基类：统一 chat 接口"""

    @abstractmethod
    def chat(self, messages, tools=None, tool_choice="auto"):
        ...

    @abstractmethod
    def chat_stream(self, messages, tools=None, tool_choice="auto"):
        """流式调用，返回迭代器"""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """模型显示名称（前端展示用）"""
        ...


class DeepSeekAdapter(BaseLLM):
    """DeepSeek 官方 API"""

    def __init__(self):
        self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        self.model = DEEPSEEK_MODEL

    @property
    def display_name(self) -> str:
        return "DeepSeek"

    def chat(self, messages, tools=None, tool_choice="auto"):
        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        return self.client.chat.completions.create(**kwargs)

    def chat_stream(self, messages, tools=None, tool_choice="auto"):
        kwargs = {"model": self.model, "messages": messages, "stream": True}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        return self.client.chat.completions.create(**kwargs)


class OpenAICompatibleAdapter(BaseLLM):
    """通用 OpenAI 兼容适配器"""

    def __init__(self, model_name: str, api_key: str, base_url: str, label: str = ""):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model_name
        self._label = label or model_name

    @property
    def display_name(self) -> str:
        return self._label

    def chat(self, messages, tools=None, tool_choice="auto"):
        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        return self.client.chat.completions.create(**kwargs)

    def chat_stream(self, messages, tools=None, tool_choice="auto"):
        kwargs = {"model": self.model, "messages": messages, "stream": True}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        return self.client.chat.completions.create(**kwargs)


# ===== 预设模型列表 =====
# 键名供前端传参用，值是对应的适配器工厂函数和角色说明
MODEL_PRESETS = {
    "deepseek": {
        "factory": lambda: DeepSeekAdapter(),
        "label": "DeepSeek",
        "role": "通用助手",
    },
    "glm": {
        "factory": lambda: OpenAICompatibleAdapter(
            model_name="glm-4-flash",
            api_key=OPENAI_API_KEY,
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            label="智谱 GLM",
        ),
        "label": "智谱 GLM",
        "role": "创意写作",
    },
    "qwen": {
        "factory": lambda: OpenAICompatibleAdapter(
            model_name="qwen-turbo",
            api_key=OPENAI_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            label="通义千问",
        ),
        "label": "通义千问",
        "role": "逻辑分析",
    },
    "yi": {
        "factory": lambda: OpenAICompatibleAdapter(
            model_name="yi-lightning",
            api_key=OPENAI_API_KEY,
            base_url="https://api.lingyiwanwu.com/v1",
            label="零一万物",
        ),
        "label": "零一万物",
        "role": "头脑风暴",
    },
}


def get_available_models() -> list[dict]:
    """返回可用的模型列表（前端展示用）"""
    result = []
    for key, preset in MODEL_PRESETS.items():
        result.append({
            "id": key,
            "label": preset["label"],
            "role": preset["role"],
        })
        # 只返回第一个可用模型
        break
    # 添加其他模型（需配置Key）
    for key, preset in list(MODEL_PRESETS.items())[1:]:
        if key == "deepseek":
            continue
        result.append({
            "id": key,
            "label": preset["label"],
            "role": preset["role"],
        })
    return result


def create_llm(provider: str = "deepseek") -> BaseLLM:
    """根据 provider 创建对应的 LLM 适配器"""
    provider = provider.lower().strip()

    if provider not in MODEL_PRESETS:
        logger.warning("不支持的模型: %s，回退到 deepseek", provider)
        provider = "deepseek"

    preset = MODEL_PRESETS[provider]
    llm = preset["factory"]()
    logger.info("LLM: %s (%s)", preset["label"], provider)
    return llm


def chat(messages, tools=None, tool_choice="auto", provider: str = "deepseek"):
    """对外接口：支持每次请求指定模型"""
    llm = create_llm(provider)
    return llm.chat(messages, tools, tool_choice)


def chat_stream(messages, tools=None, tool_choice="auto", provider: str = "deepseek"):
    """流式对外接口"""
    llm = create_llm(provider)
    return llm.chat_stream(messages, tools, tool_choice)
