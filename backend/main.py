import os
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# FastAPI 核心组件 
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse

# 限流工具 
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# 数据模型与数据库
from pydantic import BaseModel
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
import database as db

# LangChain 组件 
from langchain_openai import ChatOpenAI 
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# ================= 配置区域 =================
# 安全密钥 (生产环境需修改为复杂的随机字符串)
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-it-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # Token 有效期 1 天

# 路径配置
VECTOR_DB_DIR = "vector_db"
EMBEDDING_MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'
INFERENCE_SERVER_URL = "http://localhost:8001/v1" # 指向独立运行的推理服务

# ================= 工具初始化 =================

# 1. 密码加密工具
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# 2. OAuth2 鉴权方案
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 3. 限流器初始化 (基于客户端 IP)
limiter = Limiter(key_func=get_remote_address)

# ================= 辅助函数 =================

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ================= 依赖注入 =================

# 数据库会话依赖
def get_db():
    db_session = db.SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

# 当前用户依赖 (JWT 验证)
async def get_current_user(token: str = Depends(oauth2_scheme), db_session: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db_session.query(db.User).filter(db.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# ================= 生命周期管理 =================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(">>> 应用启动中...")
    
    # 1. 初始化数据库表结构
    db.init_db()
    
    # 2. 检查向量库是否存在
    if not os.path.exists(VECTOR_DB_DIR):
        print(f"⚠️ 警告：向量库目录 '{VECTOR_DB_DIR}' 未找到。请先运行 build_database.py。")
    
    # 3. 加载本地嵌入模型 (用于检索)
    print(">>> 正在加载嵌入模型...")
    app.state.embeddings_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': 'cuda'} # 无显卡请改为 'cpu'
    )

    # 4. 加载向量检索器
    print(">>> 正在加载向量数据库...")
    try:
        app.state.vector_db = Chroma(
            persist_directory=VECTOR_DB_DIR,
            embedding_function=app.state.embeddings_model
        )
        app.state.retriever = app.state.vector_db.as_retriever(search_kwargs={"k": 3})
    except Exception as e:
        print(f"⚠️ 向量库加载失败: {e}")

    # 5. 连接外部推理服务
    print(f">>> 正在连接推理服务 ({INFERENCE_SERVER_URL})...")
    try:
        app.state.llm = ChatOpenAI(
            base_url=INFERENCE_SERVER_URL,
            api_key="sk-no-key-required", # 本地服务无需真实 Key
            model="mistral-7b-instruct",
            temperature=0.2,
            streaming=True
        )
        print(">>> ✅ 推理服务连接配置完成")
    except Exception as e:
        print(f"⚠️ 连接推理服务失败: {e}")

    yield 
    print(">>> 应用关闭中...")

# ================= App 初始化 =================
app = FastAPI(
    title="Network QA System",
    description="Enterprise-grade RAG System",
    lifespan=lifespan
)

# 挂载限流器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生产环境建议改为 ["http://localhost", "http://your-domain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= Pydantic 模型 =================
class Token(BaseModel):
    access_token: str
    token_type: str
    username: str

class UserCreate(BaseModel):
    username: str
    password: str

class QueryRequest(BaseModel):
    question: str

# ================= API 接口 =================

# 1. 用户注册
@app.post("/register", response_model=Token)
@limiter.limit("10/minute") # 限流：注册接口每分钟最多访问10次
def register(request: Request, user: UserCreate, db_session: Session = Depends(get_db)):
    db_user = db_session.query(db.User).filter(db.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = db.User(username=user.username, hashed_password=hashed_password)
    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)
    
    access_token = create_access_token(data={"sub": new_user.username})
    return {"access_token": access_token, "token_type": "bearer", "username": new_user.username}

# 2. 用户登录 (OAuth2)
@app.post("/token", response_model=Token)
@limiter.limit("20/minute") # 限流：登录接口每分钟最多20次
def login_for_access_token(
    request: Request, 
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db_session: Session = Depends(get_db)
):
    user = db_session.query(db.User).filter(db.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer", "username": user.username}

# 3. 获取历史记录
@app.get("/history")
def get_history(current_user: db.User = Depends(get_current_user)):
    return [{"role": m.role, "content": m.content} for m in current_user.messages]

# 4. 智能问答 (RAG核心)
@app.post("/ask")
@limiter.limit("5/minute") # 限流保护：每分钟最多提问 5 次，防止显卡过热
async def ask_question(
    request: Request, # 必须添加 Request 参数供 limiter 使用
    query_req: QueryRequest, 
    current_user: db.User = Depends(get_current_user), 
    db_session: Session = Depends(get_db)
):
    # 1. 保存用户提问
    user_msg = db.Message(content=query_req.question, role="user", user_id=current_user.id)
    db_session.add(user_msg)
    db_session.commit()

    # 2. 构建提示词 (双语强指令)
    system_template = """You are a professional network assistant.
    Context information is below.
    ---------------------
    {context}
    ---------------------
    
    CRITICAL INSTRUCTION:
    1. If the user asks in Chinese, you MUST answer in CHINESE (中文).
    2. If the user asks in English, answer in English.
    3. Answer based ONLY on the provided context.
    4. If you don't know, say so. Do not make up info.
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", "{question}")
    ])
    
    # 3. 组装RAG链
    rag_chain = (
        {"context": app.state.retriever, "question": RunnablePassthrough()} 
        | prompt 
        | app.state.llm 
        | StrOutputParser()
    )

    # 4. 生成与流式响应
    async def generate():
        full_response = ""
        try:
            # 调用独立推理服务
            async for chunk in rag_chain.astream(query_req.question):
                full_response += chunk
                yield chunk
        except Exception as e:
            error_msg = f"\n[System Error: Failed to connect to inference server. {str(e)}]"
            yield error_msg
            full_response += error_msg

        # 5. 保存 AI 回答 (使用新会话避免异步冲突)
        new_db = db.SessionLocal()
        try:
            ai_msg = db.Message(content=full_response, role="assistant", user_id=current_user.id)
            new_db.add(ai_msg)
            new_db.commit()
        except Exception as e:
            print(f"Error saving chat history: {e}")
        finally:
            new_db.close()

    return StreamingResponse(generate(), media_type="text/plain")

@app.get("/")
def read_root():
    return {"message": "Network QA API is running securely."}