from models import Todo
from sqlalchemy.orm import Session
from typing import Optional
##获取所有todos
def get_all_todos(db:Session):

    todos=db.query(Todo).all()
    
    result=[{"id":todo.id,"title":todo.title,"done":todo.done,"priority":todo.priority}

            for todo in todos
    ]
    return result

##获取单个todo
def get_todo_by_id(db:Session,todo_id):

    todo=db.query(Todo).filter(Todo.id==todo_id).first()
    if todo is None:
        return None
    result={"id":todo.id,"title":todo.title,"done":todo.done,"priority":todo.priority}


    return result

##新增一个todo
def create_todo(db:Session,title: str,done:bool,priority:int):

    todo = Todo(title=title,done=done,priority=priority)
    try:
        db.add(todo)
        db.commit()
        db.refresh(todo)

        result={"id":todo.id,"title":todo.title,"done":todo.done,"priority":todo.priority}


        return result
    except  Exception:
        db.rollback()
        raise

#删除todo
def delete_todo(db:Session,todo_id:int):
    todo=db.query(Todo).filter(Todo.id==todo_id).first()

    if todo is None:
        return None
    result={"id":todo.id,"title":todo.title,"done":todo.done,"priority":todo.priority}

    try:
        db.delete(todo)
        db.commit()
        
        return result
    except Exception:
        db.rollback()
        raise

#更新todo
def update_todo(db:Session,todo_id:int,title=None,done=None,priority=None):

    todo=db.query(Todo).filter(Todo.id==todo_id).first()
    if todo is None:
        return None
    try:
        if title is not None:
            todo.title=title
        if done is not None:
            todo.done= done
        if priority is not None:
            todo.priority=priority

        db.commit()
        
        db.refresh(todo)
        result={"id":todo.id,"title":todo.title,"done":todo.done,"priority":todo.priority}

        return result
    except Exception:
        db.rollback()
        raise