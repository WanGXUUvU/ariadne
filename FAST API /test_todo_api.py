import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import app
from db import Base, get_db


class TodoApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test_todo.db"
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        TestingSessionLocal = sessionmaker(
            autoflush=False,
            autocommit=False,
            bind=self.engine,
        )

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_delete_then_get_returns_404(self):
        create_response = self.client.post(
            "/todos",
            json={"title": "学习测试", "done": False, "priority": 1},
        )
        self.assertEqual(create_response.status_code, 201)
        created_todo = create_response.json()
        todo_id = created_todo["id"]

        delete_response = self.client.delete(f"/todos/{todo_id}")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["id"], todo_id)

        get_response = self.client.get(f"/todos/{todo_id}")
        self.assertEqual(get_response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
