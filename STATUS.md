# STATUS

## Current Snapshot
- Phase: 第 1 阶段
- Task: 打牢 Python 后端基础，为后续 Agent 系统搭建做准备；当前聚焦接口分层与 `PATCH` 场景测试
- Gate: 轻量记录
- Lane: Fast
- Blocking: None
- Next: 先完成 `todo-api` 的分层和测试收口，再进入第 2 阶段的 Agent 基础组件学习与最小原型搭建

## This Week
- 目标：把 `todo-api` 从“能跑”整理到“语义明确”，作为 Agent 工程底座训练
- 重点：`routes.py` / `services.py` / `schemas.py`
- 暂不扩展：Agent 编排、工具系统、部署、微服务

## Done
- SQLite 版 CRUD 已收口
- SQLAlchemy ORM 基础设施已接上
- `Todo` 模型已定义
- 已理解 `Todo` 类、ORM 对象和数据表映射关系
- ORM 版 CRUD 已实现
- `routes.py` 与 `services.py` 已完成参数对齐
- `TodoCreate` 字段约束已开始引入
- `TodoUpdate` 已切到部分更新思路
- `Todo` 模型字段类型已修正为 SQLAlchemy 类型
- `TodoCreate` / `TodoResponse` / `TodoUpdate` 语义已对齐
- `done` / `priority` 的创建、返回、数据库非空约束已统一
- 已明确需要一个“状态驱动的后端 / RAG 教练 skill”来承接后续规划
- 已创建 `status-driven-backend-coach` skill 并通过校验
- 已定位并解决旧 `todo.db` 与 ORM 模型不一致导致的 `POST /todos` 500
- 已验证 `GET / POST / PATCH / DELETE` 全部通过
- 已完成一次失败路径实战，知道异常会中断请求并触发回滚思维
- `delete_todo()` 已和 `create_todo()` / `update_todo()` 使用同类事务处理
- 已验证 `DELETE /todos/1` 后再次 `GET /todos/1` 返回 `404`
- 已添加并通过一个最小接口测试，验证删除后再次查询返回 `404`
- 下一步重点是把“接口层负责什么、服务层负责什么”讲清楚
- 已确认项目主方向从“RAG 学习”调整为“Agent 系统搭建学习”

## Risks
- 容易因为目标改成 Agent，就跳过后端基础直接做编排层
- ORM 里手动开关 session 还不够规范
- 容易把分支状态和代码状态混淆
- `todo.db` 可能保留旧表结构，导致插入新字段时报错
- 需要避免下一步立刻跳到更大功能，先把这轮收口
- 容易把“会做 CRUD”误认为“后端基础已经完全学完”
- 容易直接跳到多 Agent，而忽略 Agent 应用最关键的工程底座
- 还缺一层“如何验证代码正确”的测试思维
- 事务边界如果不清楚，测试也很难稳定设计
- 容易只会写成功路径，不会处理失败路径
- 需要把事务处理从 `create_todo()` 迁移到其他写操作
- 写操作风格最好继续统一，避免后续维护时出现分叉
- 需要继续补 `PATCH` 场景测试，确认部分更新语义
