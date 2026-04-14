# import sqlite3
# from pathlib import Path

# db_file=Path(__file__).parent/"todo.db"

# def get_connection():
#     conn=sqlite3.connect(db_file)
#     conn.row_factory=sqlite3.Row
#     return conn

# def init_db():
#     conn=get_connection()
#     cursor=conn.cursor()

#     cursor.execute("""
#     CREATE TABLE IF NOT EXISTS todos (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         title TEXT NOT NULL
#     )
#     """)

#     conn.commit()
#     conn.close()


from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base,sessionmaker

DATEBASE_URL="sqlite:///./todo.db"
#创建数据库引擎
engine=create_engine(
    url=DATEBASE_URL,
    connect_args={"check_same_thread":False}
)
#用来生成数据库会话工厂
SessionLocal=sessionmaker(
    autoflush=False,
    autocommit=False,
    bind=engine
)
#BASE:所有ORM表模型的父类
Base=declarative_base()


def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()
    
    