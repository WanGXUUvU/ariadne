# TASK-024 - 现有后端能力前端整合

## 目标
基于当前已经存在的后端 API，做一个单页工作台，把聊天、session、trace、skills、manual compact、reset 等现有能力集中到一个前端任务里完成。

## 产品层
Frontend

## 范围内
- 三栏工作台布局
- session 列表、创建、读取
- 聊天主链路：`POST /run`
- 右侧 trace 时间线：读取 `/run` 返回的 events，并可读取 `/sessions/{session_id}/trace`
- skill 列表读取：`GET /skills`
- skill 启用/禁用开关：`POST /skills/{skill_name}/enable`、`POST /skills/{skill_name}/disable`
- 手动 compact：`POST /compact`
- session reset：`POST /reset`
- 显式 agent / skill 选择 UI，占用现有 `/run` 参数
- 统一错误提示和空状态

## 范围外
- 完整设计系统
- streaming
- markdown 渲染增强
- session 重命名/删除
- plugin / agent 管理后台
- 权限审批弹窗

## 实现步骤
1. 建立并稳定 `frontend/` 项目基础壳。
2. 封装现有后端 API client。
3. 接通 session 列表、创建、读取。
4. 接通聊天主链路与错误展示。
5. 接通右侧 trace 时间线。
6. 接通 skill 列表与 enable/disable。
7. 接通 manual compact 和 reset。
8. 收口成一个“覆盖现有后端能力”的工作台。

## 完成标准
- 用户不用 curl 也能访问当前所有主要后端能力。
- session、chat、trace、skills、compact、reset 都有可见入口。
- session 切换不混乱。
- skill 状态变化能反映到 UI。
- 移动端至少不崩。

## 验证
- 前端构建命令通过。
- 手动验证：创建 session、发送消息、查看 trace、查看 skills、切换 enable/disable、触发 compact、触发 reset。

## Review 检查点
- 是否真的覆盖了“当前已有后端能力”，而不是只做聊天壳。
- trace、skills、compact、reset 是否都能被找到。
- API 错误是否可见。
- 是否没有把业务逻辑都写进组件。
