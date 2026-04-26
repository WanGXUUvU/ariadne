# TASK-009 - 显式选择 SkillPack

## 目标
让调用方可以显式指定使用哪个 SkillPack，为后续自动路由打基础。

## 产品层
产品表面层（Product Surface）

## 范围内
- 给 `AgentInput` 增加可选 `skill_name`
- `services.py` 根据 `skill_name` 加载 SkillPack
- 默认仍然使用 `default`
- 补 API 测试覆盖默认 skill 和显式 skill

## 范围外
- 自动选择 skill
- 用户级权限
- SkillPack 启用/禁用
- UI 下拉选择

## 完成标准
- `/run` 不传 `skill_name` 时使用 `default`
- `/run` 传 `skill_name` 时使用指定 SkillPack
- 错误 skill 名称返回可理解错误

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`
