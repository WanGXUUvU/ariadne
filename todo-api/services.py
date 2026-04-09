from models import Todo
from db import SessionLocal

# def get_all_todos():
#     conn=get_connection()
#     cursor=conn.cursor()

#     cursor.execute("SELECT id,title FROM todos")
#     rows=cursor.fetchall()
    
#     conn.close()

#     return [
#         {"id":row["id"],"title":row["title"]}
#         for row in rows
#     ]
def get_all_todos():
    db=SessionLocal()

    todos=db.query(Todo).all()

    result=[{"id":todo.id,"title":todo.title}
            for todo in todos
    
    ]

    db.close()

    return result
def get_todo_by_id(todo_id):
    db=SessionLocal()

    todo=db.query(Todo).filter(Todo.id==todo_id).first()

    if todo is None:
        db.close()
        return None
    result={"id":todo.id,"title":todo.title}
    db.close()

    return result

##新增一个todo
def create_todo(title: str):
    db = SessionLocal()

    todo = Todo(title=title)
    db.add(todo)
    db.commit()
    db.refresh(todo)

    result = {
        "id": todo.id,
        "title": todo.title
    }

    db.close()
    return result
    
    
##删除一个todo
#def delete_todo(todo_id:int):
    # todo=get_todo_by_id(todo_id)
    # if todo is None:return None
    # conn=get_connection()
    # cursor=conn.cursor()

    # cursor.execute("DELETE  from todos where id=?",(todo_id,))

    # conn.commit()
    
    # conn.close()
    # return 
def delete_todo(todo_id:int):
    db=SessionLocal()

    todo=db.query(Todo).filter(Todo.id==todo_id).first()
    if todo is None:
        db.close()
        return None
    
    result={"id":todo.id,"title":todo.title}
    db.delete(todo)

    db.commit()

    db.close()

    return result


# def update_todo(todo_id:int,title:str):
#     conn=get_connection()
#     cursor=conn.cursor()

#     cursor.execute("UPDATE todos set title = ? where id=?",(title,todo_id,))

#     conn.commit()
    
#     if cursor.rowcount==0:
#         conn.close()
#         return None

#     conn.close()

#     return {"id":todo_id,"title":title}

def update_todo(todo_id:int,title:str):
    db=SessionLocal()

    todo=db.query(Todo).filter(Todo.id==todo_id).first()

    if todo is None:
        db.close()
        return None

    todo.title=title
    db.commit()
    
    db.refresh(todo)
    result={"id":todo.id,"title":todo.title}
    db.close()

    return result