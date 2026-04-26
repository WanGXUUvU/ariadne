# TASK-019 - Skill 启用和禁用配置

## 目标
支持启用和禁用 SkillPack，让产品能管理可用能力集合。

## 产品层
产品表面层 + SkillPack（Product Surface + SkillPack）

## 范围内
- 新增本地 skill 配置文件
- 支持 skill enabled/disabled
- `GET /skills` 展示启用状态
- `/run` 禁止使用 disabled skill

## 范围外
- 用户级配置
- 远程同步
- 权限审批
- 插件安装

## 完成标准
- disabled skill 不会被使用
- 默认 skill 始终可用
- 测试覆盖禁用场景

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`
