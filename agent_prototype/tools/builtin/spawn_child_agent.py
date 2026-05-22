import uuid
import os
from concurrent.futures import ThreadPoolExecutor
from ...core.tool_types import ToolDefinition,RiskLevel
from ...core.schemas import AgentInput,AgentState,ToolResult
from ...core.agent_definition import AgentDefinition
from ...model.openai_adapter import ChatCompletionsAdapter

def build_spawn_child_agent_tool(parent_run_id:str, session_id:str, executor:ThreadPoolExecutor, futures:dict)->ToolDefinition:
    """工厂函数：把db注入闭包，返回可注册的Tool Definition"""

    def spawn_child_agent(task: str, agent_name: str = "子Agent") -> ToolResult:

        child_run_id=uuid.uuid4().hex

        future=executor.submit(_run_child, task, child_run_id, parent_run_id, session_id, agent_name)
        futures[child_run_id]=future
        return ToolResult(
            ok=True,
            content=child_run_id,
            metadata={"tool_name":"spawn_child_agent","child_run_id":child_run_id,"agent_name":agent_name},
        )
    
    SCHEMA = {
    "type": "function",
    "function": {
        "name": "spawn_child_agent",
        "description": (
            "把一个独立子任务委派给子 Agent 异步执行。"
            "立即返回 child_run_id 字符串，不等待任务完成。"
            "【单任务模式】派出后立即调用 wait_child_agent(child_run_id) 阻塞等待结果，再回复用户。不要先对用户说'正在等待'就停下。"
            "【并行模式】需要同时派发多个子任务时，先连续调用多次 spawn_child_agent，"
            "然后用 check_child_status 逐一查询各子任务状态：若已 done 则直接从 reply 字段取值；"
            "若仍 running 则对该 child_run_id 单独调用 wait_child_agent 阻塞等待其完成再取结果。"
            "全部子任务结果收齐后，汇总回复用户。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "子 Agent 需要完成的具体任务描述",
                },
                "agent_name": {
                    "type": "string",
                    "description": "子 Agent 的角色名称，用于前端展示，如'数据分析师'、'代码审查员'。不填默认为'子Agent'。",
                },
            },
            "required": ["task"],
            "additionalProperties": False,
        },
    },
}

    return ToolDefinition(
        name="spawn_child_agent",
        schema=SCHEMA,
        handler=spawn_child_agent,
        risk_level=RiskLevel.SAFE,
    )
    
def _run_child(task: str, child_run_id: str, parent_run_id: str, session_id: str, agent_name: str = "子Agent"):
    from ...runtime.agent_runtime import Agent  # 懒加载，避免循环导入
    from ...storage.db import SessionLocal  # 获取数据库会话
    from ...storage.stores.session_store import SqliteSessionStore  # 导入 store
    RUN_MODEL = os.getenv("RUN_MODEL", "deepseek-v4-flash")
    child_state=AgentState()
    definition = AgentDefinition(id=child_run_id, name=agent_name)
    agent=Agent(
        state=child_state,
        definition=definition,
        model_adapter=ChatCompletionsAdapter(model=RUN_MODEL),
    )
    output=agent.run(AgentInput(
        session_id=session_id,  # 复用父 session_id，满足外键约束
        user_input=task,
    ))
    
    # 📍 落库：子 Agent 的 run 记录 + 事件列表，挂在同一个 session 下
    try:
        db = SessionLocal()
        store = SqliteSessionStore(db)
        store.create_child_run(
            parent_run_id=parent_run_id,
            session_id=session_id,
            run_id=child_run_id,
            agent_name=agent_name,
            user_input=task,
            reply=output.reply,
            events=output.events,
        )
        db.commit()
        db.close()
    except Exception as e:
        print(f"Failed to persist child run {child_run_id}: {e}")
    
    return output   # ← f.result() 拿到 AgentOutput