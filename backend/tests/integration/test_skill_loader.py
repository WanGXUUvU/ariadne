import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json

from backend.skills.loader import list_skills


class TestSkillLoader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)
        self.test_settings_path = self.root_path / "settings.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_skill(self, source_dir: Path, skill_name: str, content: str):
        skill_dir = source_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def test_list_skills_returns_enabled_and_disabled_entries(self):
        project_skills_root = self.root_path / "project-skills"
        user_skills_root = self.root_path / "user-skills"

        self._write_skill(
            project_skills_root,
            "alpha-skill",
            "---\nname: Alpha Skill\ndescription: Alpha summary\n---\n# Alpha\n",
        )
        self._write_skill(
            user_skills_root,
            "broken-skill",
            "name: Broken Skill\n# Missing frontmatter\n",
        )

        # 写入包含自定义 roots 的 settings.json
        settings_data = {
            "skills": {
                "roots": [
                    {"name": "project-opencode", "path": str(project_skills_root)},
                    {"name": "user-codex", "path": str(user_skills_root)},
                ]
            }
        }
        self.test_settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.test_settings_path.write_text(json.dumps(settings_data), encoding="utf-8")

        with patch("backend.infra.config.settings.SETTINGS_PATH", self.test_settings_path):
            results = list_skills()

        self.assertEqual(len(results), 2)
        by_name = {item.name: item for item in results}
        self.assertTrue(by_name["Alpha Skill"].enabled)
        self.assertFalse(by_name["broken-skill"].enabled)

    def test_list_skills_applies_disabled_config(self):
        project_skills_root = self.root_path / "project-skills"

        self._write_skill(
            project_skills_root,
            "alpha-skill",
            "---\nname: Alpha Skill\ndescription: Alpha summary\n---\n# Alpha\n",
        )

        # 写入同时包含 roots 和 disabled 的 settings.json
        settings_data = {
            "skills": {
                "roots": [
                    {"name": "project-opencode", "path": str(project_skills_root)}
                ],
                "disabled": ["Alpha Skill"]
            }
        }
        self.test_settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.test_settings_path.write_text(json.dumps(settings_data), encoding="utf-8")

        with patch("backend.infra.config.settings.SETTINGS_PATH", self.test_settings_path):
            results = list_skills()

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].enabled)
