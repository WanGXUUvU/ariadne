from sqlalchemy import Column,String,Text,DateTime,func,Integer
#导入ORM基类
from .db import Base

class SessionRecord(Base):#会话记录表
    __tablename__="session_records"#表名

    session_id=Column(String,primary_key=True,index=True) #会话id
    session_name = Column(String, nullable=True) #会话名称
    state_json=Column(Text,nullable=False) #会话状态
    created_at = Column(DateTime,server_default=func.now(),nullable=False)#创建时间
    updated_at=Column(DateTime,server_default=func.now(),onupdate=func.now(),nullable=False)#更新时间
    last_agent_name = Column(String,nullable=True,index=True)#最近使用的agent
    last_skill_name = Column(String,nullable=True,index=True)#最近使用的skill
    message_count=Column(Integer,nullable=False,default=0,server_default="0")
    last_reply_preview = Column(String(120),nullable=True) #最近回复的摘要

class AgentDefinitionRecord(Base):
    __tablename__="agent_definitions"#表名
    agent_id=Column(String,primary_key=True,index=True)
    definition_json=Column(Text,nullable=False)
    update_at=Column(DateTime,server_default=func.now())
