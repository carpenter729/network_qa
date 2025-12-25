# Network QA - 基于 RAG 的计算机网络智能问答系统

这是一个基于大语言模型（LLM）和检索增强生成（RAG）技术的全栈智能问答系统。它可以根据本地知识库（Markdown文档）回答专业的计算机网络问题。

#架构设计

- 前端: React + Vite + Tailwind CSS (PWA 支持)
- 后端: FastAPI + LangChain + PostgreSQL
- AI 模型: Mistral-7B (GGUF) + ChromaDB (向量检索)
- 部署: Nginx 反向代理 + Docker (可选)

##快速开始

###环境准备
- Python 3.10+
- Node.js 18+
- PostgreSQL 数据库
- 下载模型文件 `mistral-7b-instruct-v0.2.Q4_K_M.gguf` 并放入 `backend/models/` 目录。

###后端设置
```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt

# 初始化知识库
python build_database.py

# 启动 API 服务
uvicorn main:app --reload --port 8000

###前端设置
cd frontend
npm install
npm run dev
#启动推理服务：
python -m llama_cpp.server --model models/mistral-7b-instruct-v0.2.Q4_K_M.gguf --port 8001

前端和后端文件夹里面均已列出依赖库requirement.txt，构建环境时务必参考

