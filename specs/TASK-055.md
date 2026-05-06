# TASK-055 - Session 重命名与删除

## 目标
让用户可以给会话起名字，以及删除不需要的会话，让 Sessions 侧边栏真正可用。

## 产品线
聊天助理

## 范围内
- 后端新增 `PATCH /sessions/{session_id}` 支持更新 session_name
- 后端新增 `DELETE /sessions/{session_id}` 软删除或硬删除（先做硬删除）
- 前端侧边栏支持双击重命名
- 前端支持删除会话并从列表移除
- 删除当前激活 session 时自动切换到最新 session

## 范围外
- 批量删除
- 回收站
- 会话归档

## 实现步骤
1. 后端 PATCH 接口更新 session_name 字段。
2. 后端 DELETE 接口删除 session 和关联 trace（级联删除）。
3. 写后端测试覆盖重命名、删除、删除不存在的 session。
4. 前端侧边栏增加双击重命名交互。
5. 前端增加删除按钮（带确认提示，防误操作）。
6. 处理删除当前 session 后的路由跳转。

## 完成标准
- session 名称可以被修改并持久化。
- 删除后 session 不再出现在列表中。
- 删除当前 session 后不出现空白或崩溃。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`
- 手动在 UI 中重命名和删除会话。

## Review 检查点
- DELETE 是否做了级联清理 trace 数据。
- 重命名是否限制了名称长度。
- 前端删除是否有二次确认，避免误操作。
