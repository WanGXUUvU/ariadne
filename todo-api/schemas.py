from pydantic import BaseModel,Field
from typing import Optional

class TodoCreate(BaseModel):
    title: str=Field(min_length=1,max_length=100)


class TodoResponse(BaseModel):
    id: int=Field(...)
    title: str


class TodoUpdate(BaseModel):
    title: Optional[str]=None
