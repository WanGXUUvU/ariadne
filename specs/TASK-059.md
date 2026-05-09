# TASK-059 - Hooks 生命周期配置与执行

## 目标
支持 Codex 风格的 lifecycle hooks，让系统能在关键事件前后执行受控脚本或处理逻辑。

## 产品层
Hooks / Runtime

## 依赖
- `TASK-033` 配置层与项目信任
- `TASK-057` Plugin 包结构对齐

## 范围内
- 支持读取 `hooks/hooks.json`
- 支持项目配置中的 inline hooks
- 定义最小 hook event：`SessionStart`、`UserPromptSubmit`、`PreToolUse`、`PostToolUse`、`Stop`
- 先支持 command hook handler
- 记录 hook 执行结果和失败信息

## 范围外
- prompt hook / agent hook 的完整执行
- 复杂条件表达式
- 企业级 managed hooks

## 实现步骤
1. 定义 hook schema 和 event 枚举。
2. 读取插件 hooks 和项目 inline hooks。
3. 在 session / tool runtime 的关键节点触发 hooks。
4. 把 hook 执行结果写入 trace 或 debug 日志。
5. 写测试覆盖缺文件、坏 schema、hook 执行失败和跳过逻辑。

## 完成标准
- hooks 可以被发现、加载和触发。
- hook 失败不会把主流程静默吞掉。
- 插件 hooks 和项目 hooks 的来源边界清楚。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- event 选择是否最小且够用。
- 是否先只支持 command hooks。
- hook 执行是否有可观察性。
