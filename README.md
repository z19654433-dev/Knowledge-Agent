# 🧠 AI Agent · Python + DeepSeek + React

> 一个基于 **DeepSeek API** 和 **FastAPI** 的智能 Agent 全栈项目，具备长期记忆、多会话隔离、自主工具调用（Function Calling）能力，附带 **React 聊天界面**。

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-API-orange.svg)](https://deepseek.com/)
[![React](https://img.shields.io/badge/React-19+-61DAFB.svg)](https://react.dev/)

---

## ✨ 功能特性

- 🤖 **Agent 架构**：模块化设计（Agent / Tools / Memory / Chatbot 分层解耦）
- 🧠 **Function Calling 自主决策**：DeepSeek 动态决定调用哪个工具、提取哪些参数
- 🔧 **装饰器工具注册**：`@registry.register()` 一行注册，自动生成 JSON Schema
- 🔒 **安全数学计算**：AST 白名单求值器，替换危险的 `eval()`
- 💬 **长期记忆**：SQLite 持久化对话历史，支持多会话隔离
- 🌐 **RESTful API**：FastAPI 提供 `/chat` 接口，Swagger 交互文档
- 🎨 **React 前端**：Vite + TypeScript + Tailwind CSS 聊天界面
- 📝 **结构化日志**：基于标准 logging，控制台彩色输出
- 🐳 **容器化就绪**：Dockerfile 一键部署

---

## 🗂️ 项目结构

```
AI-Workspace/
├── api.py                    # FastAPI 服务入口
├── app.py                    # 终端交互入口（CLI）
├── config.py                 # 环境变量加载
├── requirements.txt          # Python 依赖
├── Dockerfile                # 容器化配置
│
├── agent/
│   ├── agent.py              # Agent 调度器：消息管理 + 工具协调 + 记忆集成
│   └── __init__.py
│
├── chatbot/
│   └── chatbot.py            # OpenAI SDK 调用 DeepSeek API
│
├── tools/
│   ├── __init__.py           # ToolRegistry + @registry.register() 装饰器
│   ├── calculator.py         # 安全数学计算（AST 白名单）
│   ├── weather.py            # 天气查询（mock 数据）
│   └── hotlist.py            # 今日热榜（GitHub 趋势 / 百度热搜）
│
├── memory/
│   └── memory.py             # SQLite 持久化 CRUD
│
├── utils/
│   └── logger.py             # 日志模块（标准 logging）
│
└── frontend/                 # React 聊天界面
    ├── vite.config.ts        # Vite 配置（Tailwind + API 代理）
    ├── src/
    │   ├── App.tsx           # 聊天主界面
    │   ├── index.css         # Tailwind 入口
    │   └── main.tsx          # React 入口
    └── package.json
```

---

## 🛠️ 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | Python 3.12 + FastAPI + Uvicorn |
| 大模型 | DeepSeek API（OpenAI 兼容 SDK） |
| 持久化 | SQLite |
| 数据校验 | Pydantic |
| 前端框架 | React 19 + TypeScript |
| 构建工具 | Vite |
| 样式 | Tailwind CSS 4 |
| 容器化 | Docker |

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/z19654433-dev/AI-Workspace.git
cd AI-Workspace
```

### 2. 配置后端

```bash
# 创建虚拟环境
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 创建 .env 文件，填入你的 DeepSeek API Key
echo DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxx > .env
```

### 3. 启动后端

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

访问 http://127.0.0.1:8000/docs 查看 Swagger 文档。

### 4. 启动前端（新开一个终端）

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173 即可开始对话。

### 5. 测试 API

```bash
curl -X POST "http://127.0.0.1:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{"message": "今天 GitHub 有什么热门项目", "session_id": "test"}'
```

---

## 🔧 现有工具

| 工具 | 功能 | 调用示例 |
|------|------|---------|
| `calculate` | 安全数学计算 | "计算 12345 × 678" |
| `get_weather` | 查询天气 | "今天河南天气怎么样" |
| `get_hotlist` | 今日热榜 | "看看 GitHub 趋势" / "百度热搜" |

### 加新工具

```python
from tools import registry

@registry.register(description="查询新闻")
def get_news(topic: str) -> str:
    """获取指定主题的最新新闻"""
    return f"{topic}的最新新闻..."
```

装饰器自动解析参数类型、生成 Schema、注册到全局注册表。

---

## 📈 版本路线

| 版本 | 功能 | 状态 |
|------|------|------|
| V1 | 终端交互 CLI | ✅ |
| V2 | DeepSeek API 接入 | ✅ |
| V3 | 上下文记忆（内存） | ✅ |
| V4 | SQLite 长期记忆 + 多会话 | ✅ |
| V5 | FastAPI 服务化 + Swagger | ✅ |
| V6 | Function Calling 自主决策 | ✅ |
| V7 | 装饰器注册 + 安全求值器 | ✅ |
| V8 | 热榜工具 + 日志模块 | ✅ |
| V9 | React 前端聊天界面 | ✅ |
| V10 | LangChain 集成（可选） | ⏳ 计划中 |
| V11 | MCP 协议接入 | ⏳ 计划中 |

---

## 🐳 Docker 部署

```bash
docker build -t ai-agent .
docker run -p 8000:8000 ai-agent
```

---

## 📄 License

MIT License © 2026
