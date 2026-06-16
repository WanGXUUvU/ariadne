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
        "timeout": 30,  # 锁被占用时等待最多 30 秒
    },
)


# WAL 模式：允许并发读写，多线程下不互相阻塞
@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_conn, connection_record):
    """这是一个“数据库性能加速器（SQLite WAL模式连接事件监听器）”。
    当系统建立跟数据库的底层连接时，这个函数会自动被叫醒。它会去执行两条 SQLite 独有的优化命令：一是开启 WAL（Write-Ahead Logging）写前日志模式，能极大地提升数据库在多线程并发读写时的效率；二是将同步模式设为 NORMAL，让数据写入如飞，同时保证系统稳定性。

    需要拿到的东西：
    - dbapi_conn: 底层的 SQLite 物理连接对象。
    - connection_record: SQLAlchemy 的连接记录。
    """
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute(
        "PRAGMA synchronous=NORMAL"
    )  # WAL 下 NORMAL 已足够安全，写入更快


# ── ORM 基类 & 会话工厂 ───────────────────────────────────────────────────────

SessionLocal = sessionmaker(
    autoflush=False,
    autocommit=False,
    bind=engine,
)

Base = declarative_base()


# ── 依赖注入入口 ──────────────────────────────────────────────────────────────


def get_db():
    """统一获取数据库会话入口，供 FastAPI 依赖注入使用。

    这是一个“数据库钥匙借还处（Session 生成器函数）”。
    当网页接口（FastAPI 路由）或者业务服务需要读写数据库时，就可以从这里临时借一把打开数据库的“钥匙”（Session 实例）。当操作全部搞定、接口请求完成之后，这个函数还会非常严谨且礼貌地自动把这把钥匙“闭合关好（db.close()）”，防止数据库连接被占满。

    会给出来的结果：
    - generator: 一个可以 yield 出数据库会话 Session 对象的生成器。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
