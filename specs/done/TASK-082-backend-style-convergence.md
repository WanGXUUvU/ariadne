# TASK-082 - 后端核心链路风格收敛（统一模块注释、docstring 与局部表达）

## 1. 目标

在不改变业务语义、不扩展产品能力的前提下，收敛后端核心链路的工程写法，让同类文件看起来像同一套系统。

本卡只处理三类问题：
- 模块头注释风格不统一，有的偏工程摘要，有的偏历史九层说明。
- 类 / 方法 docstring 长短和写法差异过大，部分仍保留原型期“教学 prose”。
- 个别主链路文件存在可顺手收紧的局部结构问题，例如重复文件读取逻辑、命名表达不一致。

## 2. 新任务拆解模板

```text
用户动作：
1. 继续维护 run / compact / trace / session 等后端主链路代码。

用户会看到：
1. 对外接口、SSE 语义、数据库行为不变。
2. 核心后端文件的注释、命名、结构更统一，后续 review 成本更低。

新数据从哪里产生：
无新业务数据。

新数据要存在哪里：
无新增持久化结构。

前端调哪个接口：
无新增接口；继续使用现有 API。

need改的层：
1. execution/
2. context/
3. memory/
```

## 3. 范围

### 本卡负责
- 统一核心后端文件的模块头注释格式。
- 将类 / 方法 docstring 收敛为职责、输入、输出、副作用导向。
- 对局部重复逻辑做无语义变化的整理。

### 本卡不负责
- 不新增业务功能。
- 不修改 API 契约。
- 不做全仓风格大扫除。
- 不引入新的领域拆分任务。

## 4. 目标文件

- `backend/execution/service.py`
- `backend/execution/runtime_context_factory.py`
- `backend/execution/child_agent_dispatcher.py`
- `backend/execution/trace_query_service.py`
- `backend/context/assembler.py`
- `backend/context/skill_context.py`
- `backend/memory/session/store.py`
- `backend/memory/summary/service.py`

## 5. Checklist

- [x] 模块头注释统一为：职责 / 上游 / 下游 / 不负责。
- [x] 类 docstring 收敛为一句职责描述。
- [x] 方法 docstring 去掉教学化长段落，保留职责和关键副作用。
- [x] `ContextAssembler` 抽出重复的工作区文件读取逻辑。
- [x] 风格调整后通过 `black`、`ruff`、unit tests、integration tests。

## 6. 验收标准

- [x] 目标文件不再混用“九层说明体”和“教学散文体”。
- [x] 核心后端文件的注释结构可预测、可复用。
- [x] 无行为回归，自动化验证通过。
