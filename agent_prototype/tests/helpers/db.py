"""测试数据库与 TestClient helper。"""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent_prototype.infra.db.engine import Base


def make_sqlite_test_db(temp_dir: str, db_name: str):
    """创建文件型 sqlite 测试库并返回 engine 与 sessionmaker。"""
    db_path = Path(temp_dir) / db_name
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )


def build_test_client(app, get_db, session_local) -> TestClient:
    """覆盖 FastAPI 的 get_db 依赖并返回 TestClient。"""

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def reset_skill_loader_cache() -> None:
    """清空 skills loader 的短期缓存，避免跨测试污染。"""
    import agent_prototype.skills.loader as loader_module

    loader_module._list_skills_cache = None
    loader_module._list_skills_cache_ts = 0.0
