# TASK-091: 多会话并行流式执行与状态隔离 (Multi-Session Concurrent Streaming & State Isolation)

## 1. 核心任务定义 (Goal)
**目标**：彻底消除多会话之间的流式输出污染和强制中断限制，使用户可以同时启动多个不同的会话进行流式生成（例如在主会话中提问，同时在分支/Fork会话中提问），并支持随时在它们之间自由切换，每个会话均能独立、完整且无感地完成后台流式生成与渲染。

---

## 2. 详细设计与范围 (Scope & Design)

### 范围内：
1. **工作区状态重构为会话级映射**：
   * 将 `useWorkspace.ts` 中目前属于单例的会话运行相关状态，合并并重构为以 `sessionId` 为键的键值对容器 `sessionStates`（例如 `Record<string, SessionSpecificState>`）。
   * 包含的会话级状态：`historyMessages`, `currentMessages`, `traceRuns`, `isChatLoading`, `isTraceLoading`, `isStreaming`, `streamingTimeline`, `streamingPrefixTimeline`, `lastCompletedRun`, `errorMsg`, `isAwaitingApproval`, `pendingApprovalInfo`, `pendingApprovalInfos`, `permissionProfile`, `streamAbortController`, `pendingRunId`, `pendingUserInput`, `pendingAgentName`, `pendingSkillName`。
2. **动态代理 Ref (Computed Ref)**：
   * 在 `useWorkspace.ts` 中，使用 Vue 3 的**可写计算属性 (Writable Computed)** 将所有原本的共享 Ref 代理到当前 `activeSessionId` 所对应的 `sessionStates`。
   * 此设计能够保证外部所有 Vue 组件（如 `ChatPanel.vue`, `CodingView.vue` 等）及关联 composables（如 `useApprovalFlow.ts`）**完全不需要做任何代码修改**即可直接适配并行状态。
3. **移除切换会话时的自动终止机制**：
   * 在 `useWorkspace.ts` 的 `activeSessionId` 监听器中，移除 `runStreaming.stopStreaming()` 的调用。切换会话时，后台任务将静默运行。
4. **流式服务改写 (useRunStreaming.ts)**：
   * 移除 `useRunStreaming` 中对 activeSessionId 计算属性的强依赖，转为面向目标 `targetSessionId`（即发起流式时的会话 ID）更新对应的 `sessionStates[targetSessionId]`，实现后台流式更新与前台切换解耦。

### 范围外：
1. 左侧会话侧边栏上的流式小圆点/进度动画（保留原有聊天页内的流式展示即可，未来可做视觉增强）。

---

## 3. 实现指南 (Implementation Guide)

### 用户动作：
1. 用户在会话 A 中发送一个耗时问题。
2. 在流式响应过程中，用户直接点击左侧侧边栏切换到会话 B。
3. 用户在会话 B 中再次发送一个问题。
4. 用户在两个会话之间反复切换。

### 用户会看到：
1. 切换到会话 B 时，会话 A 的后台流式执行不会中断，会话 B 可以正常开启新的流式。
2. 切回会话 A 时，会话 A 能够完美展示当前的流式进度（如果已完成则展示完整回答；如果仍在流式中则展示打字机动画）。
3. 两个会话的历史消息、执行轨迹（Trace）和审批状态均保持物理独立隔离，无交叉污染。

### 需要改的层：
*   **前端逻辑层**：
    *   [useWorkspace.ts](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/composables/useWorkspace.ts)：实现 `sessionStates` 映射与代理计算属性，移除 active 切换时的 `stopStreaming`。
    *   [useRunStreaming.ts](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/composables/workspace/useRunStreaming.ts)：将接口入参重构为传递 `getSessionState`，确保流式写入锁定的目标会话状态中。

---

## 4. 验证方法 (Verification)
*   **生产构建编译**：运行 `npm run build`，确保 Vue 3 和 TypeScript 100% 编译成功无警告。
*   **手动功能验证**：
    *   并发提问：在 Session A 并发提问，切换至 Session B 并发提问，验证两边是否同时正常接收流。
    *   切换回填：验证从 Session B 切换回 Session A 后，Session A 的最新生成内容 and 状态正常展现。
