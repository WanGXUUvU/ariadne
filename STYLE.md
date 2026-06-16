# STYLE

## 目标
- 让同类代码看起来像同一套系统，而不是不同阶段的临时产物。
- 让 review 关注结构和逻辑，不浪费在低价值格式问题上。

## 边界规则
- 每个模块头注释只写职责、上游、下游、是否有副作用。
- service 只接收真实依赖；不要为“以后可能用到”预留构造参数。
- route 层只做 HTTP 适配，不直接操作 store。
- execution 层不返回 HTTP DTO。
- 业务模块禁止新增包根导出、`__getattr__` 懒加载门面、`re-export` 兼容桥。

## 导入规则
- 默认使用显式模块导入，不从包根导入业务对象。
- 不新增 `from x import *`。
- 不新增仅用于兼容旧路径的桥接文件。

## 测试规则
- 重复的测试数据库初始化、假对象构造、TestClient 覆盖逻辑放进 `backend/tests/helpers/`。
- patch 优先打稳定边界，不 patch 临时私有实现。
- 新测试优先复用 helper，不重复抄初始化样板。

## Python 工具
- 格式化：`./.venv/bin/black backend`
- 检查：`./.venv/bin/ruff check backend`
- 自动修复 import 和基础问题：`./.venv/bin/ruff check --fix backend`

说明：
- `black` 负责统一格式。
- `ruff` 当前先作为“全仓可执行的正确性基线”，重点拦截明显错误和高价值坏味道。
- import 排序和更细的风格收敛，按触达文件逐步推进，避免一次性制造大规模无意义 churn。

## 提交前最小检查
- `./.venv/bin/black --check backend`
- `./.venv/bin/ruff check backend`
- `python3 -m unittest discover -s backend/tests/unit -p 'test_*.py'`
