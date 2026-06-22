# Ariadne

<p align="center">
  <img src="./docs/assets/ariadne-overview.png" alt="Ariadne overview" width="100%" />
</p>

<p align="center">
  统一 AI 工作台后端，支持流式对话、工具调用、权限审批、运行追踪与多 Agent 协作。
</p>

<p align="center">
  <a href="https://github.com/WanGXUUvU/ariadne">GitHub</a>
</p>

## 项目简介

Ariadne 是一个统一 AI 工作台，目标是在同一产品内承载对话式工作流与开发者工作流，并提供稳定的运行时、工具调用和状态管理能力。

## 核心特性

- 流式对话与结构化事件输出
- 工具注册、白名单控制与权限审批
- 会话状态、上下文与运行轨迹持久化
- 技能扩展与多 Agent 协作
- 面向工作区场景的沙箱隔离能力

## 技术栈

- 后端：Python、FastAPI、SQLAlchemy、SQLite
- 前端：Vue 3、TypeScript、Vite
- 运行时：SSE Streaming、工具中间件、会话持久化、审批流程

## 仓库结构

```text
backend/   FastAPI API、Runtime、Tools、Security、Memory、MCP
frontend/  基于 Vue 3 + Vite 的 Web Workspace
docs/      项目文档与架构资源
specs/     历史任务记录
```

## 快速开始

### 后端

```bash
python3 -m compileall backend/
python3 -m unittest discover -s backend/tests -p 'test_*.py' -v
cd backend && python3 -m api.app
```

### 前端

```bash
cd frontend
npm install
npm run dev
```
