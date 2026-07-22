import json
from tools import registry
from memory.memory import Memory
from memory.vector_memory import get_vector_memory
from chatbot.chatbot import chat, chat_stream
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_TOOL_ROUNDS = 5
# 最近对话保留条数（向量检索补丁之外，保留最基本的最近上下文）
RECENT_HISTORY_LIMIT = 5
# 向量检索返回的相关历史条数
VECTOR_MEMORY_K = 3


class Agent:

    def __init__(self, session_id: str = "default_session"):
        self.name = "MyAgent"
        self.session_id = session_id
        self.memory = Memory()
        self.vector_memory = get_vector_memory()

        system_prompt = (
            "你是一个友好的AI助手。你可以做以下事情：\n"
            "1. 查询天气：告诉用户输入城市名即可查天气\n"
            "2. 数学计算：进行精确的数学运算\n"
            "3. 今日热榜：查看GitHub趋势项目或百度热搜（默认GitHub）\n"
            "4. 知识库检索：从你的私有知识库中搜索专业内容来回答问题\n"
            "5. 联网搜索：检索互联网上的最新网页、新闻与实时信息\n"
            "你需要根据用户的问题自主决定调用哪个工具：\n"
            "  - 问天气 → weather\n"
            "  - 算数学 → calculator\n"
            "  - 问热榜 → get_hotlist\n"
            "  - 问知识库里的内容 → knowledge_search\n"
            "  - 需要联网查最新资讯/新闻/网页 → web_search\n"
            "  - 普通聊天 → 直接回答\n"
            "回答简洁友好，每次只回答用户的当前问题，不要提前列出一堆功能。"
        )
        self.messages = [{"role": "system", "content": system_prompt}]

        # ── 加载历史：最近 N 条 + 向量检索相关历史 ──
        recent = self.memory.load_history(session_id, limit=RECENT_HISTORY_LIMIT)
        self.messages.extend(recent)
        logger.info("已加载最近 %d 条历史", len(recent))

        logger.info("Agent 初始化完成, session=%s", session_id)

    # ── 消息管理 ──

    def add_user_message(self, content):
        self.messages.append({"role": "user", "content": content})
        self.memory.save_message(self.session_id, "user", content)

    def add_assistant_message(self, content):
        self.messages.append({"role": "assistant", "content": content})
        self.memory.save_message(self.session_id, "assistant", content)

    def add_tool_messages(self, tool_name, result):
        truncated = str(result)[:500] + ("..." if len(str(result)) > 500 else "")
        self.memory.save_message(
            self.session_id,
            "assistant",
            f"[{tool_name}] {truncated}",
        )

    # ── 核心执行 ──

    def _execute_tool(self, tool_call) -> str:
        tool_name = tool_call.function.name
        try:
            tool_args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            logger.warning("工具参数解析失败: %s", tool_call.function.arguments)
            return "工具参数解析失败"

        logger.info("执行工具: %s, 参数=%s", tool_name, tool_args)

        tool_func = registry.tools.get(tool_name)
        if tool_func is None:
            logger.warning("未知工具: %s", tool_name)
            return f"工具 {tool_name} 不存在"

        try:
            result = tool_func(**tool_args)
            logger.info("工具 %s 返回成功", tool_name)
            return str(result)
        except Exception as e:
            logger.error("工具 %s 执行失败: %s", tool_name, e)
            return f"工具执行失败: {str(e)}"

    def run(self, message, model_provider: str = "deepseek"):
        # ── 重建基础上下文：system prompt + 最近 SQLite 历史 ──
        # 每次 run 从干净状态开始，避免 messages 无限膨胀
        system_msg = self.messages[0]  # 第一条始终是 system prompt
        recent = self.memory.load_history(self.session_id, limit=RECENT_HISTORY_LIMIT)
        self.messages = [system_msg]
        self.messages.extend(recent)

        logger.info("用户输入: %s", message)
        self.add_user_message(message)

        # ── 向量检索相关历史记忆 ──
        try:
            related = self.vector_memory.search(
                message, session_id=self.session_id, k=VECTOR_MEMORY_K,
            )
            if related:
                context_lines = ["以下是你与用户的相关历史对话（供参考）："]
                for i, item in enumerate(related, 1):
                    context_lines.append("---\n[历史对话 {}]\n{}".format(i, item["content"]))
                self.messages.append({
                    "role": "system",
                    "content": "\n".join(context_lines),
                })
                logger.info("向量记忆检索到 %d 条相关历史", len(related))
        except Exception as e:
            logger.warning("向量记忆检索失败: %s", e)

        # ── 多轮 tool calling 循环 ──
        for round_num in range(MAX_TOOL_ROUNDS):
            response = chat(
                self.messages,
                tools=registry.schemas,
                tool_choice="auto",
                provider=model_provider,
            )
            choice = response.choices[0]
            finish_reason = choice.finish_reason

            if finish_reason != "tool_calls":
                answer = choice.message.content
                self.add_assistant_message(answer)
                logger.info("回答（第%d轮）: %s", round_num + 1, answer[:100])

                # ── 将本轮回合存入向量记忆 ──
                try:
                    self.vector_memory.add_turn(self.session_id, message, answer)
                except Exception as e:
                    logger.warning("向量记忆写入失败: %s", e)

                return answer

            # ── 执行工具调用 ──
            tool_calls = choice.message.tool_calls
            logger.info(
                "第%d轮工具调用, 数量=%d, 工具=%s",
                round_num + 1,
                len(tool_calls),
                [tc.function.name for tc in tool_calls],
            )
            self.messages.append(choice.message.model_dump())

            for tool_call in tool_calls:
                result = self._execute_tool(tool_call)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
                self.add_tool_messages(tool_call.function.name, result)

        # 超过最大轮数
        logger.warning("达到最大工具调用轮数 %d", MAX_TOOL_ROUNDS)
        final_response = chat(
            self.messages,
            tools=registry.schemas,
            tool_choice="none",
            provider=model_provider,
        )
        final_answer = final_response.choices[0].message.content
        self.add_assistant_message(final_answer)
        return final_answer

    def run_stream(self, message, model_provider: str = "deepseek"):
        """流式执行：tool calling 阶段非流式，最终回答流式输出。

        Yields:
            dict: {"type": "token", "content": str} | {"type": "done", "content": str}
        """
        # ── 重建基础上下文 ──
        system_msg = self.messages[0]
        recent = self.memory.load_history(self.session_id, limit=RECENT_HISTORY_LIMIT)
        self.messages = [system_msg]
        self.messages.extend(recent)

        logger.info("用户输入: %s", message)
        self.add_user_message(message)

        # ── 向量检索相关历史记忆 ──
        try:
            related = self.vector_memory.search(
                message, session_id=self.session_id, k=VECTOR_MEMORY_K,
            )
            if related:
                context_lines = ["以下是你与用户的相关历史对话（供参考）："]
                for i, item in enumerate(related, 1):
                    context_lines.append(
                        "---\n[历史对话 {}]\n{}".format(i, item["content"])
                    )
                self.messages.append({
                    "role": "system",
                    "content": "\n".join(context_lines),
                })
                logger.info("向量记忆检索到 %d 条相关历史", len(related))
        except Exception as e:
            logger.warning("向量记忆检索失败: %s", e)

        # ── 多轮 tool calling（非流式） ──
        for round_num in range(MAX_TOOL_ROUNDS):
            response = chat(
                self.messages,
                tools=registry.schemas,
                tool_choice="auto",
                provider=model_provider,
            )
            choice = response.choices[0]
            finish_reason = choice.finish_reason

            if finish_reason != "tool_calls":
                # ── 最终回答：流式输出 ──
                collected = ""
                try:
                    stream = chat_stream(
                        self.messages,
                        tools=registry.schemas,
                        tool_choice="none",
                        provider=model_provider,
                    )
                    for chunk in stream:
                        delta = chunk.choices[0].delta.content or ""
                        if delta:
                            collected += delta
                            yield {"type": "token", "content": delta}
                except Exception as e:
                    logger.error("流式调用失败: %s", e)
                    # fallback: 非流式重试
                    try:
                        fallback = chat(
                            self.messages,
                            tools=registry.schemas,
                            tool_choice="none",
                            provider=model_provider,
                        )
                        collected = fallback.choices[0].message.content or ""
                        if collected:
                            yield {"type": "token", "content": collected}
                    except Exception as e2:
                        logger.error("非流式回退也失败: %s", e2)
                        collected = f"（抱歉，处理您的问题时出错了：{e2}）"
                        yield {"type": "token", "content": collected}

                # 如果流式没有返回任何内容，用非流式兜底
                if not collected:
                    try:
                        fallback = chat(
                            self.messages,
                            tools=registry.schemas,
                            tool_choice="none",
                            provider=model_provider,
                        )
                        collected = fallback.choices[0].message.content or ""
                    except Exception as e2:
                        collected = f"（抱歉，处理您的问题时出错了：{e2}）"
                    if collected:
                        yield {"type": "token", "content": collected}

                self.add_assistant_message(collected)
                logger.info("回答完成（第%d轮）, 共 %d 字符", round_num + 1, len(collected))

                # ── 存入向量记忆 ──
                try:
                    self.vector_memory.add_turn(self.session_id, message, collected)
                except Exception as e:
                    logger.warning("向量记忆写入失败: %s", e)

                yield {"type": "done", "content": collected}
                return

            # ── 工具调用 ──
            tool_calls = choice.message.tool_calls
            logger.info(
                "第%d轮工具调用, 数量=%d, 工具=%s",
                round_num + 1,
                len(tool_calls),
                [tc.function.name for tc in tool_calls],
            )
            self.messages.append(choice.message.model_dump())

            for tool_call in tool_calls:
                result = self._execute_tool(tool_call)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
                self.add_tool_messages(tool_call.function.name, result)

        # 超过最大轮数，非流式兜底
        logger.warning("达到最大工具调用轮数 %d", MAX_TOOL_ROUNDS)
        final_response = chat(
            self.messages,
            tools=registry.schemas,
            tool_choice="none",
            provider=model_provider,
        )
        final_answer = final_response.choices[0].message.content
        self.add_assistant_message(final_answer)
        yield {"type": "done", "content": final_answer}

    def clear_memory(self):
        self.memory.clear_session(self.session_id)
        self.vector_memory.clear_session(self.session_id)
        system_prompt = (
            "你是一个友好的AI助手。你可以做以下事情：\n"
            "1. 查询天气：告诉用户输入城市名即可查天气\n"
            "2. 数学计算：进行精确的数学运算\n"
            "3. 今日热榜：查看GitHub趋势项目或百度热搜（默认GitHub）\n"
            "4. 知识库检索：从你的私有知识库中搜索专业内容来回答问题\n"
            "5. 联网搜索：检索互联网上的最新网页、新闻与实时信息\n"
            "你需要根据用户的问题自主决定调用哪个工具：\n"
            "  - 问天气 → weather\n"
            "  - 算数学 → calculator\n"
            "  - 问热榜 → get_hotlist\n"
            "  - 问知识库里的内容 → knowledge_search\n"
            "  - 需要联网查最新资讯/新闻/网页 → web_search\n"
            "  - 普通聊天 → 直接回答\n"
            "回答简洁友好，每次只回答用户的当前问题，不要提前列出一堆功能。"
        )
        self.messages = [{"role": "system", "content": system_prompt}]
        logger.info("记忆已清除, session=%s", self.session_id)
