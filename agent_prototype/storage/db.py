from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base,sessionmaker

DATABASE_URL="sqlite:///./agent_session.db"
engine=create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread":False}
)

SessionLocal=sessionmaker(
    autoflush=False,
    autocommit=False, 
    bind=engine,
)
Base=declarative_base()


def get_db(): #统一获取数据库会话入口
    """输入：无。输出：一个可迭代的数据库会话生成器，供 FastAPI 依赖注入使用。"""
    db =SessionLocal() 
    try:
        yield db #把会话交给路由
    finally:
        db.close()
