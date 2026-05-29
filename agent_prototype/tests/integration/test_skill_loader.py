import tempfile
import unittest
from pathlib import Path

from agent_prototype.skills.loader import list_skills


class TestSkillLoader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)

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
            user_skills_root, "broken-skill", "name: Broken Skill\n# Missing frontmatter\n"
        )

        results = list_skills(
            [
                ("project-opencode", project_skills_root),
                ("user-codex", user_skills_root),
            ]
        )

        self.assertEqual(len(results), 2)
        by_name = {item.name: item for item in results}
        self.assertTrue(by_name["Alpha Skill"].enabled)
        self.assertFalse(by_name["broken-skill"].enabled)

    def test_list_skills_applies_disabled_config(self):
        project_skills_root = self.root_path / "project-skills"
        config_path = self.root_path / "skill-config.json"

        self._write_skill(
            project_skills_root,
            "alpha-skill",
            "---\nname: Alpha Skill\ndescription: Alpha summary\n---\n# Alpha\n",
        )
        config_path.write_text('{"disabled": ["Alpha Skill"]}', encoding="utf-8")

        results = list_skills(
            [("project-opencode", project_skills_root)],
            config_path=config_path,
        )

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].enabled)
