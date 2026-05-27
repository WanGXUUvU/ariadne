"""基础设施层 (Infrastructure Layer) - SQLAlchemy 数据库引擎

职责：
1. 初始化物理 SQLite 数据库文件连接。
2. 创建全局线程安全的 SQLAlchemy Engine 与会话工厂 SessionLocal。
3. 提供统一的 get_db 上游生命周期函数。

不负责：
1. 具体的 ORM 数据表模型声明。
2. 业务数据的任何逻辑加工。

数据流向：
- 输入：本地数据库物理连接路径（URL）。
- 输出：SessionLocal 会话工厂。
- 上游来源：FastAPI 依赖注入（Dependencies）。
- 下游流向：供所有 Persistence 层 Service 直接调用执行物理 SQL。
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker


# ── 连接配置 ──────────────────────────────────────────────────────────────────

DATABASE_URL = "sqlite:///./agent_session.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,          # 锁被占用时等待最多 30 秒
    },
)

# WAL 模式：允许并发读写，多线程下不互相阻塞
@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA synchronous=NORMAL")  # WAL 下 NORMAL 已足够安全，写入更快


# ── ORM 基类 & 会话工厂 ───────────────────────────────────────────────────────

SessionLocal = sessionmaker(
    autoflush=False,
    autocommit=False,
    bind=engine,
)

Base = declarative_base()


# ── 依赖注入入口 ──────────────────────────────────────────────────────────────

def get_db():
    """统一获取数据库会话入口，供 FastAPI 依赖注入使用。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
