from sqlalchemy import Column,Integer,String,Boolean

from db import Base

class Todo(Base):
    __tablename__="todos"

    id=Column(Integer,primary_key=True,index=True)
    title=Column(String,nullable=False)
    done=Column(Boolean,nullable=False)
    priority=Column(Integer,nullable=False)
