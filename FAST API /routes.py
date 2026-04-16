from fastapi import APIRouter, HTTPException,Depends
from sqlalchemy.orm import Session
from db import get_db
from schemas import TodoCreate, TodoResponse, TodoUpdate
from services import get_todo_by_id, create_todo, update_todo, delete_todo, get_all_todos
router = APIRouter()


@router.get("/")
def read_root():
    return {"message": "hello world"}


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/todos", response_model=list[TodoResponse])
def get_all_todos_api(db: Session = Depends(get_db)):
    return get_all_todos(db)


@router.get("/todos/{todo_id}", response_model=TodoResponse)
def get_todo_by_id_api(todo_id: int,db: Session = Depends(get_db)):
    todo=get_todo_by_id(db,todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo


@router.post("/todos", response_model=TodoResponse, status_code=201)
def create_todos_api(request: TodoCreate,db: Session = Depends(get_db)):
    return create_todo(db,request.title,request.done,request.priority)


@router.delete("/todos/{todo_id}",response_model=TodoResponse)
def delete_todo_api(todo_id: int,db: Session = Depends(get_db)):
    todo=delete_todo(db,todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo


@router.patch("/todos/{todo_id}",response_model=TodoResponse)
def update_todo_api(todo_id: int, request: TodoUpdate,db: Session = Depends(get_db)):
    if request.title is None and request.done is None and request.priority is None:
        raise HTTPException(status_code=400,detail="No fields provided for update")
    todo=update_todo(db,todo_id,request.title,request.done,request.priority)
    if todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo
