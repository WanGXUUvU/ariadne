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
