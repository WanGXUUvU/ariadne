from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session 

from .schemas import AgentInput, AgentOutput, ResetInput
from .db import get_db
from .services import run_agent_service,reset_session_service

router = APIRouter()

#Session 是类型，表示这是一个 SQLAlchemy 数据库会话对象
@router.post("/run", response_model=AgentOutput)
# 这个参数叫 db
# 类型是 Session
# 值由 get_db() 提供
def run_agent_api(agent_input: AgentInput,db:Session=Depends(get_db)):#这个函数需要一个数据库会话，但不用我自己传，FastAPI 你帮我调用 get_db() 准备好
    return run_agent_service(agent_input,db)


@router.post("/reset")  # 定义 /reset 接口
def reset_session(payload: ResetInput, db: Session = Depends(get_db)):  # 注入数据库会话
    return reset_session_service(payload, db)  # 调用业务层