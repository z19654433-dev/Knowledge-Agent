"""
工具注册模块
=========
通过 @registry.register() 装饰器自动注册工具函数并生成 JSON Schema。
避免手动维护 tool_schemas.py 和 registry.py 的重复工作。

用法:
    from tools import registry

    @registry.register(description="查询天气")
    def get_weather(city: str) -> str:
        ...

然后在外层使用:
    registry.tools    -> {"get_weather": <函数>}
    registry.schemas  -> [{"type": "function", "function": {...}}, ...]
"""

import inspect
from typing import Callable, Optional, get_type_hints


# Python 类型 → JSON Schema 类型映射
_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _infer_type(annotation) -> str:
    """从类型注解推断 JSON Schema type。"""
    if annotation is inspect.Parameter.empty:
        return "string"
    # 处理 Optional[str] → str
    origin = getattr(annotation, "__origin__", None)
    if origin is type(Optional[str]):  # UnionType
        args = getattr(annotation, "__args__", ())
        real = [a for a in args if a is not type(None)]
        if real:
            return _TYPE_MAP.get(real[0], "string")
    return _TYPE_MAP.get(annotation, "string")


class ToolRegistry:
    """工具注册表：维护名称→函数映射 及 OpenAI function-calling schema。"""

    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._schemas: list[dict] = []

    def register(
        self,
        name: Optional[str] = None,
        description: str = "",
    ) -> Callable:
        """装饰器：注册一个工具函数。

        Args:
            name: 工具名称（默认使用函数名）
            description: 工具描述（默认使用函数 docstring）

        装饰器会自动从函数签名推断 JSON Schema。
        """
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            tool_desc = description or (func.__doc__ or "").strip()

            # 从函数签名生成 parameters schema
            sig = inspect.signature(func)
            hints = get_type_hints(func) if hasattr(func, "__annotations__") else {}
            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                # 排除 self / cls
                if param_name in ("self", "cls"):
                    continue

                ann = hints.get(param_name, param.annotation)
                param_type = _infer_type(ann)

                prop = {
                    "type": param_type,
                    "description": f"参数 {param_name}",
                }

                # 有默认值 → 非 required，且可提供默认值提示
                if param.default is not inspect.Parameter.empty:
                    if param.default is not None:
                        prop["default"] = param.default
                else:
                    required.append(param_name)

                properties[param_name] = prop

            schema = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_desc,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                    },
                },
            }
            if required:
                schema["function"]["parameters"]["required"] = required

            self._tools[tool_name] = func
            self._schemas.append(schema)
            return func

        return decorator

    @property
    def tools(self) -> dict[str, Callable]:
        """工具名称 → 可调用对象"""
        return dict(self._tools)

    @property
    def schemas(self) -> list[dict]:
        """OpenAI function-calling schema 列表"""
        return list(self._schemas)


# 全局注册表实例
registry = ToolRegistry()

# 导入工具模块（导入时执行装饰器，自动注册）
from . import calculator  # noqa: E402
from . import weather     # noqa: E402
from . import hotlist      # noqa: E402
from . import rag_tool      # noqa: E402
from . import web_search   # noqa: E402
from . import obsidian     # noqa: E402
import knowledge               # noqa: E402
