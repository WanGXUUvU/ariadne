import json
from typing import Optional
from sqlalchemy.orm import Session
from .models import SessionRecord
from .schemas import AgentState

class SqliteSessionStore:
    def __init__(self,db:Session):
        self.db=db

    def get(self,session_id:str)->Optional[AgentState]:
        #去数据库查SessionRecord这张表，ORM并不是真的在python里面先查询在比较，而是先把代码翻译成sql
        #first()才是执行前面构造好的查询
        record=self.db.query(SessionRecord).filter(SessionRecord.session_id==session_id).first()

        if not record:
            return None
        #record.state_json {"messages":[{"role":"user","content":"你好","tool_calls":null,"tool_call_id":null}],"step":1}
        #它在数据库里是一个字符串，不是 Python 对象
        #json.load() 把json字符串变成python字典、列表等
        #AgentState.model_validate(...） 把普通字典，验证并转换成 AgentState 对象
        return AgentState.model_validate(json.loads(record.state_json))
    #把一个AgentState保存到sqlite里面
    def save(self,session_id:str,state:AgentState)->None:
        #state.model_dump()把一个Pydantic对象转换为字典，因为数据库不能直接存Pydantic对象
        #json.dumps就是把字典转换为json字符串
        #ensure_ascii=False就是直接保留中文
        state_json=json.dumps(state.model_dump(),ensure_ascii=False)
        record=self.db.query(SessionRecord).filter(SessionRecord.session_id==session_id).first()
        if record:
            record.state_json=state_json
        else:
            record = SessionRecord(session_id=session_id,state_json=state_json)
            self.db.add(record)
        self.db.commit()


    def delete(self,session_id:str)->None:
        record = self.db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
        if record:
            self.db.delete(record)
            self.db.commit()