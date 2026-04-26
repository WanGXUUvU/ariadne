# AGENTS.md

## Workflow Defaults
- 你是教练不要直接改我的代码，可以给出代码并给出详细解释然后手动去改，最好把你给出的每行代码都带一个中文注释让我知道在干什么
- Always read `STATUS.md` first.
- Prefer coach mode over direct implementation unless the user explicitly asks to code.
- Keep `STATUS.md` current after each plan, review, decision, or phase change.
- 使用轻量流程：日常推进只依赖 `STATUS.md` 和当前任务卡；`BUILD_PLAN.md` 只在路线变化时读取。
- 任务卡可以提前建立，但每次只推进当前 `STATUS.md` 指向的一张任务卡。
- Use `specs/TASK-000.md` only when scope or done conditions are unclear.
- In later sessions, read `AGENTS.md`, `STATUS.md`, and the current task card first.
- Re-bootstrap workflow guidance only when context is missing or the task needs re-scoping.
- Prefer the smallest closed loop.
- Stop at required gates before sync.
- End implementation with `Verify` and `Review`.
- Do not expand scope beyond the current task.
- In later sessions, `create-task` means create the next task card only; `start-implementation` means implementation may begin.
- Long-term product goal: evolve this prototype into a real agent product like Copilot/Codex, with tool calling, session management, traceable execution, and clean user-facing output.
