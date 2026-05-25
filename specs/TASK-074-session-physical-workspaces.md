# TASK-074 - 本地物理工作区绑定、沙箱隔离与中间件管道全接入

## 目标
支持在新建或切换会话时，选择机器上的本地文件夹作为会话（Session）的物理工作区。同时完成中间件管道的全面接入，将审批拦截与沙箱拦截从硬编码逻辑迁移进工业级中间件架构。
1. **列表分类**：左侧会话列表按照绑定的物理工作区文件夹进行折叠、分组聚合渲染。
2. **原生文件夹选择弹窗**：在前端点击"添加本地文件夹"时，后端通过本地代理在机器上直接弹出一个**系统的原生文件夹选择对话框（MacOS Finder Dialog）**，用户选择后自动获取绝对路径并完成绑定，无需手动痛苦输入绝对路径。
3. **物理沙箱**：大模型在此会话中执行文件操作类工具时，操作边界强行限制在工作区路径下，实现彻底的物理沙箱文件隔离。
4. **中间件管道全接入**：将 TASK-073 切片 6 建立的中间件骨架真正接入工具执行流程，`ApprovalMiddleware` 接管审批逻辑，`SandboxMiddleware` 接管路径拦截，`tool_executor.py` 中的硬编码块同步清除。

## 产品层
Session Management / Workspace Sandbox / OS Native Dialog Proxy / UI Sidebar

## 背景
在大模型编码助理场景下，用户希望将不同的会话隔离在机器上的不同项目文件夹中。为了提供一流的 UX，在添加工作区时，需要直接唤起系统原生的文件夹选择器；同时在左侧侧边栏智能地以“项目文件夹”进行折叠归类展示。


## 范围内
- **数据库层**：
  - `SessionRecord` 已有 `workspace_path` / `workspace_name` 字段，`WorkspaceRecord` 表已存在，确认 Alembic 迁移已应用。
- **后端 API 与系统原生弹窗代理**：
  - `infrastructure/os_proxy/apple_script.py`：AppleScript 弹窗处理器，支持超时和取消捕获。
  - `interface/api/routes/workspace_routes.py`：`GET /workspaces`（历史库）、`POST /workspaces/select-dialog`（唤起 Finder）。
  - `SessionService.create_session` 扩展支持 `workspace_path` 绑定。
- **中间件管道全接入（TASK-073 遗留）**：
  - `ApprovalMiddleware.call()`：将 `tool_executor.py` 中的 `needs_approval` 硬编码块迁移进来，通过 `context.extra["on_approval_required"]` 拿到回调。
  - `SandboxMiddleware.call()`：从 `context.extra["workspace_path"]` 读取沙箱根路径，拦截 `../` 路径越界，无工作区时直接放行。
  - `tool_executor.py`：删除硬编码审批块，改为构建 `ToolCallContext` 并走 `MiddlewarePipeline`。
- **前端 UI**：
  - **工作区选择器**：顶部下拉显示已注册文件夹，点击"添加本地文件夹"触发 `/workspaces/select-dialog`，返回路径后绑定到新建会话。
  - **`SessionSidebar.vue`**：提取 `groupedSessions` 计算属性，按工作区分组渲染风琴折叠侧边栏，无工作区会话归入"全局"默认组。

## 范围外
- 远程 SSH 主机连接。
- Windows / Linux 原生弹窗（本阶段专精 macOS AppleScript）。

---

## 切片迭代路线（Checklist）

- [x] **切片 1：确认数据库迁移状态**
  - [x] 运行 `alembic current` 确认 `workspace_path` / `WorkspaceRecord` 迁移已落地。
  - [x] 若未落地，补写并应用 Alembic 迁移脚本。

- [ ] **切片 2：AppleScript 弹窗代理 + WorkspaceService**
  - [ ] `infrastructure/os_proxy/apple_script.py`：`open_folder_dialog() -> Optional[str]`，含超时/取消处理。
  - [ ] `application/services/workspace_service.py`：`WorkspaceService.__init__(db)`，`list_workspaces()` / `register_workspace(path)` / `select_dialog()`。
  - [ ] `interface/api/routes/workspace_routes.py`：`GET /workspaces` + `POST /workspaces/select-dialog`。
  - [ ] 注册路由进 `main.py`。

- [ ] **切片 3：SessionService 绑定工作区**
  - [ ] `SessionService.create_session(workspace_path)` 写入 `workspace_path` / `workspace_name`。
  - [ ] `GET /sessions` 响应中携带 `workspace_path` / `workspace_name` 字段。

- [ ] **切片 4：中间件管道全接入（审批 + 沙箱）**
  - [ ] `ApprovalMiddleware.call()`：填入真实审批拦截逻辑，通过 `context.extra["on_approval_required"]` 触发回调，yield 审批事件并暂停。
  - [ ] `SandboxMiddleware.call()`：从 `context.extra["workspace_path"]` 读取根路径，`Path.resolve()` 后检查越界，越界返回 `ToolResult(ok=False, ...)`。
  - [ ] `tool_executor.py`：构建 `ToolCallContext`（含 `session_id` / `run_id` / `workspace_path` / `on_approval_required`），走 `MiddlewarePipeline([SandboxMiddleware(), ApprovalMiddleware()])`，删除原有硬编码审批块。
  - [ ] 更新 `async_handle_tool_calls` 签名，新增 `session_id` / `run_id` / `workspace_path` 参数。
  - [ ] 全量单测通过（>= 83 passed）。

- [ ] **切片 5：前端工作区选择器**
  - [ ] 顶部下拉组件：调用 `GET /workspaces` 渲染历史，点击"添加本地文件夹"调用 `/workspaces/select-dialog`。
  - [ ] 新建会话时携带选中的 `workspace_path`。

- [ ] **切片 6：前端 SessionSidebar 分组折叠**
  - [ ] 提取 `groupedSessions` 计算属性：`{ workspace_name: session[] }`。
  - [ ] 风琴折叠渲染，active 会话所在分组自动展开。
  - [ ] 无工作区会话归入"全局"默认组。
  - [ ] `npm run build` 100% 通过。

---

## 完成标准
- 点击"添加本地文件夹"能唤起 macOS 原生 Finder 文件夹选择弹窗，返回路径后完成绑定。
- 左侧会话侧边栏按工作区分组折叠，active 会话所在组自动展开。
- 文件工具执行被强行限制在绑定的 `workspace_path` 下，`../` 越界调用返回错误而非执行。
- 审批拦截逻辑通过 `ApprovalMiddleware` 运行，`tool_executor` 中无硬编码审批块残留。
- 全量单测通过，前端构建通过。
