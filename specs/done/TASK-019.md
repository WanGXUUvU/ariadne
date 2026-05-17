# TASK-019 - Skill 启用和禁用配置

## 目标
让用户可以控制哪些 skill 可用，为产品设置页和插件管理做准备。

## 产品层
Skill Management / Config

## 范围内
- 新增 skill enabled 配置
- list skills 时体现 enabled
- 禁用 skill 不能被选择
- default skill 受保护或有明确 fallback

## 范围外
- UI
- 多用户配置
- 插件安装

## 实现步骤
1. 选择配置存储位置，优先简单 JSON 或项目配置。
2. 实现读取 enabled/disabled 列表。
3. 在 `load_skill` 前检查是否启用。
4. 新增 enable/disable service 函数。
5. 测试禁用 skill 后无法使用。

## 完成标准
- skill 可以被禁用。
- 禁用 skill 不出现在可选列表或标记为 disabled。
- 错误信息清楚。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 默认 skill 被禁用时如何处理。
- 配置文件是否适合提交到 repo。
- 是否为插件配置留空间。
