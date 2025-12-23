# 导入所有需要的库
import os
from langchain_community.document_loaders import DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# 定义知识库目录和向量数据库目录
KNOWLEDGE_BASE_DIR = "knowledge_base"
VECTOR_DB_DIR = "vector_db"

def main():
    """
    主函数，用于构建向量数据库。
    """
    print("阶段一：开始构建向量数据库...")

    # 1. 加载文档 (Load)

    # 我们使用DirectoryLoader来加载'knowledge_base'文件夹下所有.md文件
    # show_progress=True 可以在加载时显示进度条，非常友好
    print(f"正在从 '{KNOWLEDGE_BASE_DIR}' 文件夹加载文档...")
    try:
        loader = DirectoryLoader(KNOWLEDGE_BASE_DIR, glob="**/*.md", show_progress=True)
        documents = loader.load()
        if not documents:
            print("错误：在knowledge_base文件夹中没有找到任何.md文件。")
            print("请确保您已经将知识库文件（.md格式）放入该文件夹。")
            return
        print(f"成功加载了 {len(documents)} 篇文档。")
    except Exception as e:
        print(f"加载文档时出错：{e}")
        return

    # 2. 文本分割 (Split)
    
    # 为什么要分块？因为LLM处理的上下文长度是有限的。
    # 我们将长文档切分成小块，以便在检索时更精确。
    print("正在将文档分割成小文本块...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,      # 每个块的最大字符数
        chunk_overlap=200     # 相邻块之间重叠的字符数，有助于保持上下文连续性
    )
    chunks = text_splitter.split_documents(documents)
    print(f"文档被成功分割成 {len(chunks)} 个文本块。")

    # 3. 初始化嵌入模型 (Embedding Model)
   
    # 什么是嵌入？就是将文本转换成计算机能理解的数字向量。
    # 我们使用一个开源的、轻量且高效的模型 'all-MiniLM-L6-v2'
    # model_kwargs={'device': 'cpu'} 确保模型在CPU上运行
    print("正在初始化嵌入模型 'all-MiniLM-L6-v2'...")
    embeddings_model = HuggingFaceEmbeddings(
        model_name='sentence-transformers/all-MiniLM-L6-v2',
        model_kwargs={'device': 'cpu'}
    )
    print("嵌入模型初始化成功。")

    # 4. 创建并持久化向量数据库 (Vector Database)
    # ----------------------------------------------------------------
    # Chroma.from_documents 会为所有文本块生成嵌入向量，并将它们存入ChromaDB。
    # persist_directory 参数告诉Chroma将数据库文件保存在哪里。
    print(f"正在创建向量数据库并将其保存在 '{VECTOR_DB_DIR}'...")
    # 确保向量数据库目录存在
    if not os.path.exists(VECTOR_DB_DIR):
        os.makedirs(VECTOR_DB_DIR)

    # 这一步会花费一些时间，因为它需要为所有文本块计算向量
    db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings_model,
        persist_directory=VECTOR_DB_DIR
    )
    print("向量数据库创建并持久化成功！")
    print("\n阶段一完成！您现在可以在项目目录下看到一个 'vector_db' 文件夹。")

if __name__ == "__main__":
    main()
