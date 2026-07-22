import json
from fastapi import FastAPI, HTTPException, UploadFile, File, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent.agent import Agent
from auth import register as auth_register, login as auth_login, logout as auth_logout, verify_token, get_default_session, get_user_info as auth_get_user_info, update_display_name as auth_update_display_name, update_password as auth_update_password, get_user_sessions_list as auth_get_sessions, create_new_session as auth_create_session, delete_user_session as auth_delete_session, get_session_history as auth_get_session_history
from knowledge.pipeline import index_documents, query as rag_query
from pathlib import Path
import shutil
import uvicorn


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
        reply = agent.run(request.message, model_provider=request.model_provider)
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
            for event in agent.run_stream(request.message, model_provider=request.model_provider):
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


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
