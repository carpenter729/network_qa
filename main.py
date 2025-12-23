# 导入所有需要的库
import os
from contextlib import asynccontextmanager #用于管理生命周期
from fastapi import FastAPI, HTTPException #搭建API的骨架
from pydantic import BaseModel #定义数据格式（确保用户输入是"问题"，不是乱码）
from langchain_community.vectorstores import Chroma #向量数据库
from langchain_community.embeddings import HuggingFaceEmbeddings #嵌入模型，向量化，all-MiniLM-L6-v2轻量模型
from langchain_community.llms import LlamaCpp #加载本地大模型
from langchain_core.prompts import PromptTemplate #指导模型怎样回答问题
from langchain_core.runnables import RunnablePassthrough 
from langchain_core.output_parsers import StrOutputParser
from fastapi.responses import StreamingResponse #让回答"流式输出"

# 定义常量
VECTOR_DB_DIR = "vector_db"
MODEL_PATH = os.path.join("models", "mistral-7b-instruct-v0.2.Q4_K_M.gguf") # 确保这里的模型文件名与您下载的一致
EMBEDDING_MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2' #文本向量化的模型

# 定义生命周期管理器 (Lifespan)
# 替代原本的 @app.on_event("startup")
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("应用启动中...")
    
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

# 定义API的输入和输出模型
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str

# 创建API端点

@app.post("/ask") 
async def ask_question(request: QueryRequest):
    """
    接收用户的问题，通过RAG链处理，并以流式(Stream)返回答案。
    """
    # 检查模型是否已成功加载
    if not hasattr(app.state, 'llm'):
        raise HTTPException(status_code=503, detail="模型正在加载或加载失败，请稍后再试。")

    # 构建 RAG 链
    rag_chain = setup_rag_chain()
    
    print(f"收到问题: {request.question}")

    # 定义生成器函数
    def generate_response():
        try:
            for chunk in rag_chain.stream(request.question): #LangChain的黑科技，让模型边生成边输出
                yield chunk 
        except Exception as e:
            print(f"生成过程中出错: {e}")
            yield f"Error: {str(e)}"

    # 返回流式响应
    return StreamingResponse(generate_response(), media_type="text/plain")

# 用于测试的根端点
@app.get("/")
def read_root():
    return {"message": "欢迎来到计算机网络知识问答API！请访问 /docs 查看API文档。"}