# database.py
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 1. 定义数据库地址 (直接在当前目录下生成 sql_app.db 文件)
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"

# 2. 创建数据库引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 3. 创建会话工厂 (用来与数据库对话的工具)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. 定义基类
Base = declarative_base()

# --- 定义表结构 (Models) ---

# 用户表
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True) # 用户名唯一
    hashed_password = Column(String)#存储哈希后的密码，而不是明文
    created_at = Column(DateTime, default=datetime.now)

# 聊天记录表
class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True) # 关联到哪个用户
    role = Column(String)    # "user" 或 "assistant"
    content = Column(Text)   # 聊天内容
    timestamp = Column(DateTime, default=datetime.now)

# --- 初始化数据库函数 ---
def init_db():
    # 这句话会根据上面的类，自动在数据库里建表
    Base.metadata.create_all(bind=engine)