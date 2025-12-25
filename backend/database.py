from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime
from dotenv import load_dotenv # 导入加载器
import os

# 加载 .env 文件里的变量
load_dotenv()

# 配置 PostgreSQL 连接地址
# 格式: postgresql://用户名:密码@地址:端口/数据库名
db_password = os.getenv("DB_PASSWORD", "123456")
SQLALCHEMY_DATABASE_URL = f"postgresql://postgres:{db_password}@localhost/network_qa_db"


# 创建引擎
engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# 下面的表结构不需要动，ORM 会自动适配 Postgres

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    messages = relationship("Message", back_populates="owner")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    role = Column(String) 
    timestamp = Column(DateTime, default=datetime.now)
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="messages")

def init_db():
    Base.metadata.create_all(bind=engine)