from sqlalchemy import Column,String,Text,DateTime,func
#导入ORM基类
from .db import Base

class SessionRecord(Base):#会话记录表
    __tablename__="session_records"#表名

    session_id=Column(String,primary_key=True,index=True)
    state_json=Column(Text,nullable=False)
    updated_at=Column(DateTime,server_default=func.now(),onupdate=func.now())