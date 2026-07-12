from chatbot.chatbot import chat
from tools.registry import tools
from memory.memory import Memory   # 新增导入


class Agent:

    def __init__(self, session_id: str = "default_session"):
        self.name = "MyAgent"
        self.session_id = session_id

        # 初始化记忆模块
        self.memory = Memory()

        # 加载历史记忆（最近20条）
        history = self.memory.load_history(self.session_id, limit=20)

        # 构建 messages：system + 历史记录
        self.messages = [
            {
                "role": "system",
                "content": "你是一个友好的AI助手"
            }
        ]
        self.messages.extend(history)  # 把数据库里的历史追加进去

    def add_user_message(self, content):
        self.messages.append({"role": "user", "content": content})
        # 立即存入数据库
        self.memory.save_message(self.session_id, "user", content)

    def add_assistant_message(self, content):
        self.messages.append({"role": "assistant", "content": content})
        # 立即存入数据库
        self.memory.save_message(self.session_id, "assistant", content)

    def run(self, message):
        # 天气工具
        if "天气" in message:
            self.add_user_message(message)

            # 提取城市（简单版，后续可以用 AI 提取）
            if "河南" in message:
                city = "河南"
            elif "北京" in message:
                city = "北京"
            elif "上海" in message:
                city = "上海"
            else:
                # 兼容更多城市：如果没匹配到，就用 AI 提取（临时方案）
                # 或者直接返回提示
                city = None
                answer = "暂不支持该城市天气查询，请说「北京天气」或「上海天气」"
                self.add_assistant_message(answer)
                return answer

            if city:
                answer = tools["weather"](city)
                self.add_assistant_message(answer)
                return answer

        # 计算工具
        if "计算" in message:
            self.add_user_message(message)

            # 更精确提取表达式：去掉「计算」及其前后的空格
            import re
            match = re.search(r"计算\s*(.+)", message)
            if match:
                expression = match.group(1).strip()
            else:
                expression = message.replace("计算", "").strip()

            # 如果表达式为空，返回提示
            if not expression:
                answer = "请告诉我需要计算什么，例如「计算 1+1」"
                self.add_assistant_message(answer)
                return answer

            answer = tools["calculator"](expression)
            self.add_assistant_message(answer)
            return answer

        # 普通聊天
        self.add_user_message(message)
        answer = chat(self.messages)
        self.add_assistant_message(answer)
        return answer

    def clear_memory(self):
        """清空当前会话的记忆（慎用）"""
        self.memory.clear_session(self.session_id)
        # 重置 messages 仅保留 system
        self.messages = [{"role": "system", "content": "你是一个友好的AI助手"}]