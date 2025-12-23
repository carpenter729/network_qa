# 导入所有需要的库
import os
from contextlib import asynccontextmanager #用于管理生命周期
from fastapi import FastAPI, HTTPException,Depends #搭建API的骨架
from pydantic import BaseModel #定义数据格式（确保用户输入是"问题"，不是乱码）
from langchain_community.vectorstores import Chroma #向量数据库
from langchain_community.embeddings import HuggingFaceEmbeddings #嵌入模型，向量化，all-MiniLM-L6-v2轻量模型
from langchain_community.llms import LlamaCpp #加载本地大模型
from langchain_core.prompts import PromptTemplate #指导模型怎样回答问题
from langchain_core.runnables import RunnablePassthrough 
from langchain_core.output_parsers import StrOutputParser
from fastapi.responses import StreamingResponse #让回答"流式输出"
from sqlalchemy.orm import Session
from passlib.context import CryptContext#密码
import database as db#引入数据库

# 定义常量
VECTOR_DB_DIR = "vector_db"
MODEL_PATH = os.path.join("models", "mistral-7b-instruct-v0.2.Q4_K_M.gguf") # 确保这里的模型文件名与您下载的一致
EMBEDDING_MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2' #文本向量化的模型

# 获取数据库会话的依赖函数
def get_db():
    db_session = db.SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

# 密码加密上下文
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# 两个辅助函数
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)


# 定义生命周期管理器 (Lifespan)
# 替代原本的 @app.on_event("startup")
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("应用启动中...")

# 初始化数据库 (建表)
    print("正在初始化 SQLite 数据库...")
    db.init_db()
    
    # 检查模型文件和向量数据库是否存在
    if not os.path.exists(MODEL_PATH):
        print(f"错误：模型文件未找到，请确保 '{MODEL_PATH}' 存在。")
        yield
        return

    if not os.path.exists(VECTOR_DB_DIR):
        print(f"错误：向量数据库未找到，请确保 '{VECTOR_DB_DIR}' 存在。")
        print("您需要先运行 'build_database.py' 来创建数据库。")
        yield
        return

    # 将加载好的模型和组件存入 app.state，以便在API请求中重复使用
    print("正在加载嵌入模型...")
    app.state.embeddings_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': 'cuda'} # 如果没有显卡，请改为 'cpu'
    )

    print("正在加载向量数据库...")
    app.state.vector_db = Chroma(
        persist_directory=VECTOR_DB_DIR,
        embedding_function=app.state.embeddings_model
    )
    # 将数据库转换为一个检索器 (Retriever)
    app.state.retriever = app.state.vector_db.as_retriever(search_kwargs={"k": 3}) # k=3 表示每次检索返回3个最相关的文本块

    print("正在加载大语言模型 (LLM)... 这可能需要一些时间。")
    app.state.llm = LlamaCpp(
        model_path=MODEL_PATH,
        n_gpu_layers=-1,       # 设置为-1表示完全使用GPU。
        n_batch=512,          # 一次处理的token数
        n_ctx=8192,           # 模型的上下文窗口大小
        temperature=0.2,      # 温度参数
        max_tokens=2048,      # 单次生成的最大token数
        verbose=True,        # 设置为False以减少不必要的日志输出
    )
    
    print("--- 所有模型和数据库加载完毕，API准备就绪！ ---")
    
    yield # API 开始运行
    
    # 这里可以添加关闭应用时的清理代码（如果有）
    print("应用关闭中...")

# 初始化 FastAPI 应用
app = FastAPI(
    title="计算机网络知识问答API",
    description="一个使用RAG技术的智能问答系统API",
    lifespan=lifespan # 注入生命周期管理
)

# --- 3. 定义RAG链 (The RAG Chain) ---
def setup_rag_chain():
    # 定义提示模板 (Prompt Template)
    template = """
    [INST]
    您是一个专业的计算机网络知识问答助手。请根据下面提供的“上下文信息”来简洁、准确地回答用户的问题。
    如果“上下文信息”中没有相关内容，请回答“抱歉，根据我所掌握的知识，我无法回答这个问题。”
    不要编造信息，答案必须完全基于提供的上下文。
    [/INST]

    上下文信息:
    {context}

    用户问题:
    {question}

    回答:
    """
    prompt = PromptTemplate.from_template(template)

    # 定义RAG链
    rag_chain = (
        {"context": app.state.retriever, "question": RunnablePassthrough()} #检索
        | prompt #增强
        | app.state.llm #生成
        | StrOutputParser()
    )
    return rag_chain

# --- [新增] API 数据模型 ---
class LoginRequest(BaseModel):
    username: str
    password: str
class SaveMessageRequest(BaseModel):
    user_id: int
    role: str
    content: str

# 用户相关接口

@app.post("/login")
def login(request: LoginRequest, db_session: Session = Depends(get_db)):
    # 1. 查找用户是否存在
    user = db_session.query(db.User).filter(db.User.username == request.username).first()
    
    if not user:
        # --- 情况 A: 用户不存在 -> 注册新用户 ---
        # 对密码进行加密
        hashed_pwd = get_password_hash(request.password)
        new_user = db.User(username=request.username, hashed_password=hashed_pwd)
        db_session.add(new_user)
        db_session.commit()
        db_session.refresh(new_user)
        return {"user_id": new_user.id, "username": new_user.username, "message": "注册成功并登录"}
    
    else:
        # --- 情况 B: 用户存在 -> 验证密码 ---
        if verify_password(request.password, user.hashed_password):
            return {"user_id": user.id, "username": user.username, "message": "登录成功"}
        else:
            # 密码错误，抛出 401 异常
            raise HTTPException(status_code=401, detail="密码错误")

@app.get("/history/{user_id}")
def get_history(user_id: int, db_session: Session = Depends(get_db)):
    # 获取该用户的所有聊天记录
    messages = db_session.query(db.Message).filter(db.Message.user_id == user_id).all()
    return [{"role": m.role, "content": m.content} for m in messages]

@app.post("/save_message")
def save_message_endpoint(request: SaveMessageRequest, db_session: Session = Depends(get_db)):
    # 保存一条消息
    new_msg = db.Message(user_id=request.user_id, role=request.role, content=request.content)
    db_session.add(new_msg)
    db_session.commit()
    return {"status": "ok"}


# 定义API的输入和输出模型
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str

# 创建API端点

@app.post("/ask")
async def ask_question(request: QueryRequest):
    if not hasattr(app.state, 'llm'):
        raise HTTPException(status_code=503, detail="Service not ready")
    
    rag_chain = setup_rag_chain()
    def generate():
        for chunk in rag_chain.stream(request.question):
            yield chunk
    return StreamingResponse(generate(), media_type="text/plain")

# 用于测试的根端点
@app.get("/")
def read_root():
    return {"message": "欢迎来到计算机网络知识问答API！请访问 /docs 查看API文档。"}