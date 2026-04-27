# TASK-046 - Skill / Plugin / Agent 管理界面

## 目标
在 UI 中展示已发现的 skill、插件和 agent 信息，支持启用、禁用和查看 `SKILL.md` 摘要。

## 产品层
Frontend / Extension Management

## 范围内
- Skill 列表页
- Agent 列表页
- 展示 name、description、enabled
- 查看 Skill 详情
- 查看 Agent 详情
- 启用/禁用 Skill
- 启用/禁用 Agent
- 预留 Plugin 列表区域

## 范围外
- 在线安装插件
- 编辑完整 `SKILL.md`
- marketplace

## 实现步骤
1. 后端确认已有 skill index、agent index 和 plugin index API。
2. 前端实现 ExtensionManager 页面。
3. 增加 enable/disable 调用。
4. 详情页展示 instructions 的安全摘要。
5. 空状态提示如何添加本地 skill 或 agent。

## 完成标准
- 用户能知道当前有哪些 skill、agent 和 plugin。
- 用户能控制 skill 和 agent 是否启用。
- UI 和配置文件状态一致。

## 验证
- 手动启用/禁用一个 skill。
- 手动启用/禁用一个 agent。
- 刷新页面后状态仍正确。

## Review 检查点
- 是否避免一次性展示超长 instructions。
- enabled 状态是否来自后端。
- 是否为插件预留但不提前实现 marketplace。
