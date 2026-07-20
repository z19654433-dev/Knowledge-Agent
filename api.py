from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.agent import Agent
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


class KnowledgeQueryRequest(BaseModel):
    question: str


class KnowledgeQueryResponse(BaseModel):
    answer: str


# ═══════════════════════════════════════════
#  通用接口
# ═══════════════════════════════════════════

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
async def chat_endpoint(request: ChatRequest):
    try:
        agent = Agent(session_id=request.session_id)
        reply = agent.run(request.message, model_provider=request.model_provider)
        return ChatResponse(
            reply=reply,
            session_id=request.session_id,
            model_provider=request.model_provider,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 处理失败: {str(e)}")


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
