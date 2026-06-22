# Ariadne

<p align="center">
  <img src="./docs/assets/ariadne-overview.png" alt="Ariadne overview" width="100%" />
</p>

<p align="center">
  Unified AI workspace runtime for streaming chat, tool execution, approval control, trace persistence, and multi-agent workflows.
</p>

<p align="center">
  <a href="https://github.com/WanGXUUvU/ariadne">GitHub</a>
  ·
  <a href="./BUILD_PLAN.md">Build Plan</a>
  ·
  <a href="./STATUS.md">Current Status</a>
  ·
  <a href="./docs/database-schema.md">Database Schema</a>
</p>

## What Is Ariadne

Ariadne is a unified AI workspace that brings conversation workflows and developer workflows into one product surface.

Current focus:

- Agent runtime with layered execution flow
- Streaming SSE output with structured events
- Tool registry, sandbox isolation, and approval recovery
- Session, context, and trace persistence
- Skill and agent extensions
- Multi-agent dispatch and run lineage tracking

## Core Capabilities

### Agent Runtime

- Layered runtime split across `RunService`, `RunContextFactory`, `AgentRunner`, `RunLifecycle`, and `RunRecorder`
- Stable execution flow for context assembly, model/tool loop, finalization, and persistence
- Run-scoped VFS with commit / rollback semantics for coding workflows

### Tool Execution

- Unified `Tool Registry` with whitelisting, argument parsing, result normalization, and risk classification
- Built-in filesystem, search, utility, and agent bridge tools
- Approval-aware async tool execution pipeline

### State And Trace

- Session state persistence and history recovery
- Context compression and replayable run trace
- Parent / child run tracking for multi-agent workflows

### Safety And Control

- Sandbox path rewriting and workspace isolation
- Permission profiles and approval policies
- Pause / resume flow for high-risk tool calls

## Tech Stack

- Backend: Python, FastAPI, SQLAlchemy, SQLite
- Frontend: Vue 3, TypeScript, Vite
- Runtime: SSE streaming, tool middleware, session persistence, approval workflow

## Repository Layout

```text
backend/   FastAPI APIs, runtime, tools, security, memory, MCP
frontend/  Web workspace UI built with Vue 3 + Vite
docs/      Project docs, schema notes, architecture assets
specs/     Task cards and archived implementation records
```

## Quick Start

### Backend

```bash
python3 -m compileall backend/
python3 -m unittest discover -s backend/tests -p 'test_*.py' -v
cd backend && python3 -m api.app
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Development Notes

- `STATUS.md` is the current source of truth for active work.
- `BUILD_PLAN.md` tracks longer-term product direction.
- `specs/` contains task cards and completed refactor records.

## Documentation

- [Build Plan](./BUILD_PLAN.md)
- [Current Status](./STATUS.md)
- [Database Schema](./docs/database-schema.md)
- [Rename Plan](./docs/rename-plan.md)
