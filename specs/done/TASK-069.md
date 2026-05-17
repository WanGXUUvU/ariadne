# TASK-069 - 测试按模块拆分

## 目标
把当前单个大测试文件拆成按模块划分的多个测试文件，只做测试代码搬迁和 import 修复，不改业务实现和产品行为。

## 产品层
Tests

## 我对当前项目的理解
项目主体已经完成分层重构，但测试仍然集中在 `agent_prototype/tests/test_agent.py` 里。
这个文件同时覆盖：
- Agent runtime
- LLM adapter
- Session store
- Skill loader
- API 路由
- Tool registry
- Agent definition service

测试本身已经开始像“测试总入口”，不再适合继续堆在一个文件里。

## 现状问题
- 单个测试文件过大，阅读成本高。
- 一个文件覆盖多个模块，定位失败原因时需要翻很长。
- 模块命名已经分层，但测试还没有同步分层。

## 本次拆分原则
- 按被测模块拆文件，不按断言类型拆文件。
- 只搬测试，不改生产代码。
- 不改测试语义，不新增测试场景。
- 不引入新的测试框架。

## 建议拆分
| 当前文件 | 建议拆分后文件 |
|---|---|
| `agent_prototype/tests/test_agent.py` | `test_agent_runtime.py` |
| `agent_prototype/tests/test_agent.py` | `test_model_adapter.py` |
| `agent_prototype/tests/test_agent.py` | `test_session_store.py` |
| `agent_prototype/tests/test_agent.py` | `test_skill_loader.py` |
| `agent_prototype/tests/test_agent.py` | `test_agent_api.py` |
| `agent_prototype/tests/test_agent.py` | `test_tool_registry.py` |
| `agent_prototype/tests/test_agent.py` | `test_agent_definition_service.py` |

## 范围内
- 新建测试文件
- 按模块移动测试类
- 修复测试 import 路径
- 删除原始大测试文件或保留最小兼容入口

## 范围外
- 不改生产代码
- 不改 API 行为
- 不改数据库结构
- 不新增测试场景
- 不新增测试框架

## 完成标准
- 测试文件按模块拆开
- 现有测试语义保持不变
- `python3 -m unittest agent_prototype.tests.test_agent -v` 或等价测试命令通过

## 验证
- `python3 -m unittest discover -s agent_prototype/tests -p \"test_*.py\" -v`

