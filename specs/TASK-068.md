# TASK-068 - 模块命名统一

## 目标
把当前后端里最泛的模块名收紧成更能表达职责的名字，只做机械性重命名和 import 修复，不改业务逻辑。

## 产品层
Backend Naming Convention

## 我对当前项目的理解
现在 `agent_prototype/` 的职责分层已经基本清楚了，但有几类文件名还过于泛：
- `model/types.py`
- `skills/loader.py`
- `tools/registry.py`

这些名字本身不出错，但放进现在这个项目里，语义已经不够直观。  
后续维护时，看到文件名就应该能大致知道它属于哪一层、具体干什么。

## 现状问题
- `types.py` 太泛，容易和别的层的类型文件混淆。
- `loader.py` 太泛，放在 `skills/` 里也不够直观。
- `registry.py` 太泛，放在 `tools/` 里也不够明确。
- 当前结构已经按层划分，但模块命名还没有完全统一。

## 统一原则
- `model/` 里的文件名应明确带出模型职责。
- `skills/` 里的文件名应明确带出 skill 职责。
- `tools/` 里的文件名应明确带出 tool 职责。
- 只改文件名和 import 路径，不动实现逻辑。

## 本次建议改名
| 当前文件 | 建议文件 |
|---|---|
| `agent_prototype/model/types.py` | `agent_prototype/model/model_types.py` |
| `agent_prototype/skills/loader.py` | `agent_prototype/skills/skill_loader.py` |
| `agent_prototype/tools/registry.py` | `agent_prototype/tools/tool_registry.py` |

## 范围内
- 机械性重命名文件
- 修复内部 import
- 必要时补充兼容 shim
- 调整测试中的 import 路径

## 范围外
- 不改业务逻辑
- 不改 API 行为
- 不改数据库结构
- 不新增功能
- 不新增抽象层

## 完成标准
- 新名字能比旧名字更直接表达职责
- 现有测试通过
- 旧路径如果保留，只能是短期兼容 shim

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

