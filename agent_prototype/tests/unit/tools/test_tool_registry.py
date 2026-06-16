import tempfile
import unittest
from pathlib import Path

from agent_prototype.security.middleware.base import ToolCallContext
from agent_prototype.tools.registry import build_default_tool_registry


class TestToolRegistry(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.registry = build_default_tool_registry()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_registry_exposes_echo_tool(self):
        tool_names = [
            schema["function"]["name"] for schema in self.registry.get_tool_schemas()
        ]
        self.assertIn("echo_tool", tool_names)

    def test_execute_read_file_tool_call(self):
        file_path = Path(self.temp_dir.name) / "sample.txt"
        file_path.write_text("hello registry", encoding="utf-8")
        result = self.registry.execute_tool_call(
            "read_file", f'{{"path":"{file_path}"}}'
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.content, "hello registry")

    def test_execute_list_dir_tool_call(self):
        folder_path = Path(self.temp_dir.name) / "folder"
        folder_path.mkdir()
        (folder_path / "b.txt").write_text("b", encoding="utf-8")
        (folder_path / "a.txt").write_text("a", encoding="utf-8")
        result = self.registry.execute_tool_call(
            "list_dir", f'{{"path":"{folder_path}"}}'
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.content, "a.txt\nb.txt")

    def test_execute_search_text_tool_call(self):
        folder_path = Path(self.temp_dir.name) / "search"
        folder_path.mkdir()
        target_file = folder_path / "sample.txt"
        target_file.write_text("hello world\nsearch me here\nbye", encoding="utf-8")
        result = self.registry.execute_tool_call(
            "search_text", f'{{"query":"search me","path":"{folder_path}"}}'
        )
        self.assertTrue(result.ok)
        self.assertIn("sample.txt", result.content)

    def test_execute_write_file_tool_call(self):
        file_path = Path(self.temp_dir.name) / "written.txt"
        result = self.registry.execute_tool_call(
            "write_file", f'{{"path":"{file_path}","content":"hello write"}}'
        )
        self.assertTrue(result.ok)
        self.assertTrue(file_path.exists())
        self.assertEqual(file_path.read_text(encoding="utf-8"), "hello write")

    def test_execute_list_dir_rewrites_relative_path_with_workspace_context(self):
        workspace_path = Path(self.temp_dir.name) / "workspace"
        target_dir = workspace_path / "src"
        target_dir.mkdir(parents=True)
        (target_dir / "a.txt").write_text("a", encoding="utf-8")
        (target_dir / "b.txt").write_text("b", encoding="utf-8")
        context = ToolCallContext(
            tool_name="list_dir",
            tool_args='{"path":"src"}',
            tool_call_id="call_123",
            session_id="session_123",
            workspace_path=str(workspace_path),
        )

        result = self.registry.execute_tool_call("list_dir", '{"path":"src"}', context)

        self.assertTrue(result.ok)
        self.assertEqual(result.content, "a.txt\nb.txt")

    def test_execute_read_file_blocks_workspace_escape(self):
        workspace_path = Path(self.temp_dir.name) / "workspace"
        workspace_path.mkdir()
        context = ToolCallContext(
            tool_name="read_file",
            tool_args='{"path":"../../../etc/passwd"}',
            tool_call_id="call_456",
            session_id="session_456",
            workspace_path=str(workspace_path),
        )

        result = self.registry.execute_tool_call(
            "read_file",
            '{"path":"../../../etc/passwd"}',
            context,
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "SANDBOX_VIOLATION")

    def test_unknown_tool_raises_structured_error(self):
        result = self.registry.execute_tool_call("missing_tool", "{}")
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "unknown_tool")

    def test_invalid_json_arguments_raises_structured_error(self):
        result = self.registry.execute_tool_call("echo_tool", "{bad json")
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "invalid_arguments")

    def test_tool_runtime_error_raises_structured_error(self):
        result = self.registry.execute_tool_call(
            "write_file",
            f'{{"path":"{self.temp_dir.name}","content":"hello"}}',
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "tool_runtime_error")
