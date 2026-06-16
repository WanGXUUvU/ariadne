import json
import tempfile
import unittest
from pathlib import Path

from backend.execution.runtime.vfs import StagingFileSystem
from backend.security.middleware.base import ToolCallContext
from backend.tools.registry import build_default_tool_registry


class TestFilesystemVfsTools(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.registry = build_default_tool_registry()
        self.vfs = StagingFileSystem()
        self.context = ToolCallContext(
            tool_name="",
            tool_args="{}",
            tool_call_id="call_test",
            session_id="session_test",
            run_id="run_test",
            vfs=self.vfs,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _execute(self, tool_name: str, args: dict):
        self.context.tool_name = tool_name
        self.context.tool_args = json.dumps(args)
        return self.registry.execute_tool_call(
            tool_name,
            json.dumps(args),
            self.context,
        )

    def test_write_then_read_uses_staged_content_without_touching_disk(self):
        file_path = self.root / "staged.txt"
        write_result = self._execute(
            "write_file",
            {"path": str(file_path), "content": "hello staged world"},
        )
        self.assertTrue(write_result.ok)
        self.assertFalse(file_path.exists())

        read_result = self._execute("read_file", {"path": str(file_path)})
        self.assertTrue(read_result.ok)
        self.assertEqual(read_result.content, "hello staged world")

    def test_search_sees_staged_new_files_and_hides_staged_deletes(self):
        old_file = self.root / "old.txt"
        old_file.write_text("remove me keyword\n", encoding="utf-8")
        self.vfs.delete_file(str(old_file))

        new_file = self.root / "nested" / "new.txt"
        self.vfs.write_text(str(new_file), "alpha\nkeyword in staged file\nomega")

        search_result = self._execute(
            "search_text",
            {"query": "keyword", "path": str(self.root)},
        )
        self.assertTrue(search_result.ok)
        self.assertIn("new.txt:2: keyword in staged file", search_result.content)
        self.assertNotIn("old.txt", search_result.content)

    def test_read_deleted_file_from_vfs_returns_structured_runtime_error(self):
        deleted_file = self.root / "deleted.txt"
        deleted_file.write_text("gone", encoding="utf-8")
        self.vfs.delete_file(str(deleted_file))

        read_result = self._execute("read_file", {"path": str(deleted_file)})
        self.assertFalse(read_result.ok)
        self.assertEqual(read_result.error.code, "tool_runtime_error")
        self.assertIn("File not found", read_result.error.message)


if __name__ == "__main__":
    unittest.main()
