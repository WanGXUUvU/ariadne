from pydantic import BaseModel,Field
from typing import Optional

class TodoCreate(BaseModel):
    title: str=Field(min_length=1,max_length=100)
    done:bool
    priority:int

class TodoResponse(BaseModel):
    id: int
    title: str
    done: bool
    priority: int


class TodoUpdate(BaseModel):
    title: Optional[str]=None
    done:Optional[bool]=None
    priority:Optional[int]=None
