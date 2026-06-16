# TASK-007 - Agent 定义读取器

## 目标
实现从持久化层读取 Agent 定义的读取器，让代码可以把定义转成内部对象。

## 产品层
Agent Core

## 范围内
- 新增 `AgentDefinition` 数据结构
- 读取默认 agent 定义
- 解析核心字段
- 处理定义不存在、字段缺失、格式错误
- 提供 `load_agent_definition(agent_name)` 函数

## 范围外
- 自动发现所有 agent
- 数据库存储
- UI
- 自动选择 agent

## 实现步骤
1. 新建 `backend/agent_loader.py` 或同等模块。
2. 定义 `AgentDefinition` Pydantic/dataclass 对象。
3. 实现读取默认 agent 定义的函数。
4. 第一版优先用简单、稳定的结构，不引入复杂依赖。
5. 对缺失字段返回清晰异常。
6. 为默认 agent 写单元测试。

## 完成标准
- `load_agent_definition("default")` 能返回结构化对象。
- 读取失败时错误明确。
- 不影响现有 agent 行为。

## 验证
- `python3 -m unittest backend.tests.test_agent -v`

## Review 检查点
- 读取器是否只负责读取和解析，不负责运行。
- 错误类型是否方便 API 层处理。
- 是否避免把定义格式设计得过度复杂。
