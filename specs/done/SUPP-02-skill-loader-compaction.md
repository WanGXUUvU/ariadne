# 补充卡 02 - Skill Loader 与应用编排收缩

> 类型：补充卡（临时插入，非主线任务卡）

## 目标
把当前已经开始变厚的多职责模块继续拆薄，优先收窄 `skills/skill_loader.py`，并视需要继续压缩 `application/run_service.py` 的编排职责。

## 产品层
Backend Architecture

## 我对当前项目的理解
`TASK-071` 解决的是 runtime 过胖的问题，但代码库里不止 runtime 有臃肿迹象。

现在最明显的第二梯队问题是：
- `skills/skill_loader.py` 同时做目录扫描、frontmatter 解析、全文加载、配置读写
- `application/run_service.py` 同时做 session 读取、自动 compact、agent definition 加载、skill catalog 组装、runtime 调用、trace 落库

这两个文件都还是“能跑，但会越来越难维护”的状态。

## 目标判断
这张卡只做一个判断：
- 哪些职责已经足够独立，值得从当前文件中拆出去
- 哪些职责暂时还要留在原文件里，避免过度拆分

## 优先对象
### 第一优先：`skills/skill_loader.py`
它已经同时承担：
- skill 目录扫描
- skill frontmatter 解析
- skill 正文加载
- skill 配置读写

这说明它同时混了“发现”“解析”“读取”“配置”四类职责，适合继续拆。

### 第二优先：`application/run_service.py`
如果 `TASK-071` 完成后它仍然偏厚，再继续把其中稳定独立的部分拆出去：
- session / compact 预处理
- skill catalog 组装
- runtime 调用
- trace / snapshot 持久化

## 范围内
- 只分析和拆分现有职责，不新增功能
- 先拆 `skill_loader.py`
- 如果需要，再继续压缩 `run_service.py`
- 保持现有 API 行为不变
- 保持现有测试语义不变

## 范围外
- 不做 MCP
- 不做 streaming
- 不做新 UI
- 不改模型协议
- 不改数据库结构

## 实施步骤
1. 先把 `skills/skill_loader.py` 的职责边界画清楚。
2. 拆出最独立的 helper 或子模块。
3. 回归测试，确认技能扫描和启用/禁用行为不变。
4. 再评估 `application/run_service.py` 是否还需要继续拆。

## 完成标准
- `skills/skill_loader.py` 不再同时负责太多件事。
- 如果 `run_service.py` 仍然偏厚，已经找到下一刀从哪里下。
- 现有测试通过。
- 结构上能清楚解释每一层职责。

## 验证
- `python3 -m unittest discover -s backend/tests -p 'test_*.py' -v`

## Review 检查点
- 是否先拆最有价值的模块，而不是平均用力。
- 是否避免把 `run_service.py` 过度拆碎。
- 是否保证技能发现/读取/配置行为保持一致。

## 收口记录
- 2026-05-10：已完成 `skill_loader.py` 与 `run_service.py` 的职责收缩，补充分层 helper，并通过 `python3 -m unittest discover -s backend/tests -p 'test_*.py' -v`。
