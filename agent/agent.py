import json
from tools import registry
from memory.memory import Memory
from chatbot.chatbot import chat
from utils.logger import get_logger

logger = get_logger(__name__)


class Agent:

    def __init__(self, session_id: str = "default_session"):
        self.name = "MyAgent"
        self.session_id = session_id
        self.memory = Memory()
        history = self.memory.load_history(self.session_id, limit=20)
        system_prompt = (
            "你是一个友好的AI助手。你可以做以下事情：\n"
            "1. 查询天气：告诉用户输入城市名即可查天气\n"
            "2. 数学计算：进行精确的数学运算\n"
            "3. 今日热榜：查看GitHub趋势项目或百度热搜（默认GitHub）\n"
            "4. 知识库检索：从你的私有知识库中搜索专业内容来回答问题\n"
            "你需要根据用户的问题自主决定调用哪个工具：\n"
            "  - 问天气 → weather\n"
            "  - 算数学 → calculator\n"
            "  - 问热榜 → get_hotlist\n"
            "  - 问知识库里的内容 → knowledge_search\n"
            "  - 普通聊天 → 直接回答\n"
            "回答简洁友好，每次只回答用户的当前问题，不要提前列出一堆功能。"
        )
        self.messages = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]
        self.messages.extend(history)
        logger.info("Agent 初始化完成, session=%s", session_id)

    def add_user_message(self, content):
        self.messages.append({"role": "user", "content": content})
        self.memory.save_message(self.session_id, "user", content)

    def add_assistant_message(self, content):
        self.messages.append({"role": "assistant", "content": content})
        self.memory.save_message(self.session_id, "assistant", content)

    def add_tool_messages(self, tool_name, result):
        self.memory.save_message(
            self.session_id,
            "assistant",
            f"[工具调用] {tool_name} 返回: {result}"
        )

    def run(self, message, model_provider: str = "deepseek"):
        self.add_user_message(message)
        logger.info("用户输入: %s", message)

        response = chat(self.messages, tools=registry.schemas, tool_choice="auto", provider=model_provider)
        choice = response.choices[0]
        finish_reason = choice.finish_reason

        if finish_reason == "tool_calls":
            tool_calls = choice.message.tool_calls
            logger.info("触发工具调用, 数量=%d", len(tool_calls))

            self.messages.append(choice.message.model_dump())

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                logger.info("执行工具: %s, 参数=%s", tool_name, tool_args)

                result = registry.tools[tool_name](**tool_args)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                })
                self.add_tool_messages(tool_name, str(result))
                logger.info("工具 %s 返回: %s", tool_name, result)

            final_response = chat(self.messages, tools=registry.schemas, tool_choice="none", provider=model_provider)
            final_answer = final_response.choices[0].message.content
            self.add_assistant_message(final_answer)
            logger.info("最终回答: %s", final_answer[:100])
            return final_answer
        else:
            answer = choice.message.content
            self.add_assistant_message(answer)
            logger.info("直接回答: %s", answer[:100])
            return answer

    def clear_memory(self):
        self.memory.clear_session(self.session_id)
        system_prompt = (
            "你是一个友好的AI助手。你可以做以下事情：\n"
            "1. 查询天气：告诉用户输入城市名即可查天气\n"
            "2. 数学计算：进行精确的数学运算\n"
            "3. 今日热榜：查看GitHub趋势项目或百度热搜（默认GitHub）\n"
            "4. 知识库检索：从你的私有知识库中搜索专业内容来回答问题\n"
            "你需要根据用户的问题自主决定调用哪个工具：\n"
            "  - 问天气 → weather\n"
            "  - 算数学 → calculator\n"
            "  - 问热榜 → get_hotlist\n"
            "  - 问知识库里的内容 → knowledge_search\n"
            "  - 普通聊天 → 直接回答\n"
            "回答简洁友好，每次只回答用户的当前问题，不要提前列出一堆功能。"
        )
        self.messages = [{"role": "system", "content": system_prompt}]
        logger.info("记忆已清除, session=%s", self.session_id)
