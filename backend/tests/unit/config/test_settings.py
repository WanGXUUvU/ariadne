import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json

from backend.infra.config.settings import load_settings, save_settings

class TestSettings(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)
        self.test_settings_path = self.root_path / "settings.json"
        
        # Patch the SETTINGS_PATH to use our temp file
        self.path_patcher = patch("backend.infra.config.settings.SETTINGS_PATH", self.test_settings_path)
        self.path_patcher.start()

    def tearDown(self):
        self.path_patcher.stop()
        self.temp_dir.cleanup()

    def test_load_settings_creates_empty_file_if_not_exists(self):
        self.assertFalse(self.test_settings_path.exists())
        
        data = load_settings()
        
        self.assertEqual(data, {})
        self.assertTrue(self.test_settings_path.exists())
        self.assertEqual(self.test_settings_path.read_text(encoding="utf-8"), "{}")

    def test_load_settings_returns_parsed_json(self):
        self.test_settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.test_settings_path.write_text('{"foo": "bar"}', encoding="utf-8")
        
        data = load_settings()
        self.assertEqual(data, {"foo": "bar"})

    def test_load_settings_handles_invalid_json_gracefully(self):
        self.test_settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.test_settings_path.write_text('invalid-json{', encoding="utf-8")
        
        data = load_settings()
        self.assertEqual(data, {})

    def test_save_settings_overwrites_file(self):
        save_settings({"hello": "world"})
        
        self.assertTrue(self.test_settings_path.exists())
        content = json.loads(self.test_settings_path.read_text(encoding="utf-8"))
        self.assertEqual(content, {"hello": "world"})
