import json
from fastapi import FastAPI, HTTPException, UploadFile, File, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent.agent import Agent
from auth import register as auth_register, login as auth_login, logout as auth_logout, verify_token, get_default_session, get_user_info as auth_get_user_info, update_display_name as auth_update_display_name, update_password as auth_update_password, get_user_sessions_list as auth_get_sessions, create_new_session as auth_create_session, delete_user_session as auth_delete_session, get_session_history as auth_get_session_history
from knowledge.pipeline import index_documents, query as rag_query, index_obsidian
from memory.memory import Memory
from chatbot.chatbot import get_available_models
from pathlib import Path
import shutil
import uvicorn
from utils.logger import get_logger

logger = get_logger(__name__)

# 用户级 LLM 密钥存储（建表在 Memory.__init__ 中完成）
memory = Memory()


app = FastAPI(
    title="Knowledge-Agent API",
    description="基于 DeepSeek + RAG 的智能 Agent 服务",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════
#  Agent 实例池
# ═══════════════════════════════════════════

_agent_pool: dict[str, Agent] = {}


def get_agent(session_id: str) -> Agent:
    """按 session_id 获取或创建 Agent 实例，避免每次请求重建"""
    if session_id not in _agent_pool:
        _agent_pool[session_id] = Agent(session_id)
    return _agent_pool[session_id]


# ═══════════════════════════════════════════
#  数据模型
# ═══════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"
    model_provider: str = "deepseek"


class LLMKeyRequest(BaseModel):
    """用户级 LLM 密钥：前端切换器用，每个用户可填自己的各厂商 key"""
    provider: str                       # deepseek | glm | qwen | yi
    api_key: str
    base_url: str = ""                  # 可选，缺省用该厂商默认 base_url
    model: str = ""                     # 可选，缺省用该厂商默认模型


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    model_provider: str = "deepseek"


class AuthRegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    success: bool
    message: str = ""
    token: str = ""
    session_id: str = ""
    user_id: int = 0


class UpdateProfileRequest(BaseModel):
    display_name: str


class UpdatePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UserProfileResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: str
    created_at: str = ""


class KnowledgeQueryRequest(BaseModel):
    question: str


class KnowledgeQueryResponse(BaseModel):
    answer: str


# ═══════════════════════════════════════════
#  通用接口
# ═══════════════════════════════════════════

# ═══════════════════════════════════════════
#  认证依赖
# ═══════════════════════════════════════════

async def get_current_user(authorization: str = Header("")):
    """从 Authorization header 解析用户"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    token = authorization.replace("Bearer ", "").strip()
    user_id = verify_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    return user_id


# ═══════════════════════════════════════════
#  认证接口
# ═══════════════════════════════════════════

@app.post("/auth/register", response_model=AuthResponse)
async def register_endpoint(request: AuthRegisterRequest):
    """用户注册"""
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    success, result = auth_register(request.username, request.email, request.password)
    if not success:
        raise HTTPException(status_code=400, detail=result)
    # result is token
    user_id = verify_token(result)
    session_id = get_default_session(user_id) or f"u{user_id}_default"
    return AuthResponse(success=True, token=result, session_id=session_id, user_id=user_id, message="注册成功")


@app.post("/auth/login", response_model=AuthResponse)
async def login_endpoint(request: AuthLoginRequest):
    """用户登录"""
    success, result = auth_login(request.username, request.password)
    if not success:
        raise HTTPException(status_code=401, detail=result)
    user_id = verify_token(result)
    session_id = get_default_session(user_id) or f"u{user_id}_default"
    return AuthResponse(success=True, token=result, session_id=session_id, user_id=user_id, message="登录成功")


@app.post("/auth/logout")
async def logout_endpoint(authorization: str = Header("")):
    """用户登出"""
    token = authorization.replace("Bearer ", "").strip()
    auth_logout(token)
    return {"success": True, "message": "已登出"}


# ========== 用户中心接口 ==========

@app.get("/user/profile", response_model=UserProfileResponse)
async def get_profile(user_id: int = Depends(get_current_user)):
    """获取当前用户信息"""
    info = auth_get_user_info(user_id)
    if info is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserProfileResponse(**info)


@app.put("/user/profile", response_model=dict)
async def update_profile(request: UpdateProfileRequest, user_id: int = Depends(get_current_user)):
    """修改显示名称"""
    if not request.display_name.strip():
        raise HTTPException(status_code=400, detail="显示名称不能为空")
    ok = auth_update_display_name(user_id, request.display_name.strip())
    if not ok:
        raise HTTPException(status_code=500, detail="修改失败")
    return {"success": True, "message": "名称已更新"}


@app.put("/user/password", response_model=dict)
async def update_password(request: UpdatePasswordRequest, user_id: int = Depends(get_current_user)):
    """修改密码"""
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    ok, msg = auth_update_password(user_id, request.old_password, request.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


# ========== 用户级 LLM 密钥（前端切换器用） ==========

@app.get("/user/llm-keys")
async def list_user_llm_keys(user_id: int = Depends(get_current_user)):
    """获取当前用户已配置的模型密钥（脱敏，不返回真实 key）"""
    keys = memory.get_user_llm_keys(user_id)
    configured = [k["provider"] for k in keys]
    return {"keys": keys, "configured_providers": configured}


@app.put("/user/llm-keys")
async def save_user_llm_key(request: LLMKeyRequest, user_id: int = Depends(get_current_user)):
    """保存（更新）某模型的用户级密钥"""
    ok = memory.set_user_llm_key(
        user_id, request.provider, request.api_key, request.base_url or "", request.model or ""
    )
    if not ok:
        raise HTTPException(status_code=400, detail="provider 非法或未提供 api_key")
    return {"success": True, "provider": request.provider}


@app.delete("/user/llm-keys/{provider}")
async def delete_user_llm_key_endpoint(provider: str, user_id: int = Depends(get_current_user)):
    """删除某模型的用户级密钥"""
    ok = memory.delete_user_llm_key(user_id, provider)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到该模型配置")
    return {"success": True, "provider": provider}


@app.get("/models")
async def list_models(user_id: int = Depends(get_current_user)):
    """返回所有模型及其配置状态：全局 available（.env 是否配 key）+ 用户已配，
    合并为 effective（true=真正用该模型，false=将静默回退 DeepSeek 兜底）。"""
    try:
        user_keys = memory.get_user_llm_keys(user_id)
        user_configured = {k["provider"] for k in user_keys}
    except Exception:
        user_configured = set()
    models = get_available_models()  # [{id,label,role,available}]
    result = []
    for m in models:
        uc = m["id"] in user_configured
        g_available = bool(m.get("available", False))
        result.append({
            "id": m["id"],
            "available": g_available,         # 全局 .env 是否配了 key
            "user_configured": uc,            # 该用户是否在前端填了自己的 key
            "effective": g_available or uc,   # 真正可用（不兜底）
        })
    return {"models": result}


# ========== 会话管理接口 ==========

@app.get("/user/sessions")
async def list_sessions(user_id: int = Depends(get_current_user)):
    """获取用户的所有会话"""
    sessions = auth_get_sessions(user_id)
    return {"sessions": sessions}


@app.post("/user/sessions")
async def create_session(user_id: int = Depends(get_current_user)):
    """创建新会话"""
    session_id = auth_create_session(user_id)
    return {"session_id": session_id, "label": "新对话", "msg_count": 0}


@app.delete("/user/sessions/{session_id}")
async def delete_session(session_id: str, user_id: int = Depends(get_current_user)):
    """删除会话（验证归属，防越权删除他人会话）"""
    ok = auth_delete_session(user_id, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在或不属于当前用户")
    return {"success": True, "session_id": session_id}


@app.get("/user/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, limit: int = 200, user_id: int = Depends(get_current_user)):
    """获取指定会话的历史消息（已验证归属，防越权）"""
    history = auth_get_session_history(user_id, session_id, limit=limit)
    if history is None:
        raise HTTPException(status_code=404, detail="会话不存在或不属于当前用户")
    return {"session_id": session_id, "messages": history}


@app.get("/")
async def root():
    return {
        "message": "Knowledge-Agent 服务运行中",
        "docs": "/docs",
        "status": "active",
    }


# ═══════════════════════════════════════════
#  聊天接口（Agent）
# ═══════════════════════════════════════════

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, user_id: int = Depends(get_current_user)):
    try:
        agent = get_agent(request.session_id)
        reply = agent.run(request.message, model_provider=request.model_provider, user_id=user_id)
        return ChatResponse(
            reply=reply,
            session_id=request.session_id,
            model_provider=request.model_provider,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 处理失败: {str(e)}")


@app.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest, user_id: int = Depends(get_current_user)):
    """流式聊天接口（SSE），打字机效果"""
    agent = get_agent(request.session_id)

    async def event_generator():
        try:
            for event in agent.run_stream(request.message, model_provider=request.model_provider, user_id=user_id):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════════════════════════════════
#  知识库管理接口
# ═══════════════════════════════════════════

UPLOAD_DIR = Path("knowledge/docs")
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}


@app.post("/knowledge/upload")
async def upload_document(file: UploadFile = File(...)):
    """上传文档到知识库（PDF/TXT/MD）"""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {suffix}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_DIR / file.filename

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    return {
        "status": "success",
        "filename": file.filename,
        "path": str(file_path),
        "message": f"文件 {file.filename} 已上传，请调用 /knowledge/index 进行索引",
    }


@app.post("/knowledge/index")
async def index_knowledge():
    """索引 knowledge/docs/ 下的所有文档到向量库"""
    try:
        count = index_documents()
        return {
            "status": "success",
            "indexed_chunks": count,
            "message": f"索引完成，{count} 个切片已入库",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"索引失败: {str(e)}")


@app.post("/knowledge/query", response_model=KnowledgeQueryResponse)
async def query_knowledge(request: KnowledgeQueryRequest):
    """基于知识库生成回答"""
    try:
        answer = rag_query(request.question)
        return KnowledgeQueryResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


# ========== Obsidian 知识库接口（独立 collection，排除隐私文件）==========

@app.post("/obsidian/index")
async def index_obsidian_endpoint(force: bool = False):
    """增量索引 Obsidian vault 到独立向量集合（自动排除 OBSIDIAN_EXCLUDE 清单中的隐私文件）。

    - force=false：仅处理新增/变更/删除的文件（按 mtime 判断），效率高。
    - force=true：清空后全量重建（vault 大改后使用）。
    """
    try:
        result = index_obsidian(force=force)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return {
            "status": "success",
            "result": result,
            "message": "Obsidian 索引完成：{} 文件 / {} 切片".format(
                result.get("indexed_files", 0), result.get("chunks", 0)
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"索引失败: {str(e)}")


@app.get("/obsidian/status")
async def obsidian_status():
    """查看 Obsidian 索引状态：vault 路径、排除清单、已索引切片数。"""
    from config import OBSIDIAN_VAULT_DIR, OBSIDIAN_COLLECTION, OBSIDIAN_EXCLUDE
    from knowledge.vector_store import get_vector_store

    try:
        store = get_vector_store(OBSIDIAN_COLLECTION)
        count = store.count()
    except Exception:
        count = -1
    return {
        "vault_dir": OBSIDIAN_VAULT_DIR,
        "collection": OBSIDIAN_COLLECTION,
        "excluded": OBSIDIAN_EXCLUDE,
        "indexed_chunks": count,
        "configured": bool(OBSIDIAN_VAULT_DIR),
    }


@app.on_event("startup")
def _startup_obsidian_watcher():
    """后端启动时自动拉起 Obsidian 文件监视器（若已配置 vault）。"""
    try:
        from knowledge.obsidian_watcher import start_obsidian_watcher
        start_obsidian_watcher()
    except Exception as e:  # noqa: BLE001
        logger.warning("启动 Obsidian 监视器失败（不影响主服务）: %s", e)


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
